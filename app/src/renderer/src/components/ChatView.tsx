/**
 * ChatView — OpenCode Desktop-style Command Center.
 *
 * Layout: Sidebar | Chat Area (with inline tool panels) | Status Bar
 *
 * Tool panels are ALWAYS VISIBLE (not collapsible) — matching OpenCode Desktop.
 * Sidebar is compact — session name + time.
 * Status bar shows model, tokens, connection.
 */
import { useEffect, useMemo, useRef, useState, useCallback, useLayoutEffect, memo } from 'react'
import {
  Send, Plus, Search, Trash2,
  FileText, Terminal, Eye, PenLine, Play, Copy, Check,
  Pin, Loader2, Bot, GitBranch, X, PanelRight, Square, Paperclip, ClipboardList,
  Sparkles, ChevronDown, FolderTree,
} from 'lucide-react'
import { cn } from '../lib/utils'
import { conversationsApi, type ConversationRecord, type MessageRecord } from '../lib/api/conversations'
import { chatApi, type ToolCallData, type FileDiffData, type ShellOutputData, type TodoItemData, type DeliverableSummary, type ClarifyPayload } from '../lib/api/chat'
import { providersApi, type ProviderRecord } from '../lib/api/providers'
import { providerManageApi } from '../lib/api/provider_manage'
import { type ProjectRecord } from '../lib/api/projects'
import { ProjectPicker } from './ProjectPicker'
import { FileTree } from './FileTree'
import { resolveDefaultModelId, type ProviderLike } from '../lib/providerModel'
import { clamp, computeMessageWindow } from '../lib/virtualList'
import { WorkflowSelector, WorkflowStepper } from './WorkflowSelector'
import { readPreferredWorkflow, writePreferredWorkflow, getWorkflow } from '../lib/workflows'
import type { WorkflowType, WorkflowTag } from '../lib/api/chat'

// ── Virtual list (windowing) ─────────────────────────────
// Only the visible window of messages is rendered (a 1000-message conversation
// renders ~40-50 rows instead of 1000). We use a fixed-estimate row height that
// is refined over time by measuring the rendered slice (average height), so the
// scrollbar stays aligned with the content even though rows vary in height.
const VIRTUAL_OVERSCAN = 6       // extra rows above/below the viewport
const ROW_HEIGHT_DEFAULT = 64    // initial estimate before first measurement
const ROW_HEIGHT_MIN = 40        // measured average is clamped to this range
const ROW_HEIGHT_MAX = 220       // ...so a tall streaming row can't skew it
const SCROLL_TOLERANCE_PX = 96   // "near bottom" for stick-to-bottom (round-1)

// ── Types ────────────────────────────────────────────────

interface AssistantMessageState {
  content: string
  toolCalls: ToolCallData[]
  fileDiffs: FileDiffData[]
  shellOutputs: Map<string, ShellOutputData>
  todos: TodoItemData[]
  filesModified: string[]
  isStreaming: boolean
  /** 'queued' while the agent waits for a free execution slot (backend emits status "queued"). */
  streamStatus?: 'queued' | 'streaming'
  metadata?: Record<string, any>
  deliverables?: DeliverableSummary
  /** Backend asked clarifying questions (missing project/workspace) — render as a block. */
  clarify?: ClarifyPayload
  /** Workflow type selected by the user (applies to this turn). */
  workflow?: WorkflowType
}

// ── Engine tiers (THINKER / CRAFTER / SPRINTER / VISION) ──

type EngineTier = 'thinker' | 'crafter' | 'sprinter' | 'vision'
type TierSelection = { provider: string; model: string }

const ENGINE_TIERS: EngineTier[] = ['thinker', 'crafter', 'sprinter', 'vision']
const TIER_LABEL_COLORS: Record<EngineTier, string> = {
  thinker: 'text-primary',
  crafter: 'text-success',
  sprinter: 'text-warning',
  vision: 'text-info',
}

// Collision-resistant temp id generator. Date.now() alone can collide when two
// messages are created in the same millisecond (double-send) — crypto.randomUUID
// is preferred, with a timestamp+random fallback for non-secure contexts.
function genId(prefix: string): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `${prefix}-${crypto.randomUUID()}`
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

// ── Markdown ─────────────────────────────────────────────

function MarkdownContent({ content }: { content: string }) {
  if (!content) return null
  const parts: React.ReactNode[] = []
  const lines = content.split('\n')
  let i = 0
  let key = 0

  while (i < lines.length) {
    const line = lines[i]
    if (line.startsWith('```')) {
      const lang = line.slice(3).trim()
      const codeLines: string[] = []
      i++
      while (i < lines.length && !lines[i].startsWith('```')) { codeLines.push(lines[i]); i++ }
      i++
      parts.push(<CodeBlock key={key++} language={lang} code={codeLines.join('\n')} />)
      continue
    }
    if (line.trim() === '') { parts.push(<div key={key++} className="h-1.5" />); i++; continue }
    if (line.startsWith('## ')) { parts.push(<h2 key={key++} className="text-sm font-bold mt-3 mb-1">{renderInline(line.slice(3))}</h2>); i++; continue }
    if (line.startsWith('### ')) { parts.push(<h3 key={key++} className="text-xs font-semibold mt-2 mb-0.5">{renderInline(line.slice(4))}</h3>); i++; continue }
    if (line.match(/^\s*[-*]\s/)) {
      parts.push(<div key={key++} className="flex gap-1.5 pl-1"><span className="text-muted-foreground/60 shrink-0">·</span><span>{renderInline(line.replace(/^\s*[-*]\s/, ''))}</span></div>)
      i++; continue
    }
    parts.push(<p key={key++} className="leading-relaxed">{renderInline(line)}</p>)
    i++
  }
  return <div className="space-y-0.5 text-[13px]">{parts}</div>
}

function renderInline(text: string): React.ReactNode {
  const nodes: React.ReactNode[] = []
  let remaining = text
  let key = 0
  while (remaining.length > 0) {
    const boldMatch = remaining.match(/\*\*(.+?)\*\*/)
    const codeMatch = remaining.match(/`([^`]+)`/)
    const linkMatch = remaining.match(/\[([^\]]+)\]\(([^)]+)\)/)
    const matches = [
      boldMatch ? { type: 'bold' as const, match: boldMatch, index: boldMatch.index! } : null,
      codeMatch ? { type: 'code' as const, match: codeMatch, index: codeMatch.index! } : null,
      linkMatch ? { type: 'link' as const, match: linkMatch, index: linkMatch.index! } : null,
    ].filter(Boolean).sort((a, b) => a!.index - b!.index)
    if (matches.length === 0) { nodes.push(<span key={key++}>{remaining}</span>); break }
    const first = matches[0]!
    if (first.index > 0) nodes.push(<span key={key++}>{remaining.slice(0, first.index)}</span>)
    if (first.type === 'bold') { nodes.push(<strong key={key++} className="font-semibold">{first.match[1]}</strong>); remaining = remaining.slice(first.index + first.match[0].length) }
    else if (first.type === 'code') { nodes.push(<code key={key++} className="rounded bg-muted px-1 py-0.5 font-mono text-[0.82em] text-primary">{first.match[1]}</code>); remaining = remaining.slice(first.index + first.match[0].length) }
    else if (first.type === 'link') {
      const href = first.match[2]
      // Only render http(s) links as anchors — data:/file:/javascript: URLs
      // are rendered as plain text to avoid unsafe navigation.
      if (/^https?:\/\//i.test(href)) {
        // Open trusted external links through the main process (window.open /
        // target=_blank are denied by setWindowOpenHandler). Only allow the
        // same allowlist enforced in main.ts's aic:open-external handler; any
        // other https URL is left inert (preventDefault) rather than navigating.
        const ALLOWED = /^https:\/\/(github\.com|raw\.githubusercontent\.com|api\.github\.com)\//
        nodes.push(
          <a
            key={key++}
            href={href}
            className="text-primary underline"
            target="_blank"
            rel="noreferrer"
            onClick={(e) => {
              e.preventDefault()
              if (window.aic?.openExternal && ALLOWED.test(href)) {
                void window.aic.openExternal(href)
              }
            }}
          >
            {first.match[1]}
          </a>,
        )
      } else {
        nodes.push(<span key={key++}>{first.match[0]}</span>)
      }
      remaining = remaining.slice(first.index + first.match[0].length)
    }
  }
  return <>{nodes}</>
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;')
}

function highlightCode(code: string, language: string): string {
  const safe = escapeHtml(code)
  const isJs = ['js', 'ts', 'jsx', 'tsx', 'javascript', 'typescript'].includes(language)
  const isPy = ['py', 'python'].includes(language)
  const isJson = ['json'].includes(language)
  if (!isJs && !isPy && !isJson) return safe

  // FIX: single-pass tokenizer. The old chain-of-replace approach ran each regex
  // over the already-marked output, so the injected `<span class="...">` markup
  // got re-matched (e.g. the string regex matched the class quotes and `\b\d+\b`
  // matched the `400` in `text-purple-400`), corrupting class attributes. Here
  // every token class is matched against the ORIGINAL escaped source only, and
  // we emit the span in the same pass — injected markup is never re-processed.
  const keywordRe = isPy
    ? /\b(def|class|import|from|return|if|elif|else|for|while|try|except|finally|with|as|yield|lambda|pass|break|continue|raise|global|nonlocal|and|or|not|is|in|async|await|self)\b/
    : isJson
      ? null
      : /\b(const|let|var|function|return|import|export|from|class|extends|if|else|for|while|do|switch|case|break|continue|new|this|typeof|instanceof|async|await|try|catch|throw|finally|yield|of|in)\b/
  const literalRe = /\b(true|false|null|undefined|NaN|Infinity)\b/
  const stringRe = /(["'`])(?:(?!\1).)*?\1/
  const commentRe = isPy ? /#[^\n]*/ : /\/\/[^\n]*/
  const numberRe = isJson ? /\b\d+\.?\d*\b/ : /\b\d+\b/

  const parts: string[] = []
  let i = 0
  while (i < safe.length) {
    const rest = safe.slice(i)
    // Compute every candidate token, then pick the one that starts earliest so
    // the injected span markup is never re-processed.
    const candidates: { index: number; cls: string; src: string }[] = []
    for (const [re, cls] of [
      [commentRe, 'text-muted-foreground/50'],
      [stringRe, 'text-emerald-400'],
      [keywordRe, 'text-purple-400'],
      [literalRe, 'text-orange-400'],
      [numberRe, 'text-orange-400'],
    ] as const) {
      if (!re) continue
      const m = re.exec(rest)
      if (m) candidates.push({ index: m.index, cls, src: m[0] })
    }
    let best: { index: number; cls: string; src: string } | null = null
    for (const c of candidates) {
      if (!best || c.index < best.index) best = c
    }
    if (!best) {
      parts.push(rest)
      break
    }
    if (best.index > 0) parts.push(rest.slice(0, best.index))
    parts.push(`<span class="${best.cls}">${best.src}</span>`)
    i += best.index + best.src.length
  }
  return parts.join('')
}

