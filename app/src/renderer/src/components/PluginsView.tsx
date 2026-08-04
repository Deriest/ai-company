/**
 * PluginsView — Plugin Registry UI.
 *
 * Install, manage, assign, and toggle plugins from GitHub.
 * Plugins can include skills, commands, agents, hooks, MCP servers.
 */
import { useState, useEffect } from 'react'
import {
  Plus, Search, X, Trash2, RefreshCw, Plug,
  CheckCircle2, AlertTriangle, ToggleLeft, ToggleRight,
  Terminal, Cpu, Shield, Palette,
  BookOpen, Wrench, GitPullRequest,
} from 'lucide-react'
import { Card, PageHeader, Badge } from './kit'
import { cn } from '../lib/utils'
import { apiClient } from '../lib/api/client'

interface PluginRecord {
  id: string
  plugin_id: string
  name: string
  description: string
  version: string
  source: string
  source_url: string
  package_path: string
  components: string[]
  assigned_workers: string[]
  is_enabled: boolean
  is_required: boolean
}

const COMPONENT_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  skill: Terminal,
  scripts: Terminal,
  commands: Terminal,
  agents: Cpu,
  hooks: Shield,
  mcp: GitPullRequest,
  assets: Palette,
  docs: BookOpen,
  references: BookOpen,
  templates: BookOpen,
}

const WORKER_OPTIONS = [
  'hermes', 'rex', 'pm', 'research', 'designer', 'documentation',
  'architect', 'backend', 'frontend', 'qa', 'performance', 'database',
  'nexus', 'flint', 'security', 'coding', 'debugger',
]

