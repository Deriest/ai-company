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
  Pin, Loader2, Bot, GitBranch, X, PanelRight,
} from 'lucide-react'
import { cn } from '../lib/utils'
import { conversationsApi, type ConversationRecord, type MessageRecord } from '../lib/api/conversations'
import { chatApi, type ToolCallData, type FileDiffData, type ShellOutputData, type TodoItemData, type DeliverableSummary } from '../lib/api/chat'

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
        <div className="flex items-start gap-2">
          <span className="mt-0.5 shrink-0 font-mono text-xs font-bold text-primary/70 select-none">❯</span>
          <p className="text-[13px] leading-relaxed whitespace-pre-wrap flex-1">{message.content}</p>
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
    <aside className="flex w-52 shrink-0 flex-col border-r border-border bg-sidebar">
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
                    <button onClick={e => onDuplicate(c.id, e)} className="p-0.5 text-muted-foreground hover:text-foreground">
                      <Copy className="size-2" />
                    </button>
                    <button onClick={e => onDelete(c.id, e)} className="p-0.5 text-muted-foreground hover:text-destructive">
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

export function ChatView({ health = 'unknown' }: { health?: 'ok' | 'bad' | 'unknown' }) {
  const [conversations, setConversations] = useState<ConversationRecord[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [messages, setMessages] = useState<MessageRecord[]>([])
  const [input, setInput] = useState('')
  const [agentMode, setAgentMode] = useState<AgentMode>('build')
  const [assistantStates, setAssistantStates] = useState<Map<string, AssistantMessageState>>(new Map())
  const [contextOptimized, setContextOptimized] = useState(false)
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const active = useMemo(() => conversations.find(c => c.id === activeId) ?? null, [conversations, activeId])

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
        if (!activeId && list.length > 0) setActiveId(list[0].id)
      }
    } catch (e) { console.error('Load sessions failed', e) }
  }

  const loadMessages = async (convId: string) => {
    try { setMessages(await conversationsApi.listMessages(convId)) }
    catch (e) { console.error('Load messages failed', e) }
  }

  useEffect(() => { void loadConversations() }, [])
  useEffect(() => { if (activeId) void loadMessages(activeId); else setMessages([]) }, [activeId])
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
    if (!input.trim()) return
    const text = input.trim()
    setInput('')

    // Auto-create session if none active
    let convId = activeId
    if (!convId) {
      try {
        const conv = await conversationsApi.create(text.slice(0, 60))
        setConversations(prev => [conv, ...prev])
        convId = conv.id
        setActiveId(convId)
      } catch (e) {
        console.error('Failed to create session', e)
        setInput(text)
        return
      }
    }

    const tempUserMsg: MessageRecord = {
      id: 'temp-' + Date.now(), conversation_id: convId, role: 'user', content: text,
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

    try {
      // Use executeAgent — goes through ConversationEngine → Dispatcher → Orchestrator → Workers
      await chatApi.executeAgent(
        {
          conversation_id: convId,
          messages: [{ role: 'user', content: text }],
          worker_role: AGENT_WORKER_MAP[agentMode],
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
            updateAssistantState(tempAsstId, s => ({ ...s, isStreaming: false }))
            setMessages(prev => prev.map(m => m.id === tempAsstId ? { ...m, status: 'completed' } : m))
            void loadMessages(convId)
          },
          onError: (err) => {
            console.error('Execute error', err)
            updateAssistantState(tempAsstId, s => ({ ...s, isStreaming: false }))
            void loadMessages(convId)
          },
        },
      )
    } catch (err) {
      console.error('Send failed', err)
      setMessages(prev => prev.filter(m => m.id !== tempUserMsg.id && m.id !== tempAsstId))
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex min-h-0 flex-1">
        <Sidebar conversations={conversations} activeId={activeId} onSelect={setActiveId}
          onCreate={handleCreate} onDelete={handleDelete} onArchive={handleArchive}
          onDuplicate={handleDuplicate} onSearch={q => void loadConversations(q)} />

        <div className="flex min-w-0 flex-1 flex-col">
          {/* Header — minimal */}
          <div className="flex items-center justify-between border-b border-border px-4 py-2">
            <div className="flex items-center gap-2">
              <Terminal className="size-3.5 text-primary" />
              <span className="text-[11px] font-semibold tracking-wide">{active?.title || 'Command Center'}</span>
              {active && <span className="text-[9px] text-muted-foreground/50 font-mono">{messages.length} msgs</span>}
            </div>
            {/* Agent switcher */}
            <div className="flex items-center gap-0.5 rounded-md border border-border/50 p-0.5">
              {(['build', 'plan'] as AgentMode[]).map(mode => (
                <button key={mode} onClick={() => setAgentMode(mode)}
                  className={cn("rounded px-2.5 py-0.5 text-[10px] font-medium transition-colors",
                    agentMode === mode ? "bg-primary/15 text-primary" : "text-muted-foreground/60 hover:text-foreground"
                  )}>
                  {mode}
                </button>
              ))}
            </div>
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto scroll-thin px-4 py-3">
            {contextOptimized && (
              <div className="mx-auto max-w-3xl mb-3 flex items-center gap-2 rounded-md border border-primary/20 bg-primary/5 px-3 py-1.5 text-[11px] text-primary">
                <Loader2 className="size-3 animate-spin" />
                <span>Context optimized — older messages summarized</span>
                <button onClick={() => setContextOptimized(false)} className="ml-auto text-primary/60 hover:text-primary">
                  <X className="size-3" />
                </button>
              </div>
            )}
            {messages.length === 0 ? (
              <div className="relative grid h-full place-items-center" style={{ background: 'radial-gradient(ellipse at 50% 45%, rgba(52,211,153,0.03) 0%, transparent 60%)' }}>
                {/* Ghost conversation */}
                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none select-none" style={{ opacity: 0.08, top: '10%' }}>
                  <div className="max-w-md w-full space-y-3 px-8">
                    <div className="flex gap-2 items-start">
                      <div className="size-5 rounded-full bg-primary/40 shrink-0" />
                      <div className="rounded-lg bg-muted/50 px-3 py-1.5 text-[11px] text-foreground/60">How can I help today?</div>
                    </div>
                    <div className="flex gap-2 items-start justify-end">
                      <div className="rounded-lg bg-primary/20 px-3 py-1.5 text-[11px] text-foreground/60">Build a React dashboard with charts...</div>
                    </div>
                    <div className="flex gap-2 items-start">
                      <div className="size-5 rounded-full bg-primary/40 shrink-0" />
                      <div className="rounded-lg bg-muted/50 px-3 py-1.5 text-[11px] text-foreground/60">Planning architecture, creating components...</div>
                    </div>
                  </div>
                </div>

                {/* Main empty state — centered at ~42% */}
                <div className="relative z-10 flex flex-col items-center gap-5 -mt-12" style={{ animation: 'fadeIn 150ms ease-out' }}>
                  {/* Animated AI icon */}
                  <div className="relative">
                    <div className="grid size-16 place-items-center rounded-2xl bg-gradient-to-br from-primary/20 to-primary/5 border border-primary/20" style={{ animation: 'float 3s ease-in-out infinite' }}>
                      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" className="text-primary">
                        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </div>
                    {/* Pulse ring */}
                    <div className="absolute inset-0 rounded-2xl border border-primary/10 animate-ping" style={{ animationDuration: '3s' }} />
                  </div>

                  {/* Title & subtitle */}
                  <div className="text-center space-y-1.5">
                    <h2 className="text-lg font-semibold tracking-tight text-foreground/90">Build with AI Company</h2>
                    <p className="text-sm text-muted-foreground/70">Describe what you want to build, fix, or automate.</p>
                  </div>

                  {/* Quick command chips */}
                  <div className="flex flex-wrap justify-center gap-2 max-w-md">
                    {['Create Website', 'Build API', 'Fix Bug', 'Refactor Project', 'Generate Component', 'Write Documentation', 'Explain Repository'].map(chip => (
                      <button
                        key={chip}
                        onClick={() => setInput(chip + ': ')}
                        className="rounded-full border border-border/60 bg-card/40 px-3 py-1.5 text-[11px] text-muted-foreground/70 hover:text-foreground hover:border-primary/30 hover:bg-primary/5 transition-all"
                      >
                        {chip}
                      </button>
                    ))}
                  </div>
                </div>

                {/* CSS animations */}
                <style>{`
                  @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
                  @keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-4px); } }
                `}</style>
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
          <div className="flex items-center justify-between border-t border-border bg-sidebar px-4 py-1 text-[9px] text-muted-foreground/50">
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1">
                <span className={cn("size-1.5 rounded-full", health === 'ok' ? 'bg-success' : 'bg-destructive')} />
                {health === 'ok' ? 'connected' : health === 'bad' ? 'offline' : 'checking…'}
              </span>
              <span className="font-mono">{agentMode} agent</span>
            </div>
            <div className="flex items-center gap-3">
              <button onClick={() => setInspectorOpen(!inspectorOpen)} className="hover:text-foreground flex items-center gap-1">
                <PanelRight className="size-3" />
                {inspectorOpen ? 'inspector' : ''}
              </button>
              <span className="font-mono">Hermes</span>
            </div>
          </div>

          {/* Composer */}
          <div className="border-t border-border px-4 py-2.5">
            <div className="max-w-3xl mx-auto">
              <div className="flex items-end gap-2 rounded-lg border border-border/60 bg-card/60 px-3 py-1.5 transition-all focus-within:border-primary/40 focus-within:shadow-[0_0_12px_rgba(52,211,153,0.08)]">
                <span className="mb-1 shrink-0 font-mono text-xs font-bold text-primary/40 select-none">❯</span>
                <textarea ref={textareaRef} value={input} onChange={e => setInput(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing && e.keyCode !== 229) {
                      e.preventDefault(); void handleSend()
                    }
                  }}
                  disabled={!activeId} rows={1}
                  placeholder={activeId ? `describe what to ${agentMode === 'build' ? 'build' : 'analyze'}…` : 'create a session first'}
                  className="max-h-[160px] min-h-[24px] flex-1 resize-none bg-transparent py-0.5 text-[13px] leading-relaxed outline-none placeholder:text-muted-foreground/40 disabled:opacity-30" />
                <button onClick={() => void handleSend()} disabled={!activeId || !input.trim()}
                  className="mb-0.5 grid size-6 shrink-0 place-items-center rounded-md bg-primary/15 text-primary hover:bg-primary/25 disabled:opacity-20">
                  <Send className="size-3" />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Inspector Panel — right side */}
        {inspectorOpen && active && (
          <div className="w-72 shrink-0 border-l border-border bg-sidebar/50 flex flex-col">
            <div className="flex items-center justify-between border-b border-border px-3 py-2">
              <span className="text-[10px] font-semibold tracking-wide">Inspector</span>
              <button onClick={() => setInspectorOpen(false)} className="text-muted-foreground/60 hover:text-foreground">
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
          <button onClick={() => setInspectorOpen(true)}
            className="absolute right-0 top-12 z-10 rounded-l-md border border-border bg-sidebar p-1 text-muted-foreground/60 hover:text-foreground">
            <PanelRight className="size-3.5" />
          </button>
        )}
      </div>
    </div>
  )
}