function CodeBlock({ language, code }: { language: string; code: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <div className="my-2 overflow-hidden rounded-lg border border-border/60 bg-[oklch(0.12_0.005_250)]">
      <div className="flex items-center justify-between border-b border-border/30 px-3 py-1">
        <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground/60">{language || 'code'}</span>
        <button onClick={async () => { await navigator.clipboard.writeText(code); setCopied(true); setTimeout(() => setCopied(false), 1500) }}
          className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[9px] text-muted-foreground/60 hover:text-foreground">
          {copied ? <Check className="size-2.5 text-success" /> : <Copy className="size-2.5" />}{copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre className="overflow-x-auto p-3 text-[12px] leading-relaxed">
        <code className="font-mono text-foreground/80" dangerouslySetInnerHTML={{ __html: highlightCode(code, language) }} />
      </pre>
    </div>
  )
}

// ── Tool Panels (INLINE — always visible, OpenCode style) ─

const TOOL_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  read_file: Eye, write_file: PenLine, shell: Play, explore: FileText, search: Search, mcp_call: GitBranch,
}
const TOOL_COLORS: Record<string, string> = {
  read_file: 'text-info', write_file: 'text-success', shell: 'text-warning',
  explore: 'text-primary', search: 'text-primary', mcp_call: 'text-primary',
}

const ToolPanelInline = memo(function ToolPanelInline({ toolCall }: { toolCall: ToolCallData }) {
  const Icon = TOOL_ICONS[toolCall.type] || FileText
  const color = TOOL_COLORS[toolCall.type] || 'text-muted-foreground'
  const isError = toolCall.status === 'error'
  const isRunning = toolCall.status === 'running'

  return (
    <div className={cn(
      "my-1 rounded-lg border px-3 py-2",
      isError ? "border-destructive/30 bg-destructive/5" : "border-border/40 bg-muted/20"
    )}>
      {/* Header — always visible */}
      <div className="flex items-center gap-2">
        {isRunning ? (
          <Loader2 className={cn("size-3 animate-spin", color)} />
        ) : (
          <Icon className={cn("size-3", color)} />
        )}
        <span className="text-[11px] font-medium flex-1 truncate">{toolCall.label}</span>
        <span className="text-[9px] text-muted-foreground/60 tabular-nums">{toolCall.duration_ms ? `${toolCall.duration_ms}ms` : ''}</span>
        {isError && <span className="text-[9px] text-destructive">error</span>}
        {toolCall.status === 'completed' && !isError && <Check className="size-2.5 text-success" />}
      </div>

      {/* Output — always visible (not collapsible) */}
      {toolCall.output && (
        <pre className="mt-1.5 whitespace-pre-wrap font-mono text-[10px] text-muted-foreground/70 leading-relaxed max-h-32 overflow-y-auto scroll-thin">
          {toolCall.output.slice(0, 2000)}
        </pre>
      )}
    </div>
  )
})

const FileDiffInline = memo(function FileDiffInline({ diff }: { diff: FileDiffData }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="my-1 rounded-lg border border-border/40 bg-muted/10 px-3 py-2">
      <div className="flex items-center gap-2">
        <GitBranch className={cn("size-3",
          diff.action === 'created' ? 'text-success' : diff.action === 'deleted' ? 'text-destructive' : 'text-warning'
        )} />
        <span className="text-[11px] font-mono font-medium flex-1 truncate">{diff.path}</span>
        <span className={cn("text-[9px] rounded px-1 py-0.5 font-medium",
          diff.action === 'created' ? 'bg-success/15 text-success' :
          diff.action === 'deleted' ? 'bg-destructive/15 text-destructive' :
          'bg-warning/15 text-warning'
        )}>{diff.action}</span>
        <button onClick={() => setExpanded(!expanded)} className="text-[9px] text-muted-foreground/60 hover:text-foreground">
          {expanded ? 'hide' : 'diff'}
        </button>
      </div>
      {expanded && diff.action !== 'deleted' && (
        <pre className="mt-2 whitespace-pre-wrap font-mono text-[10px] text-foreground/60 leading-relaxed max-h-40 overflow-y-auto scroll-thin bg-[oklch(0.12_0.005_250)] rounded p-2">
          {diff.after.slice(0, 3000)}
        </pre>
      )}
    </div>
  )
})

const ShellOutputInline = memo(function ShellOutputInline({ command, outputs }: { command: string; outputs: ShellOutputData[] }) {
  const fullOutput = outputs.map(o => o.chunk).join('')
  const lastStatus = outputs[outputs.length - 1]?.status || 'running'
  const exitCode = outputs.find(o => o.exit_code !== null)?.exit_code

  return (
    <div className={cn("my-1 rounded-lg border px-3 py-2",
      lastStatus === 'error' ? "border-destructive/30 bg-destructive/5" : "border-border/40 bg-muted/10"
    )}>
      <div className="flex items-center gap-2">
        <Play className="size-3 text-warning" />
        <span className="text-[11px] font-mono font-medium flex-1 truncate">$ {command}</span>
        {lastStatus === 'running' && <Loader2 className="size-2.5 animate-spin text-muted-foreground" />}
        {exitCode !== null && exitCode !== undefined && (
          <span className={cn("text-[9px] tabular-nums", exitCode === 0 ? "text-success" : "text-destructive")}>
            exit {exitCode}
          </span>
        )}
      </div>
      {fullOutput && (
        <pre className="mt-1.5 whitespace-pre-wrap font-mono text-[10px] text-muted-foreground/60 leading-relaxed max-h-32 overflow-y-auto scroll-thin">
          {fullOutput.slice(0, 2000)}
        </pre>
      )}
    </div>
  )
})

