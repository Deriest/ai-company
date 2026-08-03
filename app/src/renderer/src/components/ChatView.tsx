/**
 * ChatView — OpenCode Desktop-style Command Center.
 *
 * Layout: Sidebar | Chat Area (with inline tool panels) | Status Bar
 *
 * Tool panels are ALWAYS VISIBLE (not collapsible) — matching OpenCode Desktop.
 * Sidebar is compact — session name + time.
 * Status bar shows model, tokens, connection.
 */
import { useEffect, useMemo, useRef, useState, useCallback } from 'react'
import {
  Send, Plus, Search, Trash2,
  FileText, Terminal, Eye, PenLine, Play, Copy, Check,
  Pin, Loader2, Bot, GitBranch, X, PanelRight, Square, Paperclip,
} from 'lucide-react'
import { cn } from '../lib/utils'
import { conversationsApi, type ConversationRecord, type MessageRecord } from '../lib/api/conversations'
import { chatApi, type ToolCallData, type FileDiffData, type ShellOutputData, type TodoItemData, type DeliverableSummary } from '../lib/api/chat'
import { providersApi, type ProviderRecord } from '../lib/api/providers'
import { providerManageApi } from '../lib/api/provider_manage'
import { resolveDefaultModelId, type ProviderLike } from '../lib/providerModel'

// ── Types ────────────────────────────────────────────────

interface AssistantMessageState {
  content: string
  toolCalls: ToolCallData[]
  fileDiffs: FileDiffData[]
  shellOutputs: Map<string, ShellOutputData>
  todos: TodoItemData[]
  filesModified: string[]
  isStreaming: boolean
  metadata?: Record<string, any>
  deliverables?: DeliverableSummary
}

type AgentMode = 'build' | 'plan'

const AGENT_WORKER_MAP: Record<AgentMode, string> = {
  build: 'backend',
  plan: 'research',
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
    else if (first.type === 'link') { nodes.push(<a key={key++} href={first.match[2]} className="text-primary underline" target="_blank" rel="noreferrer">{first.match[1]}</a>); remaining = remaining.slice(first.index + first.match[0].length) }
  }
  return <>{nodes}</>
}

