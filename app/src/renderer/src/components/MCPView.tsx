import { useState, useEffect, useCallback } from 'react'
import { Plus, RefreshCw, Play, Trash2, Server, Wrench, X, Wifi, WifiOff } from 'lucide-react'
import { Card, PageHeader, Badge } from './kit'
import { cn } from '../lib/utils'
import {
  mcpApi,
  type MCPServerRecord,
  type MCPToolRecord,
  type MCPToolExecutionRecord,
} from '../lib/api/mcp'

const statusTone: Record<string, 'muted' | 'success' | 'destructive' | 'primary'> = {
  connected: 'success',
  disconnected: 'destructive',
  error: 'destructive',
  active: 'primary',
}

export function MCPView() {
  const [servers, setServers] = useState<MCPServerRecord[]>([])
  const [tools, setTools] = useState<MCPToolRecord[]>([])
  const [executions, setExecutions] = useState<MCPToolExecutionRecord[]>([])
  const [selectedServer, setSelectedServer] = useState<string | null>(null)
  const [showRegister, setShowRegister] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Register form
  const [regName, setRegName] = useState('')
  const [regEndpoint, setRegEndpoint] = useState('')
  const [regProtocol, setRegProtocol] = useState<'stdio' | 'sse' | 'http'>('http')
  const [regDesc, setRegDesc] = useState('')

  // Execute tool
  const [executeToolId, setExecuteToolId] = useState<string | null>(null)
  const [execArgs, setExecArgs] = useState('{}')

  const loadServers = useCallback(async () => {
    try {
      const data = await mcpApi.listServers()
      setServers(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  const loadTools = useCallback(async (serverId?: string) => {
    try {
      const data = await mcpApi.listTools(serverId ? { server_id: serverId } : undefined)
      setTools(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  const loadExecutions = useCallback(async () => {
    try {
      const data = await mcpApi.listExecutions()
      setExecutions(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  useEffect(() => {
    loadServers()
    loadTools()
    loadExecutions()
  }, [loadServers, loadTools, loadExecutions])

  const handleRegister = async () => {
    if (!regName.trim() || !regEndpoint.trim()) return
    setLoading(true)
    setError(null)
    try {
      await mcpApi.registerServer({
        name: regName,
        endpoint: regEndpoint,
        protocol: regProtocol,
        description: regDesc || undefined,
      })
      setShowRegister(false)
      setRegName('')
      setRegEndpoint('')
      setRegDesc('')
      await loadServers()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const handleExecuteTool = async () => {
    if (!executeToolId) return
    setError(null)
    try {
      const args = JSON.parse(execArgs)
      await mcpApi.executeTool(executeToolId, { arguments: args })
      setExecuteToolId(null)
      setExecArgs('{}')
      await loadExecutions()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const handleServerSelect = (serverId: string) => {
    setSelectedServer(serverId === selectedServer ? null : serverId)
    loadTools(serverId === selectedServer ? undefined : serverId)
  }

  const handleConnect = async (serverId: string) => {
    setError(null)
    try {
      const result = await mcpApi.connectServer(serverId)
      await loadServers()
      await loadTools(serverId)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const handleDisconnect = async (serverId: string) => {
    setError(null)
    try {
      await mcpApi.disconnectServer(serverId)
      await loadServers()
      await loadTools()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const handleDeleteServer = async (serverId: string) => {
    setError(null)
    try {
      await mcpApi.deleteServer(serverId)
      if (selectedServer === serverId) setSelectedServer(null)
      await loadServers()
      await loadTools()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const filteredTools = selectedServer ? tools.filter((t) => t.registryId === selectedServer) : tools

  return (
    <div>
      <PageHeader
        title="MCP Servers"
        subtitle="Model Context Protocol servers, tools, and execution history."
        actions={
          <button
            onClick={() => setShowRegister(true)}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="size-4" /> Register Server
          </button>
        }
      />

      <div className="p-6 space-y-4">
        {error && (
          <Card className="border-destructive/40 bg-destructive/5 text-sm text-destructive flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)}><X className="size-4" /></button>
          </Card>
        )}

        {showRegister && (
          <Card className="space-y-3">
            <h3 className="text-sm font-semibold">Register MCP Server</h3>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Name</label>
                <input
                  value={regName}
                  onChange={(e) => setRegName(e.target.value)}
                  placeholder="Server name"
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                />
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Endpoint</label>
                <input
                  value={regEndpoint}
                  onChange={(e) => setRegEndpoint(e.target.value)}
                  placeholder="http://localhost:3000"
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                />
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Protocol</label>
                <select
                  value={regProtocol}
                  onChange={(e) => setRegProtocol(e.target.value as 'stdio' | 'sse' | 'http')}
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                >
                  <option value="http">HTTP</option>
                  <option value="sse">SSE</option>
                  <option value="stdio">Stdio</option>
                </select>
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Description</label>
                <input
                  value={regDesc}
                  onChange={(e) => setRegDesc(e.target.value)}
                  placeholder="Optional description"
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleRegister}
                disabled={loading}
                className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {loading ? 'Registering...' : 'Register'}
              </button>
              <button onClick={() => setShowRegister(false)} className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-muted">
                Cancel
              </button>
            </div>
          </Card>
        )}

        <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
          {/* Server list */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold flex items-center gap-2"><Server className="size-4" /> Servers</h3>
              <button onClick={loadServers} className="text-muted-foreground hover:text-foreground">
                <RefreshCw className="size-4" />
              </button>
            </div>
            {servers.length === 0 && <p className="text-xs text-muted-foreground">No servers registered.</p>}
            {servers.map((s) => (
              <button
                key={s.id}
                onClick={() => handleServerSelect(s.id)}
                className={cn(
                  'w-full text-left rounded-lg border p-3 transition-colors',
                  selectedServer === s.id ? 'border-primary bg-primary/5' : 'border-border bg-card hover:border-primary/40',
                )}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{s.name}</span>
                  <Badge tone={statusTone[s.status] || 'muted'}>{s.status}</Badge>
                </div>
                <p className="mt-1 text-xs font-mono text-muted-foreground">{s.endpoint}</p>
                <div className="mt-2 flex items-center gap-1.5">
                  {s.status === 'connected' ? (
                    <button onClick={(e) => { e.stopPropagation(); handleDisconnect(s.id) }}
                      className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-0.5 text-[10px] text-muted-foreground hover:text-foreground hover:bg-muted">
                      <WifiOff className="size-3" /> Disconnect
                    </button>
                  ) : (
                    <button onClick={(e) => { e.stopPropagation(); handleConnect(s.id) }}
                      className="inline-flex items-center gap-1 rounded-md border border-primary/40 px-2 py-0.5 text-[10px] text-primary hover:bg-primary/10">
                      <Wifi className="size-3" /> Connect
                    </button>
                  )}
                  <button onClick={(e) => { e.stopPropagation(); handleDeleteServer(s.id) }}
                    className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-0.5 text-[10px] text-muted-foreground hover:text-destructive hover:bg-muted">
                    <Trash2 className="size-3" /> Delete
                  </button>
                </div>
              </button>
            ))}
          </div>

          {/* Tools + Execution */}
          <div className="space-y-4">
            {/* Tools */}
            <Card>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <Wrench className="size-4" /> Tools {selectedServer ? '(filtered)' : '(all)'}
                </h3>
                <button onClick={() => loadTools(selectedServer || undefined)} className="text-muted-foreground hover:text-foreground">
                  <RefreshCw className="size-4" />
                </button>
              </div>
              {filteredTools.length === 0 ? (
                <p className="text-xs text-muted-foreground">No tools found.</p>
              ) : (
                <div className="space-y-2">
                  {filteredTools.map((t) => (
                    <div key={t.id} className="rounded-lg border border-border bg-background/50 p-3">
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="text-sm font-medium">{t.toolName}</span>
                          {t.description && <p className="text-xs text-muted-foreground mt-0.5">{t.description}</p>}
                        </div>
                        <div className="flex items-center gap-2">
                          {t.requiresApproval && <Badge tone="warning">Approval</Badge>}
                          {t.isEnabled ? <Badge tone="success">Enabled</Badge> : <Badge tone="muted">Disabled</Badge>}
                          <button
                            onClick={() => { setExecuteToolId(t.id); setExecArgs('{}') }}
                            className="inline-flex items-center gap-1 rounded-md border border-primary/50 px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10"
                          >
                            <Play className="size-3" /> Execute
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {/* Execute dialog */}
            {executeToolId && (
              <Card className="space-y-3">
                <h3 className="text-sm font-semibold">Execute Tool</h3>
                <div>
                  <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Arguments (JSON)</label>
                  <textarea
                    value={execArgs}
                    onChange={(e) => setExecArgs(e.target.value)}
                    rows={4}
                    className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 font-mono text-xs outline-none focus:border-primary"
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={handleExecuteTool}
                    className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
                  >
                    Run
                  </button>
                  <button onClick={() => setExecuteToolId(null)} className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-muted">
                    Cancel
                  </button>
                </div>
              </Card>
            )}

            {/* Execution history */}
            <Card>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold">Execution History</h3>
                <button onClick={loadExecutions} className="text-muted-foreground hover:text-foreground">
                  <RefreshCw className="size-4" />
                </button>
              </div>
              {executions.length === 0 ? (
                <p className="text-xs text-muted-foreground">No executions yet.</p>
              ) : (
                <div className="space-y-2">
                  {executions.map((ex) => (
                    <div key={ex.id} className="rounded-lg border border-border bg-background/50 p-3">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">{ex.toolName}</span>
                        <div className="flex items-center gap-2">
                          <Badge tone={ex.status === 'completed' ? 'success' : ex.status === 'failed' ? 'destructive' : 'primary'}>{ex.status}</Badge>
                          <span className="text-xs text-muted-foreground">{ex.executionTimeMs}ms</span>
                        </div>
                      </div>
                      <p className="text-[10px] text-muted-foreground mt-1">{new Date(ex.createdAt).toLocaleString()}</p>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}