function DeliverableSummaryPanel({ deliverables }: { deliverables: DeliverableSummary }) {
  const [showPreviews, setShowPreviews] = useState<Set<string>>(new Set())

  const togglePreview = (path: string) => {
    setShowPreviews(prev => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }

  const hasTests = deliverables.tests.passed > 0 || deliverables.tests.failed > 0
  const hasErrors = deliverables.errors.length > 0

  return (
    <div className="my-2 rounded-lg border border-primary/20 bg-primary/5 p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <FileText className="size-3.5 text-primary" />
          <span className="text-[11px] font-semibold text-primary">Deliverables</span>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            className="rounded px-2 py-0.5 text-[9px] font-medium bg-primary/15 text-primary hover:bg-primary/25 disabled:opacity-50"
            disabled
            title="Download All (coming soon)"
            onClick={() => {}}
          >
            Download All (soon)
          </button>
          <button
            className="rounded px-2 py-0.5 text-[9px] font-medium bg-success/15 text-success hover:bg-success/25 disabled:opacity-50"
            disabled
            title="Approve (coming soon)"
            onClick={() => {}}
          >
            Approve (soon)
          </button>
        </div>
      </div>

      {/* Files */}
      {deliverables.files.length > 0 && (
        <div className="mb-2">
          <div className="text-[10px] font-medium text-muted-foreground/70 mb-1">
            Files ({deliverables.files.length})
          </div>
          <div className="space-y-1">
            {deliverables.files.map((file, i) => (
              <div key={i} className="rounded border border-border/30 bg-muted/10 px-2 py-1.5">
                <div className="flex items-center gap-2">
                  <span className={cn("text-[9px] rounded px-1 py-0.5 font-medium",
                    file.action === 'created' ? 'bg-success/15 text-success' :
                    file.action === 'modified' ? 'bg-warning/15 text-warning' :
                    'bg-muted/30 text-muted-foreground'
                  )}>{file.action}</span>
                  <span className="text-[10px] font-mono flex-1 truncate">{file.path}</span>
                  <span className="text-[8px] text-muted-foreground/50">{file.size}B</span>
                  <button
                    onClick={() => togglePreview(file.path)}
                    className="text-[8px] text-muted-foreground/60 hover:text-foreground"
                  >
                    {showPreviews.has(file.path) ? 'hide' : 'preview'}
                  </button>
                </div>
                {showPreviews.has(file.path) && file.preview && (
                  <pre className="mt-1.5 whitespace-pre-wrap font-mono text-[9px] text-muted-foreground/60 leading-relaxed max-h-24 overflow-y-auto scroll-thin bg-[oklch(0.12_0.005_250)] rounded p-1.5">
                    {file.preview}
                  </pre>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tests */}
      {hasTests && (
        <div className="mb-2">
          <div className="text-[10px] font-medium text-muted-foreground/70 mb-1">Tests</div>
          <div className="flex items-center gap-3 text-[10px]">
            {deliverables.tests.passed > 0 && (
              <span className="text-success">{deliverables.tests.passed} passed</span>
            )}
            {deliverables.tests.failed > 0 && (
              <span className="text-destructive">{deliverables.tests.failed} failed</span>
            )}
          </div>
          {deliverables.tests.output && (
            <pre className="mt-1 whitespace-pre-wrap font-mono text-[9px] text-muted-foreground/60 leading-relaxed max-h-20 overflow-y-auto scroll-thin">
              {deliverables.tests.output.slice(0, 1000)}
            </pre>
          )}
        </div>
      )}

      {/* Shell Commands */}
      {deliverables.shell_commands.length > 0 && (
        <div className="mb-2">
          <div className="text-[10px] font-medium text-muted-foreground/70 mb-1">
            Commands ({deliverables.shell_commands.length})
          </div>
          <div className="space-y-0.5">
            {deliverables.shell_commands.slice(0, 5).map((cmd, i) => (
              <div key={i} className="text-[9px] font-mono text-muted-foreground/60 truncate">
                $ {cmd}
              </div>
            ))}
            {deliverables.shell_commands.length > 5 && (
              <div className="text-[8px] text-muted-foreground/40">
                +{deliverables.shell_commands.length - 5} more
              </div>
            )}
          </div>
        </div>
      )}

      {/* Errors */}
      {hasErrors && (
        <div>
          <div className="text-[10px] font-medium text-destructive mb-1">
            Errors ({deliverables.errors.length})
          </div>
          <div className="space-y-0.5">
            {deliverables.errors.slice(0, 3).map((err, i) => (
              <div key={i} className="text-[9px] text-destructive/80">
                <span className="font-medium">{err.tool}:</span> {err.error}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Message Row ──────────────────────────────────────────

/** Plain-text fallback of a clarify payload (persisted into the message). */
function formatClarify(p: ClarifyPayload): string {
  const lines = [p.reason ||  'Before we start, I need some details:']
  p.questions?.forEach((q, i) => {
    lines.push(`\n${i + 1}. ${q.question}`)
    if (q.options?.length) lines.push(`   Pilihan: ${q.options.join(', ')}`)
  })
  return lines.join('\n')
}

/** Structured "I need a few details" assistant block (clarify SSE event).
 *
 * Interactive: each question renders clickable option chips plus a free-text
 * field ("or specify your own"). "Send answers" submits a compact Q->A summary
 * straight into the discovery pipeline - no manual typing needed.
 */
function ClarifyBlock({ payload, onPickWorkspaceFolder, onSubmitAnswer }: { payload: ClarifyPayload; onPickWorkspaceFolder?: () => void; onSubmitAnswer?: (text: string) => void }) {
  const intro = payload.reason || 'Before we start, I need some details:'
  const [answers, setAnswers] = useState<Record<string, string>>({})

  const total = payload.questions?.length || 0
  const answeredCount = payload.questions?.filter(q => (answers[q.id] || '').trim()).length || 0

  // Compact "Q -> A" summary consumed by discovery.respond_to_clarification (plain text).
  const buildAnswerText = (): string =>
    (payload.questions || []).map((q, i) => {
      const a = (answers[q.id] || '').trim()
      return `${i + 1}. ${q.question} -> ${a || '(not answered)'}`
    }).join('\n')

  const handleSendAnswers = () => {
    if (!answeredCount || !onSubmitAnswer) return
    onSubmitAnswer(buildAnswerText())
  }

  return (
    <div className="my-1 rounded-lg border border-info/30 bg-info/5 p-3">
      <div className="flex items-center gap-2">
        <ClipboardList className="size-3.5 text-info" />
                <span className="text-[11px] font-semibold text-info">A few clarifying questions</span>
      </div>
      <p className="mt-2 text-[12px] leading-relaxed text-foreground/85">{intro}</p>
      <ol className="mt-2 space-y-2">
        {payload.questions?.map((q, i) => {
          const selected = answers[q.id] || ''
          return (
            <li key={q.id} className="rounded-md border border-border/50 bg-card/60 p-2">
              <div className="flex items-start gap-2">
                <span className="mt-0.5 grid size-4 shrink-0 place-items-center rounded-full bg-info/15 text-[9px] font-semibold text-info">{i + 1}</span>
                <span className="text-[12px] leading-snug">{q.question}</span>
              </div>
              {q.options?.length ? (
                <div className="mt-1.5 flex flex-wrap gap-1 pl-6">
                  {q.options.map(opt => {
                    const isSel = selected === opt
                    return (
                      <button
                        key={opt}
                        type="button"
                        disabled={!onSubmitAnswer}
                        onClick={() => setAnswers(prev => ({ ...prev, [q.id]: isSel ? '' : opt }))}
                        className={cn(
                          'rounded border px-1.5 py-0.5 text-[10px] font-mono transition-colors',
                          isSel
                            ? 'border-info bg-info/15 text-info'
                            : 'border-border/60 bg-muted/40 text-muted-foreground hover:border-info/50 hover:text-foreground',
                        )}
                      >
                        {opt}
                      </button>
                    )
                  })}
                </div>
              ) : null}
              {/* Free-text answer - doubles as "specify your own" for option questions */}
              <div className="mt-1.5 pl-6">
                <input
                  type="text"
                  placeholder={q.options?.length ? '...or type your own answer' : 'Type your answer...'}
                  value={selected}
                  onChange={e => setAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
                  className="w-full max-w-[420px] rounded border border-border/50 bg-background/50 px-2 py-1 text-[11px] outline-none placeholder:text-muted-foreground/40 focus:border-info/50"
                />
              </div>
              {/* Workspace question affordance */}
              {q.id === 'workspace' && onPickWorkspaceFolder && (
                <button
                  type="button"
                  onClick={onPickWorkspaceFolder}
                  className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-border/50 bg-muted/40 px-2.5 py-1 text-[11px] font-medium text-foreground hover:bg-muted/70"
                  title="Select an absolute folder path to use as the workspace root"
                >
                  <PanelRight className="size-3.5" />
                  Select a folder...
                </button>
              )}
            </li>
          )
        })}
      </ol>
      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="text-[10px] text-muted-foreground/70">
          {answeredCount ? `${answeredCount}/${total} answered` : 'Pick an option or type an answer, then send.'}
        </span>
        {answeredCount > 0 && (
          <button
            type="button"
            onClick={handleSendAnswers}
            disabled={!onSubmitAnswer}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-2.5 py-1 text-[11px] font-medium text-primary-foreground disabled:opacity-40 hover:bg-primary/90"
          >
            <Send className="size-3" />
            Send answers
          </button>
        )}
      </div>
    </div>
  )
}

// Exported for the component test (ChatView.test.tsx) — a real component test
// renders MessageRow directly with a sample message instead of mocking the
// whole ChatView (api calls, SSE, sessionStorage, ResizeObserver…).
export const MessageRow = memo(function MessageRow({ message, state, onPickWorkspaceFolder, onSubmitAnswer }: { message: MessageRecord; state?: AssistantMessageState; onPickWorkspaceFolder?: () => void; onSubmitAnswer?: (text: string) => void }) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div className="py-3 px-1">
        <div className="flex justify-end">
          <div className="flex items-start gap-2 max-w-[80%]">
            <span className="mt-0.5 shrink-0 font-mono text-xs font-bold text-primary/70 select-none">❯</span>
            <p className="text-[13px] leading-relaxed whitespace-pre-wrap">{message.content}</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="py-3 px-1">
      {/* Tool calls — inline, always visible */}
      {state?.toolCalls.map(tc => <ToolPanelInline key={tc.id} toolCall={tc} />)}

      {/* Shell outputs — inline, always visible */}
      {state && (() => {
        const grouped = new Map<string, ShellOutputData[]>()
        for (const [, output] of state.shellOutputs) {
          const existing = grouped.get(output.command) || []
          existing.push(output)
          grouped.set(output.command, existing)
        }
        return Array.from(grouped.entries()).map(([cmd, outputs]) => (
          <ShellOutputInline key={cmd} command={cmd} outputs={outputs} />
        ))
      })()}

      {/* File diffs — inline */}
      {state?.fileDiffs.map((diff, i) => <FileDiffInline key={diff.path + i} diff={diff} />)}

      {/* Deliverables — shown when agent completes */}
      {state?.deliverables && <DeliverableSummaryPanel deliverables={state.deliverables} />}

      {/* Message content */}
      <div className="flex items-start gap-2">
        <div className="mt-0.5 grid size-4 shrink-0 place-items-center rounded bg-muted/50">
          <Bot className="size-2.5 text-muted-foreground" />
        </div>
        <div className="min-w-0 flex-1">
          {/* PERF-FIX: single source of truth — streaming content lives in
              assistantStates; the messages array is finalized on done. */}
          {(() => {
            const contentText = state?.content ?? message.content
            const isStreaming = state?.isStreaming
            // Clarify renders as a structured block (from live state OR the
            // metadata persisted on the finalized message) instead of text.
            const clarify = state?.clarify
              ?? (message.role === 'assistant'
                ? (message.message_metadata as { clarify?: ClarifyPayload } | undefined)?.clarify
                : undefined)
            if (clarify) {
              return <ClarifyBlock payload={clarify} onPickWorkspaceFolder={onPickWorkspaceFolder} onSubmitAnswer={onSubmitAnswer} />
            }
            // Workflow stepper: when this turn runs a specific workflow, show the
            // phase pipeline (only the phases that workflow allows) instead of a
            // bare "thinking…" line. Activity is derived from tool calls + content.
            if (state?.workflow && isStreaming) {
              const status = state.streamStatus === 'queued' ? 'queued' : 'executing'
              const toolProgress = Math.min(state.toolCalls.length / 6, 1) * 0.6
              const contentProgress = Math.min(contentText.length / 2000, 1) * 0.4
              const activity = Math.min(toolProgress + contentProgress, 0.99)
              return (
                <div className="space-y-2">
                  <WorkflowStepper type={state.workflow} status={status} activity={activity} />
                  {contentText && <MarkdownContent content={contentText} />}
                </div>
              )
            }
            if (isStreaming && !contentText) {
              return (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Loader2 className="size-3 animate-spin" />
                  {state?.streamStatus === 'queued'
                    ? <span>Queued — waiting for a free agent slot…</span>
                    : <span>thinking…</span>}
                </div>
              )
            }
            return (
              <>
                <MarkdownContent content={contentText} />
                {isStreaming && contentText && (
                  <span className="inline-block h-3.5 w-1 animate-pulse bg-primary/60 ml-0.5 align-middle" />
                )}
              </>
            )
          })()}
        </div>
      </div>
    </div>
  )
})

// ── Sidebar (compact) ────────────────────────────────────

function Sidebar({ conversations, activeId, onSelect, onCreate, onDelete, onDuplicate, onSearch }: {
  conversations: ConversationRecord[]; activeId: string | null;
  onSelect: (id: string) => void; onCreate: () => void;
  onDelete: (id: string, e: React.MouseEvent) => void;
  onDuplicate: (id: string, e: React.MouseEvent) => void; onSearch: (q: string) => void;
}) {
  const [query, setQuery] = useState('')
  // Debounce sidebar search so keystrokes don't fire a search per character.
  useEffect(() => {
    const timer = setTimeout(() => onSearch(query), 250)
    return () => clearTimeout(timer)
  }, [query, onSearch])

  return (
    <aside className="flex w-44 lg:w-52 shrink-0 flex-col border-r border-border bg-sidebar">
      <div className="p-2 space-y-1.5">
        <button onClick={onCreate}
          className="flex w-full items-center gap-1.5 rounded-md bg-primary/15 px-2.5 py-1.5 text-[11px] font-medium text-primary hover:bg-primary/25">
          <Plus className="size-3" /> New Session
        </button>
        <div className="flex items-center gap-1.5 rounded-md border border-border/50 bg-card/50 px-2 py-1 focus-within:border-primary/40">
          <Search className="size-2.5 text-muted-foreground/60" />
          <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search…"
            className="w-full bg-transparent text-[10px] outline-none placeholder:text-muted-foreground/40" />
        </div>
      </div>
      <div className="flex-1 overflow-y-auto scroll-thin px-1.5 pb-1.5">
        {conversations.length === 0 ? (
          <div className="px-2 py-6 text-center text-[10px] text-muted-foreground/50">No sessions</div>
        ) : (
          <div className="space-y-px">
            {conversations.map(c => {
              const active = c.id === activeId
              return (
                <div key={c.id} onClick={() => onSelect(c.id)}
                  role="button"
                  tabIndex={0}
                  aria-label={`Open session ${c.title}`}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onSelect(c.id);
                    }
                  }}
                  className={cn(
                    'group relative flex cursor-pointer items-center justify-between rounded-md px-2.5 py-1.5 transition-colors',
                    active ? 'bg-muted/80 text-foreground' : 'text-muted-foreground hover:bg-muted/40 hover:text-foreground',
                  )}>
                  <div className="flex items-center gap-1.5 min-w-0">
                    {c.is_pinned && <Pin className="size-2.5 text-primary shrink-0" />}
                    <span className="truncate text-[11px]">{c.title}</span>
                  </div>
                  <span className="shrink-0 text-[8px] opacity-40 tabular-nums ml-2">
                    {new Date(c.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                  <div className="absolute right-1 top-1 hidden items-center gap-px rounded bg-muted/80 px-0.5 py-0.5 group-hover:flex">
                    <button onClick={e => onDuplicate(c.id, e)} className="p-0.5 text-muted-foreground hover:text-foreground" aria-label={`Duplicate ${c.title}`}>
                      <Copy className="size-2" />
                    </button>
                    <button onClick={e => onDelete(c.id, e)} className="p-0.5 text-muted-foreground hover:text-destructive" aria-label={`Delete ${c.title}`}>
                      <Trash2 className="size-2" />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </aside>
  )
}

// ── Main ChatView ────────────────────────────────────────

export function ChatView({ health = 'unknown', currentProvider = null, view = '', newSessionSignal = 0, projectRoot = null, projectName = null, projectRefreshKey = 0, onProjectChange }: {
  health?: 'ok' | 'bad' | 'unknown'; currentProvider?: ProviderLike | null; view?: string; newSessionSignal?: number;
  projectRoot?: string | null; projectName?: string | null; projectRefreshKey?: number;
  onProjectChange?: (project: ProjectRecord | null) => void;
}) {
  const [conversations, setConversations] = useState<ConversationRecord[]>([])
  const [activeId, setActiveId] = useState<string | null>(() => {
    try { return sessionStorage.getItem('aic-ade-active-conversation') }
    catch { return null }
  })
  const [messages, setMessages] = useState<MessageRecord[]>([])
  const [input, setInput] = useState('')
  const [attachments, setAttachments] = useState<File[]>([])
  const [attachWarnings, setAttachWarnings] = useState<string[]>([])
  const [dragActive, setDragActive] = useState(false)
  const [visionWarning, setVisionWarning] = useState('')
  const [sending, setSending] = useState(false)
  const [assistantStates, setAssistantStates] = useState<Map<string, AssistantMessageState>>(new Map())
  const [contextOptimized, setContextOptimized] = useState(false)
  const [explorerOpen, setExplorerOpen] = useState(false)
  const [fileTreeFilter, setFileTreeFilter] = useState('')
  const [providers, setProviders] = useState<ProviderRecord[]>([])
  const [tiers, setTiers] = useState<Record<EngineTier, TierSelection>>({
    thinker: { provider: '', model: '' },
    crafter: { provider: '', model: '' },
    sprinter: { provider: '', model: '' },
    vision: { provider: '', model: '' },
  })
  // Active project — used for the sidebar picker AND sent with chat requests
  // (`workspace` = repo_path, `project_id` = id) so the dispatcher creates
  // project folders in the user's chosen location instead of the app data dir.
  const [activeProject, setActiveProject] = useState<ProjectRecord | null>(null)
  // Project file panel — shows the active project's file tree in the Command
  // Center main area so a selected project's contents are visible immediately.
  // Auto-open the explorer when a project is selected so the user sees the
  // workspace/files hierarchy without an extra click.
  useEffect(() => {
    if (activeProject?.repo_path || projectRoot) {
      setExplorerOpen(true)
    }
  }, [activeProject?.repo_path, projectRoot])
  // ── Workflow selection ────────────────────────────────────
  // The next message is tagged with the selected workflow type (if any). When
  // unset the backend auto-triages the task type. Selection persists in state
  // until cleared; the preferred workflow is restored from localStorage.
  const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowType | null>(() => readPreferredWorkflow())
  const [workflowPanelOpen, setWorkflowPanelOpen] = useState(false)
  const [fetchingModels, setFetchingModels] = useState(false)
  const [compacting, setCompacting] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const shouldAutoScrollRef = useRef(true)
  // ── Virtual list state (round-8) ────────────────────────
  // scrollTop/containerHeight drive the visible window; rowHeight is the
  // measured average row height (estimated first, refined by measurement so
  // the scrollbar stays aligned with variable-height rows).
  const [scrollTop, setScrollTop] = useState(0)
  const [containerHeight, setContainerHeight] = useState(0)
  const [rowHeight, setRowHeight] = useState(ROW_HEIGHT_DEFAULT)
  const rowHeightRef = useRef(ROW_HEIGHT_DEFAULT)
  const sliceRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const abortRef = useRef<(() => void) | null>(null)
  const streamMsgIdRef = useRef<string | null>(null)
  // PERF-FIX: mutable buffer for the streaming assistant content — avoids a
  // full messages-array map + string rebuild on every chunk. Written to the
  // messages array once on done (single source of truth = assistantStates).
  const streamContentRef = useRef('')
  const activeIdRef = useRef(activeId)
  const sendingRef = useRef(false)
  const stopRequestedRef = useRef(false)
  const envWriteTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const messagesRef = useRef(messages)
  const loadRequestRef = useRef(0)
  const prevNewSessionSignalRef = useRef(newSessionSignal)
  activeIdRef.current = activeId
  messagesRef.current = messages

  const active = useMemo(() => conversations.find(c => c.id === activeId) ?? null, [conversations, activeId])

  // ── Streaming-in-background detection (round-7) ─────────
  // The temp assistant message carries status "streaming" until the backend
  // commits the response, so its conversation_id identifies the conversation
  // that owns the in-flight stream. If the user navigates to a different
  // conversation mid-stream, the pane must not show the old session's messages
  // under the new session's header — render a "streaming in background"
  // placeholder instead. Stream writes stay keyed by the temp message id, so
  // switching back to the streaming conversation shows the live stream again.
  const streamingConvId = useMemo(() => {
    const streaming = messages.find(m => m.status === 'streaming')
    return streaming?.conversation_id ?? null
  }, [messages])
  const visibleMessages = useMemo(
    () => (activeId ? messages.filter(m => m.conversation_id === activeId) : messages),
    [messages, activeId],
  )
  const streamingBackground = sending && streamingConvId !== null && activeId !== null && activeId !== streamingConvId

  // ── Virtual list: visible window (round-8) ─────────────
  // Only this slice of visibleMessages is rendered; spacers keep the native
  // scroll height identical to a fully-rendered list.
  const listWindow = useMemo(
    () => computeMessageWindow(visibleMessages.length, scrollTop, containerHeight, rowHeight, VIRTUAL_OVERSCAN),
    [visibleMessages, scrollTop, containerHeight, rowHeight],
  )
  const messageSlice = useMemo(
    () => visibleMessages.slice(listWindow.start, listWindow.end),
    [visibleMessages, listWindow],
  )

  // Keep the scroll container height in sync (initial + window resizes). The
  // jsdom test environment has no ResizeObserver, so guard for it.
  useLayoutEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const measure = () => setContainerHeight(el.clientHeight)
    measure()
    if (typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // Refine the row-height estimate by measuring the average height of the
  // rendered slice. EMA smoothing + clamping keep the estimate stable while a
  // tall streaming row is growing; the 4px tolerance prevents feedback loops.
  useLayoutEffect(() => {
    const el = sliceRef.current
    if (!el) return
    const count = el.childElementCount
    if (count < 3) return
    const measured = el.offsetHeight / count
    const prev = rowHeightRef.current
    if (Math.abs(measured - prev) < 4) return
    const next = clamp(prev * 0.6 + measured * 0.4, ROW_HEIGHT_MIN, ROW_HEIGHT_MAX)
    if (Math.abs(next - prev) < 1) return
    rowHeightRef.current = next
    setRowHeight(next)
  })

  // Reset the scroll anchor when the conversation changes so the stale
  // scrollTop from the previous session can't throw the window off.
  useEffect(() => {
    setScrollTop(0)
  }, [activeId])

  // ── Context usage (QA-2439 FIX → QA-2446: consistent per-message estimate)
  // Previous logic switched between backend token_count (crude len//4) and an
  // inflated per-message flat rate depending on whether ANY message had a
  // token_count, causing the display to jump from 3k to ~1 after a reload.
  // Now every message uses the same estimate: char-based floor so short
  // messages still report a reasonable size, falling back to a flat rate
  // when content is empty (e.g. streaming placeholder).
  const estimateTokens = (m: MessageRecord): number => {
    const fromBackend = m.token_count || 0
    const fromContent = m.content ? Math.max(Math.ceil(m.content.length / 4), 1) : 0
    const flat = m.role === 'assistant' ? 200 : 50   // floor for empty/placeholder
    return Math.max(fromBackend, fromContent, flat)
  }
  const totalTokens = useMemo(() => {
    if (messages.length === 0) return 0
    const msgTokens = messages.reduce((sum, m) => sum + estimateTokens(m), 0)
    const system = 500
    return msgTokens + system
  }, [messages])
  const contextWindow = useMemo(() => {
    const sel = tiers.thinker
    const p = providers.find(x => x.name === sel.provider)
    const m = p?.models.find(mm => mm.id === sel.model)
    return m?.capabilities?.contextWindow || 0
  }, [providers, tiers])
  const contextPct = contextWindow > 0 ? Math.min(100, (totalTokens / contextWindow) * 100) : 0
  const contextBarColor = contextPct > 80 ? 'bg-destructive' : contextPct >= 50 ? 'bg-warning' : 'bg-success'

  const loadConversations = async (query = '') => {
    try {
      if (query.trim()) {
        const results = await conversationsApi.search(query)
        const ids = Array.from(new Set(results.map(r => r.conversation_id)))
        // /conversations/search returns ids + snippets, not full records.
        // Re-filtering hits against /conversations (default limit 50) silently
        // dropped matches older than the 50 most-recent — resolve each hit by
        // id instead so the sidebar shows ALL matches for the query.
        setConversations(await conversationsApi.getMany(ids))
      } else {
        const list = await conversationsApi.list()
        setConversations(list)
        const restored = activeId && list.some(c => c.id === activeId) ? activeId : list[0]?.id || null
        if (restored !== activeId) setActiveId(restored)
      }
    } catch (e) { console.error('Load sessions failed', e) }
  }

  const loadMessages = async (convId: string) => {
    const requestId = ++loadRequestRef.current
    try {
      const loaded = await conversationsApi.listMessages(convId, 1000)
      // A slow response from an older request must never overwrite a newer
      // conversation or the local stream currently being displayed.
      if (requestId !== loadRequestRef.current || activeIdRef.current !== convId) return
      // Keep optimistic messages until matching persisted records arrive. This
      // remains necessary after onDone because /chat/execute commits at the end
      // of the pipeline and a delayed GET can still observe the old snapshot.
      const serverKeys = new Set(loaded.map(m => `${m.role}\u0000${m.content}`))
      const messageTimestamp = (s: string) => {
        const value = Date.parse(s)
        return Number.isFinite(value) ? value : Number.MAX_SAFE_INTEGER
      }
      const localOnly = messagesRef.current.filter(m =>
        m.conversation_id === convId && m.id.startsWith('temp-') &&
        !serverKeys.has(`${m.role}\u0000${m.content}`) &&
        // Once the server has persisted the current assistant response, do
        // not retain an obsolete temp assistant and show the answer twice.
        !(m.role === 'assistant' && loaded.some(server =>
          server.role === 'assistant' && messageTimestamp(server.created_at) >= messageTimestamp(m.created_at) - 5
        ))
      )
      // Stable conversation ordering. Never compare ISO strings directly:
      // Python emits +00:00 while JS emits Z, and legacy rows can have equal
      // timestamps. Numeric parsing plus a small same-turn tolerance keeps
      // each user message before its assistant response after reload.
      const roleRank = (m: MessageRecord) => m.role === 'user' ? 0 : 1
      // Stable ordering fix (chat reorders after view switch): expand the
      // same-turn tolerance and add a tertiary sort by id so messages keep a
      // deterministic order instead of flipping when rapid-fire timestamps
      // differ by more than the old 5ms window.
      setMessages([...loaded, ...localOnly].sort((a, b) =>
        (() => {
          const delta = messageTimestamp(a.created_at) - messageTimestamp(b.created_at)
          if (Math.abs(delta) <= 50) {
            const rank = roleRank(a) - roleRank(b)
            return rank !== 0 ? rank : (a.id ?? '').localeCompare(b.id ?? '')
          }
          return delta
        })()
      ))
    }
    catch (e) { console.error('Load messages failed', e) }
  }

  useEffect(() => { void loadConversations() }, [])
  useEffect(() => {
    try {
      if (activeId) sessionStorage.setItem('aic-ade-active-conversation', activeId)
      else sessionStorage.removeItem('aic-ade-active-conversation')
    } catch { /* ignore storage failures */ }
  }, [activeId])
  // QA-2443 FIX: skip loadMessages while a streaming send is in progress — the API
  // hasn't committed the streaming response yet, so fetching would wipe local state.
  // QA-2445: delayed reload after sending completes to let API commit.
  useEffect(() => {
    if (activeId && !sending) {
      const timer = setTimeout(() => void loadMessages(activeId), 3000)
      return () => clearTimeout(timer)
    } else if (!activeId) {
      setMessages([])
    }
  }, [activeId, sending])
  // BUG-2 FIX: Abort any in-flight stream when ChatView unmounts to prevent orphaned SSE connections.
  useEffect(() => {
    return () => {
      abortRef.current?.(); abortRef.current = null
      if (envWriteTimerRef.current) clearTimeout(envWriteTimerRef.current)
    }
  }, [])
  // Prune stale assistantStates when switching conversations — the map is keyed
  // by temp message ids that no longer exist after the conversation changes.
  useEffect(() => {
    setAssistantStates(prev => (prev.size === 0 ? prev : new Map()))
  }, [activeId])
  useEffect(() => {
    const el = scrollRef.current
    if (!el || !shouldAutoScrollRef.current) return
    el.scrollTop = el.scrollHeight
    // rowHeight in deps: when the measurement refines the estimate (or the
    // container resizes), re-anchor to the bottom so the streaming/last
    // message stays in view — but only when the user is already at/near the
    // bottom (shouldAutoScrollRef), never when they scrolled up.
  }, [messages, assistantStates, rowHeight, containerHeight])
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 160) + 'px'
    }
  }, [input])

  const updateAssistantState = useCallback((msgId: string, updater: (prev: AssistantMessageState) => AssistantMessageState) => {
    setAssistantStates(prev => {
      const next = new Map(prev)
      const current = next.get(msgId) || { content: '', toolCalls: [], fileDiffs: [], shellOutputs: new Map(), todos: [], filesModified: [], isStreaming: true }
      next.set(msgId, updater(current))
      return next
    })
  }, [])

  // ── Engine tier config (THINKER/CRAFTER/SPRINTER/VISION) ──
  const loadEngineConfig = useCallback(async () => {
    try {
      const [envCfg, pList] = await Promise.all([
        providerManageApi.getEnvConfig(),
        providersApi.list(),
      ])
      setProviders(pList)
      let saved: Record<string, string> = {}
      try { saved = JSON.parse(localStorage.getItem('aic-ade-engine-tiers') || '{}') } catch { /* ignore */ }
      try {
        const ipcCfg = await window.aic?.storeGet?.('engineConfig') as Record<string, string> | null
        if (ipcCfg) saved = { ...saved, ...ipcCfg }
      } catch { /* ignore */ }
      const bootProvider = currentProvider?.name || ''
      const bootModel = resolveDefaultModelId(currentProvider)
      const defaultProvider = envCfg.provider_name || bootProvider || pList[0]?.name || ''
      const defaultModel = envCfg.thinker || bootModel || ''
      setTiers({
        thinker: { provider: saved.thinkerProvider || defaultProvider, model: saved.thinkerModel || defaultModel },
        crafter: { provider: saved.crafterProvider || defaultProvider, model: saved.crafterModel || envCfg.crafter || bootModel || '' },
        sprinter: { provider: saved.sprinterProvider || defaultProvider, model: saved.sprinterModel || envCfg.sprinter || bootModel || '' },
        vision: { provider: saved.visionProvider || defaultProvider, model: saved.visionModel || envCfg.vision || bootModel || '' },
      })
    } catch (e) { console.error('Load engine config failed', e) }
  }, [currentProvider])

  useEffect(() => { void loadEngineConfig() }, [loadEngineConfig])

  // Reload engine config when the user navigates back to the Command Center,
  // so provider/env changes made in Settings are picked up (ChatView stays
  // mounted while hidden, so the mount-only effect would otherwise go stale).
  const prevViewRef = useRef(view)
  useEffect(() => {
    const entered = (view === 'hermes' || view === 'chat') && prevViewRef.current !== 'hermes' && prevViewRef.current !== 'chat'
    prevViewRef.current = view
    if (entered) void loadEngineConfig()
  }, [view, loadEngineConfig])

  const handleTierChange = useCallback((tier: EngineTier, patch: Partial<TierSelection>) => {
    // BUG-2: The backend EnvConfig is single-provider (one provider_name /
    // base_url / api_key for the whole engine). Per-tier providers are not
    // supported, so when a tier's provider changes, sync every tier to it.
    let next: Record<EngineTier, TierSelection>
    if (patch.provider !== undefined) {
      const pName = patch.provider
      const pModels = providers.find(p => p.name === pName)?.models || []
      const syncedModel = (sel: TierSelection) =>
        patch.model !== undefined ? patch.model : (pModels.some(m => m.id === sel.model) ? sel.model : '')
      next = {
        thinker: { provider: pName, model: syncedModel(tiers.thinker) },
        crafter: { provider: pName, model: syncedModel(tiers.crafter) },
        sprinter: { provider: pName, model: syncedModel(tiers.sprinter) },
        vision: { provider: pName, model: syncedModel(tiers.vision) },
      }
    } else {
      next = { ...tiers, [tier]: { ...tiers[tier], ...patch } }
    }
    setTiers(next)
    const persist = {
      thinkerProvider: next.thinker.provider,
      crafterProvider: next.crafter.provider,
      sprinterProvider: next.sprinter.provider,
      visionProvider: next.vision.provider,
      thinkerModel: next.thinker.model,
      crafterModel: next.crafter.model,
      sprinterModel: next.sprinter.model,
      visionModel: next.vision.model,
    }
    try { localStorage.setItem('aic-ade-engine-tiers', JSON.stringify(persist)) } catch { /* ignore */ }
    void window.aic?.storeSet?.('engineConfig', persist)
    // Debounce the env write so rapid dropdown changes don't spam the backend.
    if (envWriteTimerRef.current) clearTimeout(envWriteTimerRef.current)
    envWriteTimerRef.current = setTimeout(() => {
      const p = providers.find(x => x.name === next.thinker.provider) || providers[0]
      providerManageApi.updateEnvConfig({
        provider_name: p?.name || '',
        base_url: p?.endpoint || '',
        api_key: p?.apiKey || '',
        thinker: next.thinker.model,
        crafter: next.crafter.model,
        sprinter: next.sprinter.model,
        vision: next.vision.model,
      }).catch(e => console.error('Apply engine config failed', e))
    }, 500)
  }, [tiers, providers])

  const handleFetchModels = useCallback(async () => {
    if (fetchingModels) return
    setFetchingModels(true)
    try {
      const current = await providersApi.list()
      const updated: ProviderRecord[] = []
      for (const p of current) {
        try { updated.push(await providersApi.fetchModelsAndUpdate(p.id)) }
        catch (e) { console.error('Fetch models failed for', p.name, e); updated.push(p) }
      }
      setProviders(updated)
    } catch (e) { console.error('Fetch models failed', e) }
    setFetchingModels(false)
  }, [fetchingModels])

  const handleCompact = useCallback(async () => {
    if (compacting || sending || !activeId) return
    setCompacting(true)
    try {
      await loadMessages(activeId)
      setContextOptimized(true)
    } catch (e) { console.error('Compact context failed', e) }
    setCompacting(false)
  }, [compacting, sending, activeId])

  // ── Stop/cancel generation (QA-2437 BUG-4) ─────────────
  const handleStop = useCallback(() => {
    // BUG-11: executeAgent is async — abortRef may still be null when Stop is
    // clicked during setup. Flag the request so handleSend can abort after the
    // cancel fn is returned.
    stopRequestedRef.current = true
    abortRef.current?.()
    abortRef.current = null
    const msgId = streamMsgIdRef.current
    streamMsgIdRef.current = null
    if (msgId) {
      updateAssistantState(msgId, s => ({ ...s, isStreaming: false }))
      setMessages(prev => prev.map(m => m.id === msgId
        ? { ...m, content: (m.content || '') + '\n\n*[stopped]*', status: 'completed' }
        : m))
      // Clean up the temp streaming state entry (BUG-10)
      setAssistantStates(prev => {
        const next = new Map(prev)
        next.delete(msgId)
        return next
      })
    }
    setSending(false)
    sendingRef.current = false
    // QA-2445: Don't reload — useEffect handles it
  }, [updateAssistantState])

  const handleCreate = async () => {
    try {
      const c = await conversationsApi.create('New Session', undefined, [], activeProject?.id)
      setConversations(prev => [c, ...prev])
      setActiveId(c.id)
    } catch (e) { console.error(e) }
  }

  // "New Conversation" from the command palette / app — create a real session.
  useEffect(() => {
    if (newSessionSignal !== prevNewSessionSignalRef.current) {
      prevNewSessionSignalRef.current = newSessionSignal
      void handleCreate()
    }
  }, [newSessionSignal])

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await conversationsApi.delete(id)
      setConversations(prev => prev.filter(c => c.id !== id))
      if (activeId === id) setActiveId(conversations.find(c => c.id !== id)?.id || null)
    } catch (e) { 
      console.error(e)
      alert(`Failed to delete conversation: ${e instanceof Error ? e.message : 'Unknown error'}`)
    }
  }

  const handleDuplicate = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      const dup = await conversationsApi.duplicate(id)
      setConversations(prev => [dup, ...prev])
      setActiveId(dup.id)
    } catch (e) { console.error(e) }
  }

  const handleSend = async (overrideText?: string) => {
    // BUG-1: guard on the ref (set synchronously) instead of the `sending`
    // state, which can be stale in a closure when two Enter presses land in
    // the same tick — the ref closes the double-send race.
    const composed = overrideText ?? input
    if ((!composed.trim() && attachments.length === 0) || sendingRef.current) return
    sendingRef.current = true
    stopRequestedRef.current = false
    const hasImages = attachments.some(file => file.type.startsWith('image/'))
    const visionProvider = providers.find(provider => provider.name === tiers.vision.provider)
    const visionModel = visionProvider?.models.find(model => model.id === tiers.vision.model)
    if (hasImages && (!tiers.vision.model || visionModel?.capabilities.vision !== true)) {
      sendingRef.current = false
      setVisionWarning('The selected Vision model does not support images. Select a model marked Vision in the Vision tier.')
      return
    }
    const text = composed.trim()
    const attachmentText = attachments.map(file => `[Attached file: ${file.name}]`).join('\n')
    const promptText = [text, attachmentText].filter(Boolean).join('\n')
    let attachmentPayload: { name: string; mime_type: string; data_url: string }[] = []
    try {
      attachmentPayload = await Promise.all(attachments.map(readAttachment))
    } catch (error) {
      sendingRef.current = false
      setVisionWarning(error instanceof Error ? error.message : 'Could not read attachment')
      return
    }
    setInput('')
    setAttachments([])
    setVisionWarning('')
    setSending(true)

    // Auto-create session if none active
    let convId = activeId
    if (!convId) {
      try {
        const conv = await conversationsApi.create(promptText.slice(0, 60), undefined, [], activeProject?.id)
        setConversations(prev => [conv, ...prev])
        convId = conv.id
        setActiveId(convId)
      } catch (e: any) {
        const errMsg = e?.message || String(e)
        const tempErr: MessageRecord = {
          id: genId('err'), conversation_id: '', role: 'assistant', content: `Failed to create session: ${errMsg}`,
          status: 'completed', created_at: new Date().toISOString(), updated_at: new Date().toISOString(), attachments: [],
        }
        setMessages(prev => [...prev, tempErr])
        setSending(false)
        sendingRef.current = false
        return
      }
    }

    const tempUserMsg: MessageRecord = {
      id: genId('temp'), conversation_id: convId, role: 'user', content: promptText,
      status: 'completed', created_at: new Date().toISOString(), updated_at: new Date().toISOString(), attachments: [],
      // Persist the selected workflow on the user message so it survives reloads
      // and can be rendered as a badge/tag in the UI.
      message_metadata: selectedWorkflow ? { workflow: selectedWorkflow } : undefined,
    }
    const tempAsstId = genId('temp-ast')
    const tempAsstMsg: MessageRecord = {
      id: tempAsstId, conversation_id: convId, role: 'assistant', content: '',
      status: 'streaming', created_at: new Date().toISOString(), updated_at: new Date().toISOString(), attachments: [],
    }
    setMessages(prev => [...prev, tempUserMsg, tempAsstMsg])
    setAssistantStates(prev => {
      const next = new Map(prev)
      next.set(tempAsstId, { content: '', toolCalls: [], fileDiffs: [], shellOutputs: new Map(), todos: [], filesModified: [], isStreaming: true, workflow: selectedWorkflow ?? undefined })
      return next
    })
    streamMsgIdRef.current = tempAsstId
    streamContentRef.current = ''

    // Build workflow tags from the selected workflow type. Empty when the user
    // left it on auto (backend will triage the task type itself).
    const workflowTags: WorkflowTag[] = selectedWorkflow
      ? [{ workflow: selectedWorkflow }]
      : []

    try {
      // Use executeAgent — goes through ConversationEngine → Dispatcher → Orchestrator → Workers
      // executeAgent returns an AbortController-backed cancel fn (QA-2437 BUG-4)
      // workspace + project_id: send the active project (repo_path + id) so the
      // dispatcher creates folder/files inside the user's chosen project folder.
      // NOTE: no worker_role is sent — Hermes is the dispatcher, so the backend
      // maps the selected workflow tags to the correct worker role itself
      // (chat.py only maps when worker_role is omitted). No agent-mode toggle.
      abortRef.current = await chatApi.executeAgent(
        {
          conversation_id: convId,
          messages: [{ role: 'user', content: promptText }],
          model_tier: hasImages ? 'vision' : 'crafter',
          attachments: attachmentPayload,
          workspace: activeProject?.repo_path || projectRoot || undefined,
          project_id: activeProject?.id || undefined,
          // Tag the task with the chosen workflow so the dispatcher runs the
          // right phase pipeline (bugfix/build/etc). Omit when auto.
          tags: workflowTags.length ? workflowTags : undefined,
        },
        {
          onChunk: (chunk) => {
            // M2: only append when this chunk belongs to the current streaming
            // message — after Stop + immediate resend the aborted stream can
            // still deliver late chunks that must not bleed into the new one.
            if (streamMsgIdRef.current !== tempAsstId) return
            // PERF-FIX: single source of truth = assistantStates; the messages
            // array is only finalized once on done (no per-chunk O(n) map).
            streamContentRef.current += chunk
            updateAssistantState(tempAsstId, s => ({ ...s, content: streamContentRef.current, streamStatus: undefined }))
          },
          onToolStart: (tool, args, callId) => {
            if (streamMsgIdRef.current !== tempAsstId) return
            const tc: ToolCallData = {
              id: callId || genId('tc'), type: tool, label: `${tool}: ${args.path || args.command || args.pattern || ''}`,
              status: 'running', args, result: {}, output: '', duration_ms: 0, timestamp: new Date().toISOString(), error: null,
            }
            updateAssistantState(tempAsstId, s => ({ ...s, toolCalls: [...s.toolCalls, tc], streamStatus: undefined }))
          },
          onToolResult: (toolCall) => {
            if (streamMsgIdRef.current !== tempAsstId) return
            updateAssistantState(tempAsstId, s => ({
              ...s,
              toolCalls: s.toolCalls.map(tc =>
                tc.id === toolCall.id ? { ...tc, ...toolCall } : tc
              ),
            }))
          },
          onStatus: (status, _data) => {
            // M2: a superseded stream (stopped / replaced by a resend) must not
            // recreate assistant state or flip queued/executing on the new turn.
            if (streamMsgIdRef.current !== tempAsstId) return
            if (status === 'overflow_warning') setContextOptimized(true)
            if (status === 'queued') {
              // Round-6 backend: agent concurrency cap emits "queued" before
              // waiting on the semaphore. Show a distinct status instead of
              // "thinking…" which can otherwise sit for the queue timeout.
              updateAssistantState(tempAsstId, s => ({ ...s, streamStatus: 'queued' }))
            }
            if (status === 'executing' || status === 'completed') {
              // Slot acquired — the queued state is over.
              updateAssistantState(tempAsstId, s => ({ ...s, streamStatus: undefined }))
            }
            if (status === 'cancelled') {
              // Server cooperatively cancelled (Stop) — the SSE parser returns
              // here so onDone never fires. Finalize with the *[stopped]*
              // marker; never overwrite the partial content with a normal done.
              abortRef.current = null
              streamMsgIdRef.current = null
              const finalContent = streamContentRef.current
              streamContentRef.current = ''
              setAssistantStates(prev => {
                const next = new Map(prev)
                next.delete(tempAsstId)
                return next
              })
              setMessages(prev => prev.map(m => m.id === tempAsstId
                ? { ...m, content: (finalContent || '') + '\n\n*[stopped]*', status: 'completed' }
                : m))
              setSending(false)
              sendingRef.current = false
            }
          },
          onClarify: (payload) => {
            // M2: ignore clarify events from a superseded stream.
            if (streamMsgIdRef.current !== tempAsstId) return
            // M1: clarify ENDS the turn — the user answers in the next message.
            // Finalize the assistant message (content + metadata carry the block)
            // and RELEASE the send lock so the composer unlocks immediately.
            // The backend may emit clarify without a following done; any later
            // done/error from this stream hits the ownership guard above and is
            // a no-op (the onDone fallback for normal streams stays intact).
            const text = formatClarify(payload)
            streamContentRef.current = text
            streamMsgIdRef.current = null
            setAssistantStates(prev => {
              const next = new Map(prev)
              next.delete(tempAsstId)
              return next
            })
            setMessages(prev => prev.map(m => m.id === tempAsstId
              ? { ...m, content: text, status: 'completed', message_metadata: { ...m.message_metadata, clarify: payload } }
              : m))
            setSending(false)
            sendingRef.current = false
          },
          onDeliverables: (deliverables) => {
            if (streamMsgIdRef.current !== tempAsstId) return
            updateAssistantState(tempAsstId, s => ({ ...s, deliverables }))
          },
          onDone: () => {
            // M2: a stale stream (clarify-finalized, stopped, or superseded by a
            // resend) must not overwrite the current message content or release
            // a send lock it no longer owns.
            if (streamMsgIdRef.current !== tempAsstId) return
            abortRef.current = null
            streamMsgIdRef.current = null
            const finalContent = streamContentRef.current
            streamContentRef.current = ''
            // Clean up the temp streaming state entry (BUG-10)
            setAssistantStates(prev => {
              const next = new Map(prev)
              next.delete(tempAsstId)
              return next
            })
            setMessages(prev => prev.map(m => m.id === tempAsstId ? { ...m, content: finalContent, status: 'completed' } : m))
            setSending(false)
            sendingRef.current = false
            // QA-2445: Don't reload immediately — give API time to commit the response.
            // The useEffect on [activeId, sending] will reload naturally.
          },
          onError: (err) => {
            // M2: an error from a superseded stream must not unlock the composer
            // mid-new-send or clobber the new message.
            if (streamMsgIdRef.current !== tempAsstId) return
            abortRef.current = null
            streamMsgIdRef.current = null
            const finalContent = streamContentRef.current
            streamContentRef.current = ''
            setAssistantStates(prev => {
              const next = new Map(prev)
              next.delete(tempAsstId)
              return next
            })
            setMessages(prev => prev.map(m => m.id === tempAsstId ? { ...m, content: (finalContent || '') + `\n\nError: ${err}`, status: 'completed' } : m))
            setSending(false)
            sendingRef.current = false
          },
        },
      )
      // BUG-11: Stop may have been clicked while executeAgent was still setting
      // up (abortRef was null). Abort now that the cancel fn exists.
      if (stopRequestedRef.current) {
        stopRequestedRef.current = false
        abortRef.current?.()
        abortRef.current = null
        streamMsgIdRef.current = null
        setAssistantStates(prev => {
          const next = new Map(prev)
          next.delete(tempAsstId)
          return next
        })
        const stoppedContent = streamContentRef.current
        streamContentRef.current = ''
        setMessages(prev => prev.map(m => m.id === tempAsstId
          ? { ...m, content: (stoppedContent || '') + '\n\n*[stopped]*', status: 'completed' }
          : m))
        setSending(false)
        sendingRef.current = false
        return
      }
    } catch (err: any) {
      abortRef.current = null
      streamMsgIdRef.current = null
      setAssistantStates(prev => {
        const next = new Map(prev)
        next.delete(tempAsstId)
        return next
      })
      const errMsg = err?.message || String(err)
      setMessages(prev => prev.map(m => m.id === tempAsstId ? { ...m, content: `Failed to send: ${errMsg}`, status: 'completed' } : m))
      setSending(false)
      sendingRef.current = false
    }
  }

  const addAttachments = (files: FileList | File[]) => {
    const all = Array.from(files)
    const accepted = all.filter(file => file.size <= 20 * 1024 * 1024)
    const warnings: string[] = []
    const skipped = all.length - accepted.length
    if (skipped > 0) warnings.push(`Skipped ${skipped} file(s) over 20MB`)
    // Aggregate cap: 10 files × 20MB could balloon into a ~270MB base64 POST.
    // Reject files that would push the total past 50MB at add time.
    const MAX_TOTAL_ATTACHMENT_BYTES = 50 * 1024 * 1024
    let total = attachments.reduce((sum, f) => sum + f.size, 0)
    const kept: File[] = []
    for (const f of accepted) {
      if (total + f.size > MAX_TOTAL_ATTACHMENT_BYTES) {
        warnings.push(`Skipped ${f.name} — total attachment size exceeds 50MB`)
        continue
      }
      total += f.size
      kept.push(f)
    }
    if (kept.length > 0) {
      setAttachments(prev => {
        const next = [...prev, ...kept].slice(0, 10)
        if (next.length > 10) warnings.push('Only the first 10 files are kept')
        return next
      })
    }
    if (warnings.length > 0) setAttachWarnings(warnings)
    if (accepted.some(file => file.type.startsWith('image/')) && !tiers.vision.model) {
      setVisionWarning('Image attached. Select a Vision model before sending.')
    }
  }

  const readAttachment = (file: File): Promise<{ name: string; mime_type: string; data_url: string }> =>
    new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve({ name: file.name, mime_type: file.type || 'application/octet-stream', data_url: String(reader.result || '') })
      reader.onerror = () => reject(reader.error || new Error(`Could not read ${file.name}`))
      reader.readAsDataURL(file)
    })

  // MEDIUM (clarify workspace): pick an absolute folder path and insert it into
  // the composer so the user can send it as their answer. Does NOT auto-send.
  // Clarify answers: stable handler (memo-safe) that submits the Q->A summary
  // straight through handleSend without touching the composer state.
  const handleSendRef = useRef(handleSend)
  handleSendRef.current = handleSend
  const handleClarifyAnswer = useCallback((answerText: string) => {
    void handleSendRef.current(answerText)
  }, [])

  const handlePickWorkspaceFolder = useCallback(async () => {
    if (!window.aic?.selectDirectory) return
    try {
      const dir = await window.aic.selectDirectory()
      if (!dir) return
      // Replace if the input is empty; otherwise append a space-separated path.
      setInput(prev => prev.trim() ? `${prev.trim()} ${dir}` : dir)
    } catch { /* selection cancelled */ }
  }, [])

  // ── Workflow selection handlers ───────────────────────────
  // Selecting a card tags the next message with the workflow type and, [])

  return (
    <div className="flex flex-col h-full min-h-0 overflow-hidden bg-background text-foreground">
      <div className="flex min-h-0 flex-1">
        <Sidebar conversations={conversations} activeId={activeId} onSelect={setActiveId}
          onCreate={handleCreate} onDelete={handleDelete}
          onDuplicate={handleDuplicate} onSearch={q => void loadConversations(q)} />

        <div className="flex min-w-0 min-h-0 flex-1 flex-col">
          {/* Header — minimal */}
          <div className="flex items-center justify-between border-b border-border px-4 py-2.5 shrink-0">
            <div className="flex items-center gap-2">
              <Terminal className="size-3.5 text-primary" />
              <span className="text-[11px] font-semibold tracking-wide">{active?.title || 'Command Center'}</span>
              {active && <span className="text-[9px] text-muted-foreground/50 font-mono">{visibleMessages.length} msgs</span>}
               {(activeProject || projectRoot) && (
                 <span
                   className="flex max-w-[240px] items-center gap-1.5 rounded-md border border-border/50 bg-card/50 px-2 py-0.5"
                   title={activeProject?.repo_path || projectRoot || undefined}
                 >
                   <GitBranch className="size-3 shrink-0 text-primary/70" />
                   <span className="truncate text-[10px] font-medium text-foreground">{activeProject?.name || projectName || 'Project'}</span>
                   <span className="truncate text-[9px] font-mono text-muted-foreground">{activeProject?.repo_path || projectRoot}</span>
                 </span>
               )}
            </div>
          </div>

          {/* Messages */}
          <div
            ref={scrollRef}
            onScroll={e => {
              const el = e.currentTarget
              // Stick-to-bottom: only auto-scroll when already near the bottom.
              // When the user scrolls up, this becomes false and the scroll
              // position is never forced (round-1 behavior, preserved).
              shouldAutoScrollRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < SCROLL_TOLERANCE_PX
              setScrollTop(el.scrollTop)
            }}
            className="flex-1 overflow-y-auto scroll-thin px-4 py-3"
          >
            {contextOptimized && (
              <div className="mx-auto max-w-3xl mb-3 flex items-center gap-2 rounded-md border border-primary/20 bg-primary/5 px-3 py-1.5 text-[11px] text-primary">
                <Check className="size-3 shrink-0" />
                <span>Context refreshed</span>
                <button onClick={() => setContextOptimized(false)} className="ml-auto text-primary/60 hover:text-primary" aria-label="Dismiss context optimization notice">
                  <X className="size-3" />
                </button>
              </div>
            )}
            {streamingBackground ? (
              <div className="grid h-full place-items-center">
                <div className="text-center space-y-2">
                  <Loader2 className="mx-auto size-4 animate-spin text-primary/50" />
                  <p className="text-xs text-muted-foreground/60">Still streaming in background…</p>
                </div>
              </div>
            ) : visibleMessages.length === 0 ? (
              <div className="grid h-full place-items-center">
                <div className="text-center space-y-3">
                  <div className="mx-auto grid size-10 place-items-center rounded-xl bg-muted/30">
                    <Terminal className="size-5 text-muted-foreground/40" />
                  </div>
                  <p className="text-xs text-muted-foreground/60">
                    {active ? `describe what to do` : 'select or create a session'}
                  </p>
                </div>
              </div>
            ) : (
              <div className="max-w-3xl mx-auto">
                {/* Virtual window (round-8): spacers preserve the total scroll
                    height; only the visible slice of messages is rendered. */}
                <div style={{ height: listWindow.spacerTop }} aria-hidden="true" />
                <div ref={sliceRef}>
                  {messageSlice.map(m => (
                    <MessageRow key={m.id} message={m} state={m.role === 'assistant' ? assistantStates.get(m.id) : undefined} onPickWorkspaceFolder={handlePickWorkspaceFolder} onSubmitAnswer={handleClarifyAnswer} />
                  ))}
                </div>
                <div style={{ height: listWindow.spacerBottom }} aria-hidden="true" />
              </div>
            )}
          </div>



          {/* Composer — QA-2437 BUG-2: everything in ONE horizontal row, textarea below */}
          <div className="border-t border-border/60 px-4 py-3.5 shrink-0 bg-card/20 backdrop-blur-sm">
            <div className="w-full max-w-none">
              {/* IMPROVED SINGLE-LINE TOOLBAR DESIGN: Modern polish, gradients, shadows, buttons inline */}
              <div className="mb-2 flex items-center gap-3 overflow-x-auto overflow-y-hidden pb-1.5" style={{ scrollbarWidth: 'none' }}>
                
                {/* LEFT: Context Box + Progress Bar */}
                <div className="flex items-center gap-3 shrink-0" title="Context usage indicator">
                  
                  {/* Context Indicator Card */}
                  <div className="group flex items-center gap-2 rounded-lg bg-gradient-to-br from-primary/10 to-primary/5 px-3 py-2 shadow-sm transition-all hover:shadow-md hover:from-primary/15 hover:to-primary/8 border border-primary/10 hover:border-primary/20 cursor-default">
                    <span className="text-[9px] font-extrabold tracking-widest text-primary drop-shadow-sm">CONTEXT</span>
                    <span className="font-mono text-[9px] font-bold tabular-nums text-primary">{totalTokens > 0 ? totalTokens.toLocaleString() : '?'}</span>
                    {contextWindow > 0 && (
                      <>
                        <span className="text-[7px] font-semibold text-muted-foreground/60">/</span>
                        <span className="font-mono text-[9px] font-bold tabular-nums text-muted-foreground/80">{contextWindow.toLocaleString()}</span>
                      </>
                    )}
                  </div>

                  {/* Enhanced Progress Bar */}
                  <div className="relative h-2 w-40 shrink-0 overflow-hidden rounded-full bg-gradient-to-b from-muted/50 to-muted/30 shadow-inner border border-muted/20" title="Token usage progress">
                    <div className={cn("absolute inset-0 h-full rounded-full transition-all duration-500 ease-out", contextBarColor)} 
                         style={{ width: `${contextPct}%`, boxShadow: 'inset 0 -1px 3px rgba(0,0,0,0.2), 0 0 12px rgba(0,0,0,0.1)' }} />
                  </div>
                </div>

                {/* DIVIDER LINE */}
                <div className="mx-1.5 h-6 w-px shrink-0 bg-gradient-to-b from-transparent via-muted/40 to-transparent"></div>

                {/* MIDDLE: Tier Selectors (all 4 tiers inline) */}
                <div className="flex min-w-0 flex-nowrap items-center gap-2 overflow-x-auto overflow-y-hidden" style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
                  {ENGINE_TIERS.map(tier => {
                    const sel = tiers[tier]
                    const providerModels = (providers.find(p => p.name === sel.provider)?.models || []).filter(m => tier !== 'vision' || m.capabilities?.vision)
                    return (
                      <div key={tier} className="group relative flex items-center gap-1.5 rounded-lg bg-gradient-to-br from-card/60 to-card/40 px-2.5 py-1.5 shadow-sm transition-all hover:from-card/80 hover:to-card/60 hover:shadow-md border border-border/30 hover:border-border/50 cursor-default">
                        
                        {/* Glow effect on hover */}
                        <div className={cn("absolute inset-0 rounded-lg opacity-0 transition-opacity group-hover:opacity-20", TIER_LABEL_COLORS[tier].replace('text-', 'bg-'))}></div>
                        
                        {/* Tier Label */}
                        <span className={cn("relative z-10 text-[8px] font-extrabold tracking-widest", TIER_LABEL_COLORS[tier])}>
                          {tier.toUpperCase()}
                        </span>
                        
                        {/* Provider Dropdown */}
                        <select value={sel.provider} onChange={e => handleTierChange(tier, { provider: e.target.value, model: '' })}
                          aria-label={`${tier} provider`}
                          className="relative z-10 block cursor-pointer rounded bg-transparent px-1 py-0.5 text-[8px] font-medium text-foreground outline-none focus:text-primary [&::-ms-expand]:hidden [&::-webkit-appearance:none] [&::-webkit-slider-thumb]:appearance-none">
                          <option value="">—</option>
                          {providers.map(p => <option key={p.id} value={p.name}>{p.name}</option>)}
                        </select>
                        
                        {/* Model Dropdown */}
                        <select value={sel.model} onChange={e => handleTierChange(tier, { model: e.target.value })}
                          aria-label={`${tier} model`}
                          className="relative z-10 block cursor-pointer rounded bg-transparent px-1 py-0.5 font-mono text-[8px] font-medium text-foreground/90 outline-none focus:text-primary [&::-ms-expand]:hidden [&::-webkit-appearance:none]">
                          <option value="">—</option>
                          {providerModels.map(m => <option key={m.id} value={m.id}>{m.name || m.id}</option>)}
                        </select>
                      </div>
                    )
                  })}
                </div>

                {/* DIVIDER LINE */}
                <div className="mx-1.5 h-6 w-px shrink-0 bg-gradient-to-b from-transparent via-muted/40 to-transparent"></div>

                {/* RIGHT: Fetch & Compact Buttons (pill-style, inline) */}
                <div className="flex items-center gap-2 shrink-0">
                  <button onClick={() => void handleFetchModels()} disabled={fetchingModels}
                    className="group relative inline-flex items-center gap-2 rounded-xl border border-border/40 bg-gradient-to-br from-card/50 to-card/30 px-3.5 py-2 text-[9px] font-bold tracking-wide text-muted-foreground transition-all hover:border-primary/30 hover:from-primary/10 hover:to-primary/5 hover:text-primary hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-card/50 disabled:hover:text-muted-foreground overflow-hidden">
                    
                    {/* Background shine effect */}
                    <div className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/5 to-transparent transition-transform group-hover:animate-[shimmer_1s_infinite]"></div>
                    
                    {/* Icon spinner when fetching */}
                    {fetchingModels ? (
                      <Loader2 className="relative z-10 size-3 animate-spin" />
                    ) : (
                      <svg className="relative z-10 size-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                    )}
                    
                    <span className="relative z-10 font-semibold">FETCH</span>
                  </button>

                  <button onClick={() => void handleCompact()} disabled={compacting || sending}
                    className="group relative inline-flex items-center gap-2 rounded-xl border border-border/40 bg-gradient-to-br from-card/50 to-card/30 px-3.5 py-2 text-[9px] font-bold tracking-wide text-muted-foreground transition-all hover:border-primary/30 hover:from-primary/10 hover:to-primary/5 hover:text-primary hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-card/50 disabled:hover:text-muted-foreground overflow-hidden">
                    
                    {/* Background shine effect */}
                    <div className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/5 to-transparent transition-transform group-hover:animate-[shimmer_1s_infinite]"></div>
                    
                    {/* Icon spinner when compacting */}
                    {compacting ? (
                      <Loader2 className="relative z-10 size-3 animate-spin" />
                    ) : (
                      <svg className="relative z-10 size-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M19 14l-7 7m0 0l-7-7m7 7V3" /></svg>
                    )}
                    
                    <span className="relative z-10 font-semibold">COMPACT</span>
                  </button>
                </div>

              </div>

              {visionWarning && <p className="mb-2 text-[10px] text-warning">{visionWarning}</p>}
              {attachWarnings.length > 0 && (
                <div className="mb-2 flex items-center gap-2">
                  {attachWarnings.map((w, i) => (
                    <span key={i} className="text-[10px] text-warning">{w}</span>
                  ))}
                  <button onClick={() => setAttachWarnings([])} className="text-[10px] text-muted-foreground/60 hover:text-foreground" aria-label="Dismiss warnings">✕</button>
                </div>
              )}
              {attachments.length > 0 && (
                <div className="mb-2 flex flex-wrap gap-1.5">
                  {attachments.map((file, index) => (
                    <span key={`${file.name}-${index}`} className="inline-flex items-center gap-1 rounded border border-info/30 bg-info/10 px-2 py-1 text-[10px] text-info">
                      {file.name}
                      <button onClick={() => setAttachments(prev => prev.filter((_, i) => i !== index))} className="text-info/60 hover:text-info" aria-label={`Remove ${file.name}`}><X className="size-3" /></button>
                    </span>
                  ))}
                </div>
              )}
              {/* Row 2 — input + file picker + send/stop */}
              <div
                onDragOver={e => { e.preventDefault(); setDragActive(true) }}
                onDragLeave={() => setDragActive(false)}
                onDrop={e => { e.preventDefault(); setDragActive(false); addAttachments(e.dataTransfer.files) }}
                className={cn("flex items-end gap-2 rounded-lg border bg-card/60 px-3 py-2 focus-within:border-primary/40", dragActive ? "border-info bg-info/5" : "border-border/60")}
              >
                <span className="mb-1 shrink-0 font-mono text-xs font-bold text-primary/40 select-none">❯</span>
                <textarea ref={textareaRef} value={input} onChange={e => setInput(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing && e.keyCode !== 229) {
                      e.preventDefault(); void handleSend()
                    }
                  }}
                  disabled={false} rows={1}
                  placeholder={activeId ? `describe what to build or drop files…` : 'Type a message to start…'}
                  className="max-h-[160px] min-h-[24px] flex-1 resize-none bg-transparent py-0.5 text-[13px] leading-relaxed outline-none placeholder:text-muted-foreground/40 disabled:opacity-30" />
                <input id="chat-file-input" type="file" multiple className="hidden" onChange={e => { if (e.target.files) addAttachments(e.target.files); e.currentTarget.value = '' }} />
                <button onClick={() => document.getElementById('chat-file-input')?.click()} className="mb-0.5 grid size-6 shrink-0 place-items-center rounded-md text-muted-foreground hover:bg-muted/50 hover:text-foreground" aria-label="Attach files" title="Attach files">
                  <Paperclip className="size-3" />
                </button>
                {/* QA-2437 BUG-4: send button doubles as stop (abort) while generating */}
                <button onClick={() => sending ? handleStop() : void handleSend()}
                  aria-label={sending ? 'Stop generation' : 'Send message'}
                  title={sending ? 'Stop generation' : 'Send message'}
                  className={cn("mb-0.5 grid size-6 shrink-0 place-items-center rounded-md transition-colors",
                    sending ? "bg-destructive/15 text-destructive hover:bg-destructive/25" : "bg-primary/15 text-primary hover:bg-primary/25"
                  )}>
                  {sending ? <Square className="size-2.5 fill-current" /> : <Send className="size-3" />}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Explorer Panel — right side */}
        {explorerOpen && (
          <div className="w-60 lg:w-72 shrink-0 border-l border-border bg-sidebar/50 flex flex-col">
            <div className="flex items-center justify-between border-b border-border px-3 py-2">
              <div className="flex items-center gap-1.5">
                <FolderTree className="size-3.5 text-primary" />
                <span className="text-[10px] font-semibold tracking-wide">Explorer</span>
              </div>
              <button onClick={() => setExplorerOpen(false)} className="text-muted-foreground/60 hover:text-foreground" aria-label="Close explorer">
                <X className="size-3" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto scroll-thin flex flex-col min-h-0">
              {activeProject?.repo_path || projectRoot ? (
                <div className="p-2 space-y-2">
                  {/* Workspace / project selector */}
                  <ProjectPicker
                    onProjectChange={(p) => { setActiveProject(p); onProjectChange?.(p) }}
                    onActiveChange={setActiveProject}
                    refreshKey={projectRefreshKey}
                    fallbackLabel={projectName}
                    fallbackPath={projectRoot}
                  />
                  {/* File tree search */}
                  <div className="flex items-center gap-1.5 rounded-md border border-border/50 bg-card/50 px-2 py-1 focus-within:border-primary/40">
                    <Search className="size-2.5 text-muted-foreground/60" />
                    <input
                      value={fileTreeFilter}
                      onChange={e => setFileTreeFilter(e.target.value)}
                      placeholder="Filter files…"
                      className="w-full bg-transparent text-[10px] outline-none placeholder:text-muted-foreground/40"
                    />
                    {fileTreeFilter && (
                      <button onClick={() => setFileTreeFilter('')} className="text-muted-foreground/50 hover:text-foreground" aria-label="Clear file filter">
                        <X className="size-2.5" />
                      </button>
                    )}
                  </div>
                  {/* File tree */}
                  <div className="border rounded-md border-border/50 bg-card/60 -mx-0.5">
                    <FileTree
                      rootPath={activeProject?.repo_path || projectRoot || ''}
                      rootLabel={activeProject?.name || projectName || undefined}
                      onFileSelect={(path) => window.aic?.openPath?.(path)}
                      filter={fileTreeFilter}
                    />
                  </div>
                </div>
              ) : (
                <div className="flex flex-1 flex-col items-center justify-center p-4 text-center space-y-2">
                  <div className="grid size-8 place-items-center rounded-lg bg-muted/30">
                    <FolderTree className="size-4 text-muted-foreground/40" />
                  </div>
                  <p className="text-[11px] text-muted-foreground/70">No workspace selected</p>
                  <p className="text-[10px] text-muted-foreground/50">Pick a project folder to see its files here.</p>
                  <ProjectPicker
                    onProjectChange={(p) => { setActiveProject(p); onProjectChange?.(p) }}
                    onActiveChange={setActiveProject}
                    refreshKey={projectRefreshKey}
                    fallbackLabel={projectName}
                    fallbackPath={projectRoot}
                  />
                </div>
              )}
            </div>
          </div>
        )}

        {!explorerOpen && (
          <button onClick={() => setExplorerOpen(true)} aria-label="Open explorer"
            className="absolute right-0 top-12 z-10 rounded-l-md border border-border bg-sidebar p-1 text-muted-foreground/60 hover:text-foreground">
            <PanelRight className="size-3.5" />
          </button>
        )}
      </div>
    </div>
  )
}
