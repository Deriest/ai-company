import { useState, useEffect, useMemo } from 'react'
import { Search, Terminal, Users, Wrench, Plug, Settings, MessageSquare, LayoutDashboard, BarChart3, PanelBottom, PanelLeft } from 'lucide-react'
import { cn } from '../lib/utils'

interface Command {
  id: string
  label: string
  category: string
  icon: React.ComponentType<{ className?: string }>
  action: () => void
}

export function CommandPalette({ open, onClose, onNavigate, onNewSession, onToggleTerminal, onToggleFileTree }: {
  open: boolean; onClose: () => void; onNavigate: (view: string) => void; onNewSession: () => void;
  onToggleTerminal?: () => void; onToggleFileTree?: () => void
}) {
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(0)

  const commands: Command[] = useMemo(() => [
    { id: 'office', label: 'Go to Office', category: 'Navigation', icon: LayoutDashboard, action: () => { onNavigate('home'); onClose() } },
    { id: 'command', label: 'Go to Command Center', category: 'Navigation', icon: MessageSquare, action: () => { onNavigate('hermes'); onClose() } },
    { id: 'company', label: 'Go to Live Company', category: 'Navigation', icon: Users, action: () => { onNavigate('live'); onClose() } },
    { id: 'skills', label: 'Go to Skills', category: 'Navigation', icon: Wrench, action: () => { onNavigate('skills'); onClose() } },
    { id: 'mcp', label: 'Go to MCP Servers', category: 'Navigation', icon: Plug, action: () => { onNavigate('mcp'); onClose() } },
    { id: 'observability', label: 'Go to Observability', category: 'Navigation', icon: BarChart3, action: () => { onNavigate('observability'); onClose() } },
    { id: 'settings', label: 'Open Settings', category: 'Navigation', icon: Settings, action: () => { onNavigate('settings'); onClose() } },
    { id: 'new-conversation', label: 'New Conversation', category: 'Actions', icon: Terminal, action: () => { onNewSession(); onClose() } },
    { id: 'toggle-terminal', label: 'Toggle Terminal', category: 'Actions', icon: PanelBottom, action: () => { onToggleTerminal?.(); onClose() } },
    { id: 'toggle-file-tree', label: 'Toggle File Tree', category: 'Actions', icon: PanelLeft, action: () => { onToggleFileTree?.(); onClose() } },
  ], [onNavigate, onNewSession, onClose, onToggleTerminal, onToggleFileTree])

  const filtered = useMemo(() => {
    if (!query) return commands
    const q = query.toLowerCase()
    return commands.filter(c => c.label.toLowerCase().includes(q) || c.category.toLowerCase().includes(q))
  }, [query, commands])

  useEffect(() => { setSelected(0); setQuery('') }, [open])
  useEffect(() => { setSelected(0) }, [query])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]" onClick={onClose}>
      <div className="w-full max-w-md rounded-xl border border-border bg-card shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center gap-2 border-b border-border px-4 py-3">
          <Search className="size-4 text-muted-foreground" />
          <input
            value={query} onChange={e => setQuery(e.target.value)}
            placeholder="Type a command…"
            className="flex-1 bg-transparent text-sm outline-none"
            autoFocus
            onKeyDown={e => {
              if (e.key === 'Escape') onClose()
              if (e.key === 'ArrowDown') { e.preventDefault(); setSelected(s => Math.min(s + 1, filtered.length - 1)) }
              if (e.key === 'ArrowUp') { e.preventDefault(); setSelected(s => Math.max(s - 1, 0)) }
              if (e.key === 'Enter' && filtered[selected]) filtered[selected].action()
            }}
          />
        </div>
        <div className="max-h-64 overflow-y-auto py-1">
          {filtered.map((cmd, i) => {
            const Icon = cmd.icon
            return (
              <button key={cmd.id} onClick={cmd.action}
                className={cn("flex w-full items-center gap-3 px-4 py-2 text-sm text-left",
                  i === selected ? "bg-primary/10 text-primary" : "text-foreground hover:bg-muted/50"
                )}>
                <Icon className="size-4 shrink-0 text-muted-foreground" />
                <span className="flex-1">{cmd.label}</span>
                <span className="text-[10px] text-muted-foreground">{cmd.category}</span>
              </button>
            )
          })}
          {filtered.length === 0 && <p className="px-4 py-3 text-sm text-muted-foreground">No commands found</p>}
        </div>
      </div>
    </div>
  )
}
