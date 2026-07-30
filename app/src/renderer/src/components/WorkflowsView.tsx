import { useState, useEffect, useCallback } from 'react'
import { Plus, Play, RefreshCw, GitBranch, X } from 'lucide-react'
import { Card, PageHeader, Badge } from './kit'
import { cn } from '../lib/utils'
import {
  workflowsApi,
  type WorkflowRecord,
  type WorkflowDag,
} from '../lib/api/workflows'

export function WorkflowsView() {
  const [workflows, setWorkflows] = useState<WorkflowRecord[]>([])
  const [selected, setSelected] = useState<WorkflowRecord | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Create form state
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [newDagJson, setNewDagJson] = useState('{\n  "nodes": [],\n  "edges": []\n}')

  // Instantiate state
  const [instConvId, setInstConvId] = useState('')
  const [showInstantiate, setShowInstantiate] = useState(false)

  const loadWorkflows = useCallback(async () => {
    try {
      const data = await workflowsApi.list()
      setWorkflows(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  useEffect(() => { loadWorkflows() }, [loadWorkflows])

  const handleCreate = async () => {
    if (!newName.trim()) return
    setLoading(true)
    setError(null)
    try {
      const dag: WorkflowDag = JSON.parse(newDagJson)
      await workflowsApi.create({ name: newName, description: newDesc || undefined, dag })
      setShowCreate(false)
      setNewName('')
      setNewDesc('')
      setNewDagJson('{\n  "nodes": [],\n  "edges": []\n}')
      await loadWorkflows()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const handleInstantiate = async (id: string) => {
    if (!instConvId.trim()) return
    setError(null)
    try {
      await workflowsApi.instantiate(id, { conversation_id: instConvId })
      setShowInstantiate(false)
      setInstConvId('')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div>
      <PageHeader
        title="Workflows"
        subtitle="Define, manage, and instantiate reusable workflow DAGs."
        actions={
          <button
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="size-4" /> New Workflow
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
            <h3 className="text-sm font-semibold">Create Workflow</h3>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Name</label>
                <input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="Workflow name"
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                />
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Description</label>
                <input
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  placeholder="Optional description"
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                />
              </div>
            </div>
            <div>
              <label className="text-[11px] uppercase tracking-wide text-muted-foreground">DAG (JSON)</label>
              <textarea
                value={newDagJson}
                onChange={(e) => setNewDagJson(e.target.value)}
                rows={6}
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 font-mono text-xs outline-none focus:border-primary"
              />
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
          {/* Workflow list */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">Definitions</h3>
              <button onClick={loadWorkflows} className="text-muted-foreground hover:text-foreground">
                <RefreshCw className="size-4" />
              </button>
            </div>
            {workflows.length === 0 && <p className="text-xs text-muted-foreground">No workflows defined.</p>}
            {workflows.map((w) => (
              <button
                key={w.id}
                onClick={() => setSelected(w)}
                className={cn(
                  'w-full text-left rounded-lg border p-3 transition-colors',
                  selected?.id === w.id ? 'border-primary bg-primary/5' : 'border-border bg-card hover:border-primary/40',
                )}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{w.name}</span>
                  <Badge tone="muted">v{w.version}</Badge>
                </div>
                {w.description && <p className="mt-1 text-xs text-muted-foreground truncate">{w.description}</p>}
                <p className="mt-1 text-[10px] text-muted-foreground">{w.dag.nodes.length} nodes, {w.dag.edges.length} edges</p>
              </button>
            ))}
          </div>

          {/* Workflow detail / DAG */}
          {selected ? (
            <div className="space-y-4">
              <Card>
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h3 className="text-sm font-semibold">{selected.name}</h3>
                    {selected.description && <p className="text-xs text-muted-foreground">{selected.description}</p>}
                  </div>
                  <button
                    onClick={() => setShowInstantiate(true)}
                    className="inline-flex items-center gap-1 rounded-md border border-primary/50 px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10"
                  >
                    <Play className="size-3" /> Instantiate
                  </button>
                </div>
                {showInstantiate && (
                  <div className="mb-3 flex items-end gap-2 rounded-lg border border-border bg-background/50 p-3">
                    <div className="flex-1">
                      <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Conversation ID</label>
                      <input
                        value={instConvId}
                        onChange={(e) => setInstConvId(e.target.value)}
                        placeholder="Enter conversation ID"
                        className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                      />
                    </div>
                    <button
                      onClick={() => handleInstantiate(selected.id)}
                      className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
                    >
                      Run
                    </button>
                    <button onClick={() => setShowInstantiate(false)} className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-muted">
                      Cancel
                    </button>
                  </div>
                )}
              </Card>

              {/* DAG Nodes */}
              <Card>
                <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <GitBranch className="size-4" /> DAG Nodes ({selected.dag.nodes.length})
                </h3>
                <div className="space-y-2">
                  {selected.dag.nodes.map((node) => (
                    <div key={node.id} className="rounded-lg border border-border bg-background/50 p-3">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">{node.title || node.id}</span>
                        {node.worker && <Badge tone="primary">{node.worker}</Badge>}
                      </div>
                      {node.description && <p className="mt-1 text-xs text-muted-foreground">{node.description}</p>}
                      <p className="mt-1 text-[10px] font-mono text-muted-foreground">ID: {node.id}</p>
                    </div>
                  ))}
                </div>
              </Card>

              {/* DAG Edges */}
              {selected.dag.edges.length > 0 && (
                <Card>
                  <h3 className="text-sm font-semibold mb-3">Edges ({selected.dag.edges.length})</h3>
                  <div className="space-y-1">
                    {selected.dag.edges.map((edge, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs font-mono">
                        <span className="rounded bg-muted px-1.5 py-0.5">{edge.from}</span>
                        <span className="text-muted-foreground">→</span>
                        <span className="rounded bg-muted px-1.5 py-0.5">{edge.to}</span>
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </div>
          ) : (
            <Card className="flex items-center justify-center text-sm text-muted-foreground min-h-[200px]">
              Select a workflow to view its DAG
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
