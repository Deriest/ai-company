/**
 * WorkspaceView — Live Office Floor
 *
 * 2D virtual office with animated workers walking between desks and meeting room.
 * Uses HTML5 Canvas rendering inspired by my-virtual-office.
 */
import { useState, useEffect, useCallback } from 'react'
import {
  Target, Users, Terminal, UserPlus, Command, X, Coins, Zap, FolderOpen,
} from 'lucide-react'
import { Card, PageHeader } from './kit'
import { cn } from '../lib/utils'
import { apiClient } from '../lib/api/client'
import { FileTree } from './FileTree'
import { VirtualOfficeCanvas } from './VirtualOfficeCanvas'

// ── Types ──────────────────────────────────────────────

interface WorkspaceViewProps {
  onNavigate?: (view: string) => void
  projectRoot?: string | null
  projectName?: string | null
}

// ── Main Component ─────────────────────────────────────

export function WorkspaceView({ onNavigate, projectRoot, projectName }: WorkspaceViewProps) {
  const [error, setError] = useState('')
  const [workers, setWorkers] = useState<{ id: string; state: string; task: string }[]>([])
  const [activeMissions, setActiveMissions] = useState(0)
  const [totalTokens, setTotalTokens] = useState(0)
  const [totalCost, setTotalCost] = useState(0)
  const [loading, setLoading] = useState(true)

  const loadData = useCallback(async () => {
    try {
      setLoading(true)

      const [tasksRes, workersRes, usageRes] = await Promise.allSettled([
        apiClient.get<any[]>('/tasks?limit=50'),
        apiClient.get<any[]>('/runtime/workers'),
        apiClient.get<any>('/api/usage/stats?days=30'),
      ])

      // Process tasks
      const tasks = tasksRes.status === 'fulfilled' ? (tasksRes.value || []) : []
      const activeTasks = tasks.filter(
        (t: any) => !['completed', 'cancelled', 'failed', 'blocked'].includes(t.status)
      )
      setActiveMissions(activeTasks.length)

      // Process worker metrics
      const runtimeWorkers = workersRes.status === 'fulfilled' ? (workersRes.value || []) : []
      const metricsMap: Record<string, any> = {}
      for (const w of runtimeWorkers) {
        metricsMap[w.role] = w.metrics || {}
      }

      // Map workers to states
      const workerStates = runtimeWorkers.map((w: any) => {
        const hasActiveTask = activeTasks.some((t: any) => t.worker_type === w.role)
        const task = activeTasks.find((t: any) => t.worker_type === w.role)
        return {
          id: w.role,
          state: hasActiveTask ? 'working' : 'idle',
          task: task?.title || '',
        }
      })
      setWorkers(workerStates)

      // Process usage
      if (usageRes.status === 'fulfilled' && usageRes.value) {
        setTotalTokens(usageRes.value.total_tokens || 0)
        setTotalCost(usageRes.value.total_cost || 0)
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  // Simulate meeting states for demo
  useEffect(() => {
    if (workers.length === 0) return
    const interval = setInterval(() => {
      setWorkers(prev => prev.map(w => {
        if (w.state === 'working' && Math.random() < 0.1) {
          return { ...w, state: 'meeting' }
        }
        if (w.state === 'meeting' && Math.random() < 0.15) {
          return { ...w, state: 'working' }
        }
        return w
      }))
    }, 5000)
    return () => clearInterval(interval)
  }, [workers.length])

  const handleWorkerClick = useCallback((id: string) => {
    onNavigate?.('live')
  }, [onNavigate])

  const workingCount = workers.filter(w => w.state === 'working' || w.state === 'meeting').length

  return (
    <div className="min-h-full">
      {projectRoot && (
        <div className="mx-6 mt-4 flex items-center gap-3 rounded-lg border border-primary/20 bg-primary/5 px-4 py-2">
          <FolderOpen className="size-4 text-primary" />
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-semibold text-primary truncate">{projectName || 'Active Project'}</p>
            <p className="text-[10px] text-muted-foreground truncate font-mono">{projectRoot}</p>
          </div>
        </div>
      )}

      <PageHeader
        title="AIC Engineering Office"
        subtitle={loading ? "Loading office…" : `15 workers · ${workingCount} active · ${activeMissions} missions`}
        actions={
          <button
            onClick={() => onNavigate?.('hermes')}
            className="inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-4 py-2 text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <Terminal className="size-4" /> Command Center
          </button>
        }
      />

      <div className="p-4 space-y-4">
        {error && (
          <Card className="border-destructive/40 bg-destructive/5 text-sm text-destructive flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError('')}><X className="size-4" /></button>
          </Card>
        )}

        {/* Quick Stats Bar */}
        <div className="grid grid-cols-4 gap-3">
          <Card className="flex items-center gap-3 py-3">
            <div className="grid size-8 place-items-center rounded-lg bg-primary/15">
              <Target className="size-4 text-primary" />
            </div>
            <div>
              <p className="text-lg font-bold leading-none">{activeMissions}</p>
              <p className="text-[10px] text-muted-foreground">Active Missions</p>
            </div>
          </Card>
          <Card className="flex items-center gap-3 py-3">
            <div className="grid size-8 place-items-center rounded-lg bg-success/15">
              <Users className="size-4 text-success" />
            </div>
            <div>
              <p className="text-lg font-bold leading-none">{workingCount}</p>
              <p className="text-[10px] text-muted-foreground">Workers Active</p>
            </div>
          </Card>
          <Card className="flex items-center gap-3 py-3">
            <div className="grid size-8 place-items-center rounded-lg bg-warning/15">
              <Zap className="size-4 text-warning" />
            </div>
            <div>
              <p className="text-lg font-bold leading-none">{totalTokens > 1000 ? `${(totalTokens / 1000).toFixed(0)}k` : totalTokens}</p>
              <p className="text-[10px] text-muted-foreground">Tokens (30d)</p>
            </div>
          </Card>
          <Card className="flex items-center gap-3 py-3">
            <div className="grid size-8 place-items-center rounded-lg bg-info/15">
              <Coins className="size-4 text-info" />
            </div>
            <div>
              <p className="text-lg font-bold leading-none">${totalCost.toFixed(2)}</p>
              <p className="text-[10px] text-muted-foreground">Cost (30d)</p>
            </div>
          </Card>
        </div>

        {/* Project File Tree */}
        {projectRoot && (
          <Card className="overflow-hidden">
            <div className="flex items-center gap-2 border-b border-border px-4 py-2">
              <FolderOpen className="size-3.5 text-primary" />
              <span className="text-[11px] font-semibold">Project Files</span>
              <span className="text-[10px] text-muted-foreground truncate">— {projectName || projectRoot}</span>
            </div>
            <div className="max-h-64 overflow-y-auto scroll-thin">
              <FileTree rootPath={projectRoot} onFileSelect={(path) => window.aic?.openPath?.(path)} />
            </div>
          </Card>
        )}

        {/* Virtual Office Canvas */}
        <VirtualOfficeCanvas workers={workers} onWorkerClick={handleWorkerClick} />

        {/* Quick Actions */}
        <div className="grid grid-cols-3 gap-3">
          <button
            onClick={() => onNavigate?.('hermes')}
            className="flex items-center gap-3 rounded-xl border border-border bg-card p-4 text-left transition-all hover:border-primary/30 hover:bg-muted/50"
          >
            <div className="grid size-10 place-items-center rounded-lg bg-primary/15">
              <Terminal className="size-5 text-primary" />
            </div>
            <div>
              <p className="text-sm font-semibold">New Mission</p>
              <p className="text-[11px] text-muted-foreground">Open Command Center</p>
            </div>
          </button>
          <button
            onClick={() => onNavigate?.('live')}
            className="flex items-center gap-3 rounded-xl border border-border bg-card p-4 text-left transition-all hover:border-primary/30 hover:bg-muted/50"
          >
            <div className="grid size-10 place-items-center rounded-lg bg-success/15">
              <UserPlus className="size-5 text-success" />
            </div>
            <div>
              <p className="text-sm font-semibold">View Workforce</p>
              <p className="text-[11px] text-muted-foreground">Org chart & metrics</p>
            </div>
          </button>
          <button
            onClick={() => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true }))}
            className="flex items-center gap-3 rounded-xl border border-border bg-card p-4 text-left transition-all hover:border-primary/30 hover:bg-muted/50"
          >
            <div className="grid size-10 place-items-center rounded-lg bg-warning/15">
              <Command className="size-5 text-warning" />
            </div>
            <div>
              <p className="text-sm font-semibold">Command Palette</p>
              <p className="text-[11px] text-muted-foreground">Quick navigation</p>
            </div>
          </button>
        </div>
      </div>
    </div>
  )
}
