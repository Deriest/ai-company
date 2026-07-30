import { useState, useEffect, useCallback } from 'react'
import { Plus, Play, XCircle, RefreshCw, CheckCircle, X } from 'lucide-react'
import { Card, PageHeader, Badge, ProgressBar } from './kit'
import { cn } from '../lib/utils'
import {
  orchestrationApi,
  type OrchestrationSessionRecord,
  type OrchestrationSessionDetail,
  type OrchestrationApprovalRecord,
} from '../lib/api/orchestration'

const statusTone: Record<string, 'muted' | 'success' | 'warning' | 'destructive' | 'primary'> = {
  pending: 'muted',
  running: 'primary',
  paused: 'warning',
  completed: 'success',
  failed: 'destructive',
  cancelled: 'destructive',
}

const taskStatusTone: Record<string, 'muted' | 'success' | 'warning' | 'destructive' | 'primary'> = {
  pending: 'muted',
  queued: 'muted',
  running: 'primary',
  completed: 'success',
  failed: 'destructive',
  skipped: 'warning',
  cancelled: 'destructive',
}

export function OrchestrationView() {
  const [sessions, setSessions] = useState<OrchestrationSessionRecord[]>([])
  const [selected, setSelected] = useState<OrchestrationSessionDetail | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [newConvId, setNewConvId] = useState('')
  const [newMode, setNewMode] = useState('sequential')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadSessions = useCallback(async () => {
    try {
      const data = await orchestrationApi.listSessions()
      setSessions(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  const loadDetail = useCallback(async (id: string) => {
    try {
      const detail = await orchestrationApi.getSession(id)
      setSelected(detail)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  useEffect(() => { loadSessions() }, [loadSessions])

  const handleCreate = async () => {
    if (!newConvId.trim()) return
    setLoading(true)
    setError(null)
    try {
      await orchestrationApi.createSession({ conversation_id: newConvId, mode: newMode })
      setShowCreate(false)
      setNewConvId('')
      await loadSessions()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const handleExecute = async (id: string) => {
    try {
      await orchestrationApi.executeSession(id)
      await loadDetail(id)
      await loadSessions()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const handleCancel = async (id: string) => {
    try {
      await orchestrationApi.cancelSession(id)
      await loadDetail(id)
      await loadSessions()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const handleResolveApproval = async (approvalId: string, approved: boolean) => {
    try {
      await orchestrationApi.resolveApproval(approvalId, { approved })
      if (selected) await loadDetail(selected.id)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div>
      <PageHeader
        title="Orchestration"
        subtitle="Manage multi-agent orchestration sessions, tasks, and approvals."
        actions={
          <button
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="size-4" /> New Session
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

        {showCreate && (
          <Card className="space-y-3">
            <h3 className="text-sm font-semibold">Create Orchestration Session</h3>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Conversation ID</label>
                <input
                  value={newConvId}
                  onChange={(e) => setNewConvId(e.target.value)}
                  placeholder="Enter conversation ID"
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                />
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Mode</label>
                <select
                  value={newMode}
                  onChange={(e) => setNewMode(e.target.value)}
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                >
                  <option value="sequential">Sequential</option>
                  <option value="parallel">Parallel</option>
                </select>
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleCreate}
                disabled={loading}
                className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {loading ? 'Creating...' : 'Create'}
              </button>
              <button onClick={() => setShowCreate(false)} className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-muted">
                Cancel
              </button>
            </div>
          </Card>
        )}

        <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
          {/* Session list */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">Sessions</h3>
              <button onClick={loadSessions} className="text-muted-foreground hover:text-foreground">
                <RefreshCw className="size-4" />
              </button>
            </div>
            {sessions.length === 0 && <p className="text-xs text-muted-foreground">No sessions found.</p>}
            {sessions.map((s) => (
              <button
                key={s.id}
                onClick={() => loadDetail(s.id)}
                className={cn(
                  'w-full text-left rounded-lg border p-3 transition-colors',
                  selected?.id === s.id ? 'border-primary bg-primary/5' : 'border-border bg-card hover:border-primary/40',
                )}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono truncate max-w-[180px]">{s.id}</span>
                  <Badge tone={statusTone[s.status] || 'muted'}>{s.status}</Badge>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">Mode: {s.mode}</p>
                {s.createdAt && <p className="mt-0.5 text-[10px] text-muted-foreground">{new Date(s.createdAt).toLocaleString()}</p>}
              </button>
            ))}
          </div>

          {/* Session detail */}
          {selected && (
            <div className="space-y-4">
              <Card>
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h3 className="text-sm font-semibold">Session Detail</h3>
                    <p className="text-xs font-mono text-muted-foreground">{selected.id}</p>
                  </div>
                  <div className="flex gap-2">
                    {(selected.status === 'pending' || selected.status === 'paused') && (
                      <button
                        onClick={() => handleExecute(selected.id)}
                        className="inline-flex items-center gap-1 rounded-md border border-primary/50 px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10"
                      >
                        <Play className="size-3" /> Execute
                      </button>
                    )}
                    {(selected.status === 'running' || selected.status === 'pending') && (
                      <button
                        onClick={() => handleCancel(selected.id)}
                        className="inline-flex items-center gap-1 rounded-md border border-destructive/40 px-2 py-1 text-xs text-destructive hover:bg-destructive/10"
                      >
                        <XCircle className="size-3" /> Cancel
                      </button>
                    )}
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-3 text-xs">
                  <div><span className="text-muted-foreground">Mode:</span> {selected.mode}</div>
                  <div><span className="text-muted-foreground">Status:</span> <Badge tone={statusTone[selected.status] || 'muted'}>{selected.status}</Badge></div>
                  <div><span className="text-muted-foreground">Created:</span> {selected.createdAt ? new Date(selected.createdAt).toLocaleString() : '—'}</div>
                </div>
                {selected.errorMessage && (
                  <p className="mt-2 text-xs text-destructive">Error: {selected.errorMessage}</p>
                )}
              </Card>

              {/* Tasks */}
              <Card>
                <h3 className="text-sm font-semibold mb-3">Tasks ({selected.tasks.length})</h3>
                <div className="space-y-2">
                  {selected.tasks.map((t) => (
                    <div key={t.id} className="rounded-lg border border-border bg-background/50 p-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium">{t.title}</span>
                          <Badge tone="muted">{t.workerRole}</Badge>
                        </div>
                        <Badge tone={taskStatusTone[t.status] || 'muted'}>{t.status}</Badge>
                      </div>
                      {t.description && <p className="mt-1 text-xs text-muted-foreground">{t.description}</p>}
                      {t.dependsOn.length > 0 && (
                        <p className="mt-1 text-[10px] text-muted-foreground">Depends on: {t.dependsOn.join(', ')}</p>
                      )}
                      {t.errorMessage && <p className="mt-1 text-xs text-destructive">{t.errorMessage}</p>}
                    </div>
                  ))}
                </div>
              </Card>

              {/* Approvals */}
              {selected.approvals.length > 0 && (
                <Card>
                  <h3 className="text-sm font-semibold mb-3">Approvals ({selected.approvals.length})</h3>
                  <div className="space-y-2">
                    {selected.approvals.map((a) => (
                      <div key={a.id} className="rounded-lg border border-border bg-background/50 p-3">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-xs font-mono">Task: {a.taskId}</p>
                            {a.reason && <p className="text-xs text-muted-foreground mt-0.5">{a.reason}</p>}
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge tone={a.status === 'approved' ? 'success' : a.status === 'rejected' ? 'destructive' : 'warning'}>
                              {a.status}
                            </Badge>
                            {a.status === 'pending' && (
                              <div className="flex gap-1">
                                <button
                                  onClick={() => handleResolveApproval(a.id, true)}
                                  className="inline-flex items-center gap-1 rounded-md border border-success/40 px-2 py-1 text-xs text-success hover:bg-success/10"
                                >
                                  <CheckCircle className="size-3" /> Approve
                                </button>
                                <button
                                  onClick={() => handleResolveApproval(a.id, false)}
                                  className="inline-flex items-center gap-1 rounded-md border border-destructive/40 px-2 py-1 text-xs text-destructive hover:bg-destructive/10"
                                >
                                  <XCircle className="size-3" /> Reject
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </div>
          )}

          {!selected && (
            <Card className="flex items-center justify-center text-sm text-muted-foreground min-h-[200px]">
              Select a session to view details
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