export function PluginsView() {
  const [plugins, setPlugins] = useState<PluginRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [showInstall, setShowInstall] = useState(false)
  const [installUrl, setInstallUrl] = useState('')
  const [installRequired, setInstallRequired] = useState(false)
  const [installing, setInstalling] = useState(false)
  const [installError, setInstallError] = useState('')
  const [expandedPlugin, setExpandedPlugin] = useState<string | null>(null)

  const load = async () => {
    try {
      setLoading(true)
      setPlugins(await apiClient.get<PluginRecord[]>('/plugins'))
    } catch (e) {
      console.error('Failed to load plugins', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  const handleInstall = async () => {
    if (!installUrl.trim()) return
    setInstalling(true)
    setInstallError('')
    try {
      await apiClient.post('/plugins/install', {
        repo_url: installUrl.trim(),
        is_required: installRequired,
      })
      setInstallUrl('')
      setShowInstall(false)
      await load()
    } catch (e) {
      setInstallError(e instanceof Error ? e.message : String(e))
    } finally {
      setInstalling(false)
    }
  }

  const handleToggle = async (plugin: PluginRecord) => {
    try {
      await apiClient.patch(`/plugins/${plugin.plugin_id}`, { is_enabled: !plugin.is_enabled })
      setPlugins(prev => prev.map(p => p.plugin_id === plugin.plugin_id ? { ...p, is_enabled: !p.is_enabled } : p))
    } catch (e) { console.error(e) }
  }

  const handleRequired = async (plugin: PluginRecord) => {
    try {
      await apiClient.patch(`/plugins/${plugin.plugin_id}`, { is_required: !plugin.is_required })
      setPlugins(prev => prev.map(p => p.plugin_id === plugin.plugin_id ? { ...p, is_required: !p.is_required } : p))
    } catch (e) { console.error(e) }
  }

  const handleAssign = async (plugin: PluginRecord, worker: string) => {
    const current = plugin.assigned_workers || []
    const updated = current.includes(worker) ? current.filter(w => w !== worker) : [...current, worker]
    try {
      await apiClient.patch(`/plugins/${plugin.plugin_id}`, { assigned_workers: updated })
      setPlugins(prev => prev.map(p => p.plugin_id === plugin.plugin_id ? { ...p, assigned_workers: updated } : p))
    } catch (e) { console.error(e) }
  }

  const handleUninstall = async (plugin: PluginRecord) => {
    try {
      await apiClient.delete(`/plugins/${plugin.plugin_id}`)
      setPlugins(prev => prev.filter(p => p.plugin_id !== plugin.plugin_id))
    } catch (e) { console.error(e) }
  }

  const filtered = plugins.filter(p =>
    !query || p.name.toLowerCase().includes(query.toLowerCase()) ||
    p.plugin_id.toLowerCase().includes(query.toLowerCase()) ||
    p.description.toLowerCase().includes(query.toLowerCase())
  )

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
      <PageHeader
        title="Plugin Registry"
        subtitle={`${plugins.length} plugins · ${plugins.filter(p => p.is_enabled).length} enabled · ${plugins.filter(p => p.is_required).length} required`}
        actions={
          <>
            <button onClick={() => setShowInstall(v => !v)}
              className="inline-flex items-center gap-2 rounded-lg bg-primary/15 px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/25">
              <Plus className="size-3.5" /> Install Plugin
            </button>
            <button onClick={load}
              className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground">
              <RefreshCw className="size-3.5" /> Refresh
            </button>
          </>
        }
      />

      <div className="flex flex-col gap-4 p-4 lg:flex-row lg:items-start">
        <div className="min-w-0 flex-1 space-y-4">
          {/* Search */}
          <div className="flex items-center gap-3 rounded-lg border border-border bg-card px-3 py-2 max-w-md focus-within:border-primary/50">
            <Search className="size-4 text-muted-foreground" />
            <input value={query} onChange={e => setQuery(e.target.value)}
              placeholder="Search plugins…"
              className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground/60" />
          </div>

          {/* Install form */}
          {showInstall && (
            <Card className="space-y-3 border-primary/30">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold">Install Plugin from GitHub</h3>
                  <p className="text-[11px] text-muted-foreground">Supports packages with .claude-plugin, SKILL.md, scripts, commands, or agents.</p>
                </div>
                <button onClick={() => setShowInstall(false)} aria-label="Close"><X className="size-4 text-muted-foreground" /></button>
              </div>
              <input value={installUrl} onChange={e => setInstallUrl(e.target.value)}
                placeholder="https://github.com/org/repo[/tree/main/path]"
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-xs outline-none focus:border-primary" />
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <input type="checkbox" checked={installRequired} onChange={e => setInstallRequired(e.target.checked)}
                  className="rounded border-border" />
                Required — workers cannot run without this plugin
              </label>
              {installError && <p className="text-xs text-destructive">{installError}</p>}
              <button onClick={() => void handleInstall()} disabled={installing || !installUrl.trim()}
                className="rounded-lg bg-primary px-4 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50">
                {installing ? 'Installing…' : 'Install Plugin'}
              </button>
            </Card>
          )}

          {/* Plugin list */}
          {loading ? (
            <div className="py-12 text-center text-sm text-muted-foreground">Loading plugins…</div>
          ) : filtered.length === 0 ? (
            <div className="py-12 text-center text-sm text-muted-foreground">
              {plugins.length === 0 ? 'No plugins installed. Install from GitHub.' : 'No plugins match your search.'}
            </div>
          ) : (
            <div className="space-y-2">
              {filtered.map(plugin => {
                const isExpanded = expandedPlugin === plugin.plugin_id
                return (
                  <Card key={plugin.plugin_id} className={cn("p-3 transition-all", !plugin.is_enabled && "opacity-50")}>
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1" onClick={() => setExpandedPlugin(isExpanded ? null : plugin.plugin_id)}>
                        <div className="flex items-center gap-2">
                          <Plug className="size-4 text-primary" />
                          <p className="text-sm font-semibold cursor-pointer hover:text-primary">{plugin.name}</p>
                          <span className="text-[10px] text-muted-foreground font-mono">v{plugin.version}</span>
                          {plugin.is_required && (
                            <Badge tone="destructive" className="text-[8px]">REQUIRED</Badge>
                          )}
                        </div>
                        <p className="mt-0.5 text-[11px] text-muted-foreground">{plugin.description}</p>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        <button onClick={() => handleRequired(plugin)} className="p-1" title={plugin.is_required ? 'Unmark required' : 'Mark required'}>
                          {plugin.is_required
                            ? <AlertTriangle className="size-3.5 text-destructive" />
                            : <CheckCircle2 className="size-3.5 text-muted-foreground hover:text-foreground" />}
                        </button>
                        <button onClick={() => handleToggle(plugin)} className="p-1" title={plugin.is_enabled ? 'Disable' : 'Enable'}>
                          {plugin.is_enabled
                            ? <ToggleRight className="size-4 text-success" />
                            : <ToggleLeft className="size-4 text-muted-foreground" />}
                        </button>
                        <button onClick={() => handleUninstall(plugin)} className="p-1 text-muted-foreground hover:text-destructive" title="Uninstall">
                          <Trash2 className="size-3" />
                        </button>
                      </div>
                    </div>

                    {/* Components */}
                    <div className="mt-2 flex flex-wrap gap-1">
                      {plugin.components?.map(c => {
                        const Icon = COMPONENT_ICONS[c] || Wrench
                        return (
                          <Badge key={c} tone="primary" className="text-[8px] uppercase gap-1">
                            <Icon className="size-2.5" /> {c}
                          </Badge>
                        )
                      })}
                    </div>

                    {/* Expanded: worker assignment */}
                    {isExpanded && (
                      <div className="mt-3 border-t border-border pt-3">
                        <p className="text-[10px] text-muted-foreground mb-1.5">Assign to workers:</p>
                        <div className="flex flex-wrap gap-1">
                          {WORKER_OPTIONS.map(w => {
                            const active = plugin.assigned_workers?.includes(w)
                            return (
                              <button key={w} onClick={() => handleAssign(plugin, w)}
                                className={cn("rounded px-2 py-0.5 text-[9px] transition-colors",
                                  active ? "bg-primary/20 text-primary" : "bg-muted text-muted-foreground hover:text-foreground"
                                )}>{w}</button>
                            )
                          })}
                        </div>
                      </div>
                    )}
                  </Card>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}