function highlightCode(code: string, language: string): string {
  if (['js', 'ts', 'jsx', 'tsx', 'javascript', 'typescript'].includes(language)) {
    return code
      .replace(/\b(const|let|var|function|return|import|export|from|class|extends|if|else|for|while|do|switch|case|break|continue|new|this|typeof|instanceof|async|await|try|catch|throw|finally|yield|of|in)\b/g, '<span class="text-purple-400">$1</span>')
      .replace(/\b(true|false|null|undefined|NaN|Infinity)\b/g, '<span class="text-orange-400">$1</span>')
      .replace(/(["'`])(?:(?!\1).)*?\1/g, '<span class="text-emerald-400">$&</span>')
      .replace(/\/\/.*$/gm, '<span class="text-muted-foreground/50">$&</span>')
      .replace(/\b(\d+)\b/g, '<span class="text-orange-400">$1</span>')
  }
  if (['py', 'python'].includes(language)) {
    return code
      .replace(/\b(def|class|import|from|return|if|elif|else|for|while|try|except|finally|with|as|yield|lambda|pass|break|continue|raise|global|nonlocal|and|or|not|is|in|True|False|None|async|await|self)\b/g, '<span class="text-purple-400">$1</span>')
      .replace(/(#.*$)/gm, '<span class="text-muted-foreground/50">$1</span>')
      .replace(/(["'])(?:(?!\1).)*?\1/g, '<span class="text-emerald-400">$&</span>')
      .replace(/\b(\d+)\b/g, '<span class="text-orange-400">$1</span>')
  }
  if (['json'].includes(language)) {
    return code
      .replace(/(["'])(?:(?!\1).)*?\1/g, '<span class="text-emerald-400">$&</span>')
      .replace(/\b(\d+\.?\d*)\b/g, '<span class="text-orange-400">$1</span>')
      .replace(/\b(true|false|null)\b/g, '<span class="text-orange-400">$1</span>')
  }
  return code
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

function ToolPanelInline({ toolCall }: { toolCall: ToolCallData }) {
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
}

function FileDiffInline({ diff }: { diff: FileDiffData }) {
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
}

function ShellOutputInline({ command, outputs }: { command: string; outputs: ShellOutputData[] }) {
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
}

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
            className="rounded px-2 py-0.5 text-[9px] font-medium bg-primary/15 text-primary hover:bg-primary/25"
            onClick={() => {/* placeholder for download all */}}
          >
            Download All
          </button>
          <button
            className="rounded px-2 py-0.5 text-[9px] font-medium bg-success/15 text-success hover:bg-success/25"
            onClick={() => {/* placeholder for approve */}}
          >
            Approve
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

function MessageRow({ message, state }: { message: MessageRecord; state?: AssistantMessageState }) {
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
          {state?.isStreaming && !message.content ? (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="size-3 animate-spin" />
              <span>thinking…</span>
            </div>
          ) : (
            <MarkdownContent content={message.content} />
          )}
          {state?.isStreaming && message.content && (
            <span className="inline-block h-3.5 w-1 animate-pulse bg-primary/60 ml-0.5 align-middle" />
          )}
        </div>
      </div>
    </div>
  )
}

// ── Sidebar (compact) ────────────────────────────────────

function Sidebar({ conversations, activeId, onSelect, onCreate, onDelete, onArchive, onDuplicate, onSearch }: {
  conversations: ConversationRecord[]; activeId: string | null;
  onSelect: (id: string) => void; onCreate: () => void;
  onDelete: (id: string, e: React.MouseEvent) => void; onArchive: (id: string, e: React.MouseEvent) => void;
  onDuplicate: (id: string, e: React.MouseEvent) => void; onSearch: (q: string) => void;
}) {
  const [query, setQuery] = useState('')
  useEffect(() => { onSearch(query) }, [query])

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

export function ChatView({ health = 'unknown', currentProvider = null }: { health?: 'ok' | 'bad' | 'unknown'; currentProvider?: ProviderLike | null }) {
  const [conversations, setConversations] = useState<ConversationRecord[]>([])
  const [activeId, setActiveId] = useState<string | null>(() => {
    try { return sessionStorage.getItem('aic-ade-active-conversation') }
    catch { return null }
  })
  const [messages, setMessages] = useState<MessageRecord[]>([])
  const [input, setInput] = useState('')
  const [attachments, setAttachments] = useState<File[]>([])
  const [dragActive, setDragActive] = useState(false)
  const [visionWarning, setVisionWarning] = useState('')
  const [sending, setSending] = useState(false)
  const [agentMode, setAgentMode] = useState<AgentMode>('build')
  const [assistantStates, setAssistantStates] = useState<Map<string, AssistantMessageState>>(new Map())
  const [contextOptimized, setContextOptimized] = useState(false)
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const [providers, setProviders] = useState<ProviderRecord[]>([])
  const [tiers, setTiers] = useState<Record<EngineTier, TierSelection>>({
    thinker: { provider: '', model: '' },
    crafter: { provider: '', model: '' },
    sprinter: { provider: '', model: '' },
    vision: { provider: '', model: '' },
  })
  const [fetchingModels, setFetchingModels] = useState(false)
  const [compacting, setCompacting] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const abortRef = useRef<(() => void) | null>(null)
  const streamMsgIdRef = useRef<string | null>(null)
  const activeIdRef = useRef(activeId)
  const sendingRef = useRef(sending)
  const messagesRef = useRef(messages)
  const loadRequestRef = useRef(0)
  activeIdRef.current = activeId
  sendingRef.current = sending
  messagesRef.current = messages

  const active = useMemo(() => conversations.find(c => c.id === activeId) ?? null, [conversations, activeId])

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
        const all = await conversationsApi.list()
        setConversations(all.filter(c => ids.includes(c.id)))
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
      const loaded = await conversationsApi.listMessages(convId)
      // A slow response from an older request must never overwrite a newer
      // conversation or the local stream currently being displayed.
      if (requestId !== loadRequestRef.current || activeIdRef.current !== convId) return
      // Keep optimistic messages until matching persisted records arrive. This
      // remains necessary after onDone because /chat/execute commits at the end
      // of the pipeline and a delayed GET can still observe the old snapshot.
      const serverKeys = new Set(loaded.map(m => `${m.role}\u0000${m.content}`))
      const localOnly = messagesRef.current.filter(m =>
        m.conversation_id === convId && m.id.startsWith('temp-') &&
        !serverKeys.has(`${m.role}\u0000${m.content}`)
      )
      // Stable ordering: backend assigns user+assistant the same created_at,
      // so tiebreak by role (user above its assistant response).
      // Normalize timestamps: Python isoformat ends with +00:00, JS ends with Z.
      // Without normalization, localeCompare sorts all +00:00 before all Z
      // regardless of actual time, causing reversed message order after reload.
      const normTs = (s: string) => s.replace(/\+00:00$/, 'Z')
      const roleRank = (m: MessageRecord) => m.role === 'user' ? 0 : 1
      setMessages([...loaded, ...localOnly].sort((a, b) =>
        normTs(a.created_at).localeCompare(normTs(b.created_at)) || roleRank(a) - roleRank(b)
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
    return () => { abortRef.current?.(); abortRef.current = null }
  }, [])
  useEffect(() => { if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight }, [messages, assistantStates])
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

  // ── Engine tier config (THINKER/CRAFTER/SPRINTER) ──────
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [envCfg, pList] = await Promise.all([
          providerManageApi.getEnvConfig(),
          providersApi.list(),
        ])
        if (cancelled) return
        setProviders(pList)
        let saved: Record<string, string> = {}
        try { saved = JSON.parse(localStorage.getItem('aic-ade-engine-tiers') || '{}') } catch { /* ignore */ }
        try {
          const ipcCfg = await window.aic?.storeGet?.('engineConfig') as Record<string, string> | null
          if (ipcCfg) saved = { ...saved, ...ipcCfg }
        } catch { /* ignore */ }
        if (cancelled) return
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
    })()
    return () => { cancelled = true }
  }, [])

  const handleTierChange = useCallback((tier: EngineTier, patch: Partial<TierSelection>) => {
    const next: Record<EngineTier, TierSelection> = { ...tiers, [tier]: { ...tiers[tier], ...patch } }
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
    // Apply to engine so the agent runner picks up the new tier models
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
  }, [tiers, providers])

  const handleFetchModels = useCallback(async () => {
    if (fetchingModels) return
    setFetchingModels(true)
    try {
      const current = await providersApi.list()
      const updated: ProviderRecord[] = []
      for (const p of current) {
        try { updated.push(await providersApi.fetchModelsAndUpdate(p.id, p.endpoint)) }
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
    abortRef.current?.()
    abortRef.current = null
    const msgId = streamMsgIdRef.current
    streamMsgIdRef.current = null
    if (msgId) {
      updateAssistantState(msgId, s => ({ ...s, isStreaming: false }))
      setMessages(prev => prev.map(m => m.id === msgId
        ? { ...m, content: (m.content || '') + '\n\n*[stopped]*', status: 'completed' }
        : m))
    }
    setSending(false)
    // QA-2445: Don't reload — useEffect handles it
  }, [activeId, updateAssistantState])

  const handleCreate = async () => {
    try {
      const c = await conversationsApi.create('New Session')
      setConversations(prev => [c, ...prev])
      setActiveId(c.id)
    } catch (e) { console.error(e) }
  }

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await conversationsApi.delete(id)
      setConversations(prev => prev.filter(c => c.id !== id))
      if (activeId === id) setActiveId(conversations.find(c => c.id !== id)?.id || null)
    } catch (e) { console.error(e) }
  }

  const handleArchive = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await conversationsApi.update(id, { is_archived: true })
      setConversations(prev => prev.filter(c => c.id !== id))
      if (activeId === id) setActiveId(conversations.find(c => c.id !== id)?.id || null)
    } catch (e) { console.error(e) }
  }

  const handleDuplicate = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      const dup = await conversationsApi.duplicate(id)
      setConversations(prev => [dup, ...prev])
      setActiveId(dup.id)
    } catch (e) { console.error(e) }
  }

  const handleSend = async () => {
    if ((!input.trim() && attachments.length === 0) || sending) return
    const hasImages = attachments.some(file => file.type.startsWith('image/'))
    const visionProvider = providers.find(provider => provider.name === tiers.vision.provider)
    const visionModel = visionProvider?.models.find(model => model.id === tiers.vision.model)
    if (hasImages && (!tiers.vision.model || visionModel?.capabilities.vision !== true)) {
      setVisionWarning('The selected Vision model does not support images. Select a model marked Vision in the Vision tier.')
      return
    }
    const text = input.trim()
    const attachmentText = attachments.map(file => `[Attached file: ${file.name}]`).join('\n')
    const promptText = [text, attachmentText].filter(Boolean).join('\n')
    let attachmentPayload: { name: string; mime_type: string; data_url: string }[] = []
    try {
      attachmentPayload = await Promise.all(attachments.map(readAttachment))
    } catch (error) {
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
        const conv = await conversationsApi.create(promptText.slice(0, 60))
        setConversations(prev => [conv, ...prev])
        convId = conv.id
        setActiveId(convId)
      } catch (e: any) {
        const errMsg = e?.message || String(e)
        const tempErr: MessageRecord = {
          id: 'err-' + Date.now(), conversation_id: '', role: 'assistant', content: `Failed to create session: ${errMsg}`,
          status: 'completed', created_at: new Date().toISOString(), updated_at: new Date().toISOString(), attachments: [],
        }
        setMessages(prev => [...prev, tempErr])
        setSending(false)
        return
      }
    }

    const tempUserMsg: MessageRecord = {
      id: 'temp-' + Date.now(), conversation_id: convId, role: 'user', content: promptText,
      status: 'completed', created_at: new Date().toISOString(), updated_at: new Date().toISOString(), attachments: [],
    }
    const tempAsstId = 'temp-ast-' + Date.now()
    const tempAsstMsg: MessageRecord = {
      id: tempAsstId, conversation_id: convId, role: 'assistant', content: '',
      status: 'streaming', created_at: new Date().toISOString(), updated_at: new Date().toISOString(), attachments: [],
    }
    setMessages(prev => [...prev, tempUserMsg, tempAsstMsg])
    setAssistantStates(prev => {
      const next = new Map(prev)
      next.set(tempAsstId, { content: '', toolCalls: [], fileDiffs: [], shellOutputs: new Map(), todos: [], filesModified: [], isStreaming: true })
      return next
    })
    streamMsgIdRef.current = tempAsstId

    try {
      // Use executeAgent — goes through ConversationEngine → Dispatcher → Orchestrator → Workers
      // executeAgent returns an AbortController-backed cancel fn (QA-2437 BUG-4)
      abortRef.current = await chatApi.executeAgent(
        {
          conversation_id: convId,
          messages: [{ role: 'user', content: promptText }],
          worker_role: AGENT_WORKER_MAP[agentMode],
          model_tier: hasImages ? 'vision' : 'crafter',
          attachments: attachmentPayload,
        },
        {
          onChunk: (chunk) => {
            updateAssistantState(tempAsstId, s => ({ ...s, content: s.content + chunk }))
            setMessages(prev => prev.map(m => m.id === tempAsstId ? { ...m, content: (m.content || '') + chunk } : m))
          },
          onToolStart: (tool, args, callId) => {
            const tc: ToolCallData = {
              id: callId || 'tc-' + Date.now(), type: tool, label: `${tool}: ${args.path || args.command || args.pattern || ''}`,
              status: 'running', args, result: {}, output: '', duration_ms: 0, timestamp: new Date().toISOString(), error: null,
            }
            updateAssistantState(tempAsstId, s => ({ ...s, toolCalls: [...s.toolCalls, tc] }))
          },
          onToolResult: (toolCall) => {
            updateAssistantState(tempAsstId, s => ({
              ...s,
              toolCalls: s.toolCalls.map(tc =>
                tc.id === toolCall.id ? { ...tc, ...toolCall } : tc
              ),
            }))
          },
          onStatus: (status, _data) => {
            if (status === 'overflow_warning') setContextOptimized(true)
          },
          onDeliverables: (deliverables) => {
            updateAssistantState(tempAsstId, s => ({ ...s, deliverables }))
          },
          onDone: () => {
            abortRef.current = null
            streamMsgIdRef.current = null
            updateAssistantState(tempAsstId, s => ({ ...s, isStreaming: false }))
            setMessages(prev => prev.map(m => m.id === tempAsstId ? { ...m, status: 'completed' } : m))
            setSending(false)
            // QA-2445: Don't reload immediately — give API time to commit the response.
            // The useEffect on [activeId, sending] will reload naturally.
          },
          onError: (err) => {
            abortRef.current = null
            streamMsgIdRef.current = null
            updateAssistantState(tempAsstId, s => ({ ...s, isStreaming: false, content: s.content || `Error: ${err}` }))
            setMessages(prev => prev.map(m => m.id === tempAsstId ? { ...m, content: (m.content || '') + `\n\nError: ${err}`, status: 'completed' } : m))
            setSending(false)
          },
        },
      )
    } catch (err: any) {
      abortRef.current = null
      streamMsgIdRef.current = null
      const errMsg = err?.message || String(err)
      setMessages(prev => prev.map(m => m.id === tempAsstId ? { ...m, content: `Failed to send: ${errMsg}`, status: 'completed' } : m))
      setSending(false)
    }
  }

  const addAttachments = (files: FileList | File[]) => {
    const accepted = Array.from(files).filter(file => file.size <= 20 * 1024 * 1024)
    setAttachments(prev => [...prev, ...accepted].slice(0, 10))
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

  return (
    <div className="flex flex-col absolute inset-0">
      <div className="flex min-h-0 flex-1">
        <Sidebar conversations={conversations} activeId={activeId} onSelect={setActiveId}
          onCreate={handleCreate} onDelete={handleDelete} onArchive={handleArchive}
          onDuplicate={handleDuplicate} onSearch={q => void loadConversations(q)} />

        <div className="flex min-w-0 min-h-0 flex-1 flex-col">
          {/* Header — minimal */}
          <div className="flex items-center justify-between border-b border-border px-4 py-2.5 shrink-0">
            <div className="flex items-center gap-2">
              <Terminal className="size-3.5 text-primary" />
              <span className="text-[11px] font-semibold tracking-wide">{active?.title || 'Command Center'}</span>
              {active && <span className="text-[9px] text-muted-foreground/50 font-mono">{messages.length} msgs</span>}
            </div>
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto scroll-thin px-4 py-3">
            {contextOptimized && (
              <div className="mx-auto max-w-3xl mb-3 flex items-center gap-2 rounded-md border border-primary/20 bg-primary/5 px-3 py-1.5 text-[11px] text-primary">
                <Loader2 className="size-3 animate-spin" />
                <span>Context optimized — older messages summarized</span>
                <button onClick={() => setContextOptimized(false)} className="ml-auto text-primary/60 hover:text-primary" aria-label="Dismiss context optimization notice">
                  <X className="size-3" />
                </button>
              </div>
            )}
            {messages.length === 0 ? (
              <div className="grid h-full place-items-center">
                <div className="text-center space-y-3">
                  <div className="mx-auto grid size-10 place-items-center rounded-xl bg-muted/30">
                    <Terminal className="size-5 text-muted-foreground/40" />
                  </div>
                  <p className="text-xs text-muted-foreground/60">
                    {active ? `${agentMode} mode · describe what to do` : 'select or create a session'}
                  </p>
                </div>
              </div>
            ) : (
              <div className="max-w-3xl mx-auto">
                {messages.map(m => (
                  <MessageRow key={m.id} message={m} state={m.role === 'assistant' ? assistantStates.get(m.id) : undefined} />
                ))}
              </div>
            )}
          </div>

          {/* Status bar */}
          <div className="flex items-center justify-between border-t border-border bg-sidebar px-4 py-1.5 text-[9px] text-muted-foreground/50 shrink-0">
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1">
                <span className={cn("size-1.5 rounded-full", health === 'ok' ? 'bg-success' : 'bg-destructive')} />
                {health === 'ok' ? 'connected' : health === 'bad' ? 'offline' : 'checking…'}
              </span>
              <span className="font-mono">{agentMode} agent</span>
            </div>
            <div className="flex items-center gap-3">
              <button onClick={() => setInspectorOpen(!inspectorOpen)} className="hover:text-foreground flex items-center gap-1" aria-label={inspectorOpen ? "Hide inspector" : "Show inspector"}>
                <PanelRight className="size-3" />
                {inspectorOpen ? 'inspector' : ''}
              </button>
              <span className="font-mono">Hermes</span>
            </div>
          </div>

          {/* Composer — QA-2437 BUG-2: everything in ONE horizontal row, textarea below */}
          <div className="border-t border-border px-4 py-3 shrink-0">
            <div className="mx-auto max-w-5xl">
              {/* Row 1 — mode | context usage | progress | tier selectors | actions */}
              <div className="mb-2 flex items-center gap-2 overflow-x-auto scroll-thin pb-0.5">
                {/* BUILD | PLAN */}
                <div className="flex shrink-0 items-center gap-0.5 rounded-md border border-border/50 p-0.5">
                  {(['build', 'plan'] as AgentMode[]).map(mode => (
                    <button key={mode} onClick={() => setAgentMode(mode)}
                      className={cn("rounded px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide transition-colors",
                        agentMode === mode ? "bg-primary/15 text-primary" : "text-muted-foreground/60 hover:text-foreground"
                      )}>
                      {mode}
                    </button>
                  ))}
                </div>

                {/* Context usage — QA-2437 BUG-1: token_count sum, '?' fallback; BUG-3: primary-colored label */}
                <div className="flex shrink-0 items-center gap-1.5">
                  <span className="text-[10px] font-semibold text-primary">Context</span>
                  <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
                    {totalTokens > 0 ? totalTokens.toLocaleString() : '?'}{contextWindow > 0 ? ` / ${contextWindow.toLocaleString()}` : ''}
                  </span>
                </div>

                {/* Progress bar — QA-2437 BUG-3: green < 50%, yellow 50-80%, red > 80% */}
                <div className="h-1.5 min-w-6 flex-1 overflow-hidden rounded-full bg-muted/40">
                  <div className={cn("h-full rounded-full transition-all", contextBarColor)} style={{ width: `${contextPct}%` }} />
                </div>

                {/* THINKER / CRAFTER / SPRINTER / VISION tier selectors */}
                {ENGINE_TIERS.map(tier => {
                  const sel = tiers[tier]
                  const providerModels = providers.find(p => p.name === sel.provider)?.models || []
                  return (
                    <div key={tier} className="flex shrink-0 items-center gap-1">
                      <span className={cn("text-[8px] font-bold tracking-wide", TIER_LABEL_COLORS[tier])}>{tier.toUpperCase()}:</span>
                      <select value={sel.provider} onChange={e => handleTierChange(tier, { provider: e.target.value, model: '' })}
                        aria-label={`${tier} provider`}
                        className="max-w-20 cursor-pointer rounded border border-border/50 bg-card/60 px-1 py-0.5 text-[9px] outline-none focus:border-primary/40">
                        <option value="">—</option>
                        {providers.map(p => <option key={p.id} value={p.name}>{p.name}</option>)}
                      </select>
                      <select value={sel.model} onChange={e => handleTierChange(tier, { model: e.target.value })}
                        aria-label={`${tier} model`}
                        className="max-w-28 cursor-pointer rounded border border-border/50 bg-card/60 px-1 py-0.5 font-mono text-[9px] outline-none focus:border-primary/40">
                        <option value="">—</option>
                        {providerModels.map(m => <option key={m.id} value={m.id}>{m.name || m.id}</option>)}
                      </select>
                    </div>
                  )
                })}

                {/* Fetch / Compact */}
                <button onClick={() => void handleFetchModels()} disabled={fetchingModels}
                  className="inline-flex shrink-0 items-center rounded-md border border-border/50 px-2 py-0.5 text-[9px] font-medium text-muted-foreground hover:bg-muted/50 hover:text-foreground disabled:opacity-50">
                  {fetchingModels ? <Loader2 className="size-2.5 animate-spin" /> : 'Fetch'}
                </button>
                <button onClick={() => void handleCompact()} disabled={compacting || sending}
                  className="inline-flex shrink-0 items-center rounded-md border border-border/50 px-2 py-0.5 text-[9px] font-medium text-muted-foreground hover:bg-muted/50 hover:text-foreground disabled:opacity-50">
                  {compacting ? <Loader2 className="size-2.5 animate-spin" /> : 'Compact'}
                </button>
              </div>

              {visionWarning && <p className="mb-2 text-[10px] text-warning">{visionWarning}</p>}
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
                  placeholder={activeId ? `describe what to ${agentMode === 'build' ? 'build' : 'analyze'} or drop files…` : 'Type a message to start…'}
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

        {/* Inspector Panel — right side */}
        {inspectorOpen && active && (
          <div className="w-60 lg:w-72 shrink-0 border-l border-border bg-sidebar/50 flex flex-col">
            <div className="flex items-center justify-between border-b border-border px-3 py-2">
              <span className="text-[10px] font-semibold tracking-wide">Inspector</span>
              <button onClick={() => setInspectorOpen(false)} className="text-muted-foreground/60 hover:text-foreground" aria-label="Close inspector">
                <X className="size-3" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto scroll-thin p-3 space-y-3">
              {/* Deliverables */}
              {(() => {
                const lastState = Array.from(assistantStates.values()).find(s => s.deliverables)
                if (!lastState?.deliverables) return null
                const d = lastState.deliverables
                return (
                  <div className="space-y-2">
                    <div className="flex items-center gap-1.5 text-[10px] font-semibold text-success">
                      <Check className="size-3" /> Deliverables
                    </div>
                    <div className="space-y-1.5">
                      {d.files_created?.length > 0 && (
                        <div className="rounded-md border border-border/60 bg-card/60 p-2">
                          <p className="text-[9px] text-muted-foreground mb-1">Files Created ({d.files_created.length})</p>
                          {d.files_created.slice(0, 10).map((f: string, i: number) => (
                            <div key={i} className="text-[10px] font-mono text-foreground/80 truncate">{f}</div>
                          ))}
                        </div>
                      )}
                      {d.files_modified?.length > 0 && (
                        <div className="rounded-md border border-border/60 bg-card/60 p-2">
                          <p className="text-[9px] text-muted-foreground mb-1">Files Modified ({d.files_modified.length})</p>
                          {d.files_modified.slice(0, 10).map((f: string, i: number) => (
                            <div key={i} className="text-[10px] font-mono text-foreground/80 truncate">{f}</div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )
              })()}

              {/* Active Tool Calls */}
              {(() => {
                const lastState = Array.from(assistantStates.values()).find(s => s.toolCalls.length > 0)
                if (!lastState) return null
                return (
                  <div className="space-y-2">
                    <div className="flex items-center gap-1.5 text-[10px] font-semibold text-primary">
                      <Terminal className="size-3" /> Tools
                    </div>
                    <div className="space-y-1">
                      {lastState.toolCalls.slice(-5).map(tc => (
                        <div key={tc.id} className="flex items-center gap-2 rounded-md border border-border/60 bg-card/60 px-2 py-1.5">
                          <span className={cn("size-1.5 rounded-full shrink-0",
                            tc.status === 'running' ? 'bg-warning animate-pulse' :
                            tc.status === 'completed' ? 'bg-success' : 'bg-destructive'
                          )} />
                          <span className="text-[10px] font-mono text-foreground/80">{tc.type}</span>
                          <span className="text-[9px] text-muted-foreground truncate ml-auto">{tc.duration_ms}ms</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })()}

              {/* Session Info */}
              <div className="space-y-2">
                <div className="flex items-center gap-1.5 text-[10px] font-semibold text-muted-foreground">
                  <FileText className="size-3" /> Session
                </div>
                <div className="rounded-md border border-border/60 bg-card/60 p-2 space-y-1.5">
                  <div className="flex justify-between text-[10px]">
                    <span className="text-muted-foreground">Mode</span>
                    <span className="font-mono">{agentMode}</span>
                  </div>
                  <div className="flex justify-between text-[10px]">
                    <span className="text-muted-foreground">Messages</span>
                    <span className="font-mono">{messages.length}</span>
                  </div>
                  <div className="flex justify-between text-[10px]">
                    <span className="text-muted-foreground">Worker</span>
                    <span className="font-mono">{AGENT_WORKER_MAP[agentMode]}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {!inspectorOpen && active && (
          <button onClick={() => setInspectorOpen(true)} aria-label="Open inspector"
            className="absolute right-0 top-12 z-10 rounded-l-md border border-border bg-sidebar p-1 text-muted-foreground/60 hover:text-foreground">
            <PanelRight className="size-3.5" />
          </button>
        )}
      </div>
    </div>
  )
}
