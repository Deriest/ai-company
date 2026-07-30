/**
 * WorkspaceView — Live Office Floor
 *
 * 2D animated open-office visualization showing 15 AI workers at their desks.
 * - Each desk shows worker name, status, and activity
 * - Department color-coded zones
 * - Meeting table in center activates during active tasks
 * - Real-time stats from backend
 */
import { useState, useEffect, useCallback } from 'react'
import {
  Target,
  Users,
  Terminal,
  UserPlus,
  Command,
  X,
  Coins,
  Zap,
  FolderOpen,
} from 'lucide-react'
import { Card, PageHeader, Badge } from './kit'
import { cn } from '../lib/utils'
import { apiClient } from '../lib/api/client'
import { FileTree } from './FileTree'

// ── Types ──────────────────────────────────────────────

interface WorkspaceViewProps {
  onNavigate?: (view: string) => void
  projectRoot?: string | null
  projectName?: string | null
}

interface DeskWorker {
  id: string
  name: string
  role: string
  dept: string
  color: string
  status: 'online' | 'working' | 'idle' | 'offline'
  tasks: number
  initials: string
}

// ── Office Layout ──────────────────────────────────────

const OFFICE_WORKERS: DeskWorker[] = [
  // Leadership (top center)
  { id: 'hermes', name: 'Hermes', role: 'Dispatcher', dept: 'Leadership', color: '#3ddc97', status: 'online', tasks: 0, initials: 'HE' },
  { id: 'rex', name: 'Rex', role: 'Governor', dept: 'Leadership', color: '#3ddc97', status: 'online', tasks: 0, initials: 'RX' },
  // Product (left wing)
  { id: 'pm', name: 'Aria', role: 'PM', dept: 'Product', color: '#f59e0b', status: 'online', tasks: 0, initials: 'AR' },
  { id: 'research', name: 'Sage', role: 'Research', dept: 'Product', color: '#f59e0b', status: 'online', tasks: 0, initials: 'SG' },
  { id: 'designer', name: 'Luna', role: 'Designer', dept: 'Product', color: '#f59e0b', status: 'online', tasks: 0, initials: 'LN' },
  { id: 'documentation', name: 'Echo', role: 'Docs', dept: 'Product', color: '#f59e0b', status: 'online', tasks: 0, initials: 'EC' },
  // Engineering (right wing)
  { id: 'architect', name: 'Atlas', role: 'Architect', dept: 'Engineering', color: '#22d3ee', status: 'online', tasks: 0, initials: 'AT' },
  { id: 'backend', name: 'Hugo', role: 'Backend', dept: 'Engineering', color: '#22d3ee', status: 'online', tasks: 0, initials: 'HG' },
  { id: 'frontend', name: 'Leo', role: 'Frontend', dept: 'Engineering', color: '#22d3ee', status: 'online', tasks: 0, initials: 'LE' },
  { id: 'qa', name: 'Eve', role: 'QA', dept: 'Engineering', color: '#22d3ee', status: 'online', tasks: 0, initials: 'EV' },
  { id: 'performance', name: 'Pulse', role: 'Perf', dept: 'Engineering', color: '#22d3ee', status: 'online', tasks: 0, initials: 'PL' },
  // Platform (bottom)
  { id: 'database', name: 'Nova', role: 'Database', dept: 'Platform', color: '#a78bfa', status: 'online', tasks: 0, initials: 'NV' },
  { id: 'nexus', name: 'Nexus', role: 'Integration', dept: 'Platform', color: '#a78bfa', status: 'online', tasks: 0, initials: 'NX' },
  { id: 'flint', name: 'Flint', role: 'Infra', dept: 'Platform', color: '#a78bfa', status: 'online', tasks: 0, initials: 'FL' },
  { id: 'security', name: 'Sentinel', role: 'Security', dept: 'Platform', color: '#a78bfa', status: 'online', tasks: 0, initials: 'SE' },
]

const DEPT_COLORS: Record<string, string> = {
  Leadership: 'from-success/10 to-success/5 border-success/20',
  Product: 'from-warning/10 to-warning/5 border-warning/20',
  Engineering: 'from-primary/10 to-primary/5 border-primary/20',
  Platform: 'from-info/10 to-info/5 border-info/20',
}

const DEPT_TEXT: Record<string, string> = {
  Leadership: 'text-success',
  Product: 'text-warning',
  Engineering: 'text-primary',
  Platform: 'text-info',
}

// ── Desk Component ─────────────────────────────────────

function Desk({ worker, onClick }: { worker: DeskWorker; onClick: () => void }) {
  const isWorking = worker.status === 'working'

  return (
    <button
      onClick={onClick}
      className="group relative flex flex-col items-center gap-1.5 p-2 rounded-xl transition-all hover:bg-white/5 hover:scale-105"
    >
      {/* Monitor */}
      <div className={cn(
        "relative w-12 h-9 rounded-md border-2 flex items-center justify-center transition-colors",
        isWorking
          ? "border-success/60 bg-success/10 shadow-[0_0_12px_rgba(52,211,153,0.2)]"
          : "border-border/60 bg-card/80"
      )}>
        {/* Screen content */}
        {isWorking ? (
          <div className="flex gap-0.5">
            <span className="w-1 h-1 rounded-full bg-success animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-1 h-1 rounded-full bg-success animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-1 h-1 rounded-full bg-success animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
        ) : (
          <div className="w-5 h-0.5 rounded bg-muted-foreground/30" />
        )}

        {/* Monitor stand */}
        <div className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 w-3 h-1.5 bg-border/40 rounded-b" />
      </div>

      {/* Status dot */}
      <span className={cn(
        "absolute top-1 right-1 w-2 h-2 rounded-full",
        worker.status === 'online' ? "bg-success" :
        worker.status === 'working' ? "bg-success animate-pulse" :
        worker.status === 'idle' ? "bg-warning" : "bg-muted-foreground/30"
      )} />

      {/* Name */}
      <span className="text-[10px] font-medium text-foreground/80 leading-none">{worker.name}</span>
      <span className="text-[8px] text-muted-foreground leading-none">{worker.role}</span>

      {/* Task count badge */}
      {worker.tasks > 0 && (
        <span className="absolute -top-0.5 -left-0.5 min-w-[14px] h-3.5 px-1 rounded-full bg-primary text-[8px] font-bold text-primary-foreground flex items-center justify-center">
          {worker.tasks}
        </span>
      )}
    </button>
  )
}

// ── Meeting Table ──────────────────────────────────────

function MeetingTable({ activeMissions }: { activeMissions: number }) {
  const isActive = activeMissions > 0

  return (
    <div className={cn(
      "relative flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-4 transition-all",
      isActive
        ? "border-primary/40 bg-primary/5 shadow-[0_0_30px_rgba(52,211,153,0.1)]"
        : "border-border/30 bg-muted/20"
    )}>
      {/* Table surface */}
      <div className={cn(
        "w-20 h-12 rounded-lg border flex items-center justify-center transition-colors",
        isActive
          ? "border-primary/30 bg-primary/10"
          : "border-border/30 bg-card/50"
      )}>
        {isActive ? (
          <div className="flex flex-col items-center gap-0.5">
            <span className="text-[9px] font-bold text-primary">{activeMissions}</span>
            <span className="text-[7px] text-primary/70">ACTIVE</span>
          </div>
        ) : (
          <span className="text-[8px] text-muted-foreground/50">STANDBY</span>
        )}
      </div>

      <span className="mt-2 text-[9px] font-medium text-muted-foreground">
        {isActive ? 'Mission Control' : 'Meeting Room'}
      </span>

      {/* Active pulse ring */}
      {isActive && (
        <span className="absolute inset-0 rounded-2xl animate-ping bg-primary/5 pointer-events-none" style={{ animationDuration: '3s' }} />
      )}
    </div>
  )
}

// ── Main Component ─────────────────────────────────────

export function WorkspaceView({ onNavigate, projectRoot, projectName }: WorkspaceViewProps) {
  const [error, setError] = useState('')
  const [workers, setWorkers] = useState<DeskWorker[]>(OFFICE_WORKERS)
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

      // Update worker statuses based on active tasks
      setWorkers(prev => prev.map(w => {
        const metrics = metricsMap[w.id] || {}
        const hasActiveTask = activeTasks.some((t: any) => t.worker_type === w.id)
        return {
          ...w,
          status: hasActiveTask ? 'working' : 'online',
          tasks: activeTasks.filter((t: any) => t.worker_type === w.id).length,
        }
      }))

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

  // Group workers by department
  const byDept = (dept: string) => workers.filter(w => w.dept === dept)

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
        subtitle={loading ? "Loading office…" : `${workers.filter(w => w.status !== 'offline').length} workers online · ${activeMissions} active missions`}
        actions={
          <button
            onClick={() => onNavigate?.('hermes')}
            className="inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-4 py-2 text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <Terminal className="size-4" /> Command Center
          </button>
        }
      />

      <div className="p-6 space-y-6">
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
              <p className="text-lg font-bold leading-none">{workers.filter(w => w.status !== 'offline').length}</p>
              <p className="text-[10px] text-muted-foreground">Workers Online</p>
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

        {/* Office Floor */}
        <Card className="overflow-hidden">
          <div className="relative bg-[radial-gradient(ellipse_at_center,_rgba(52,211,153,0.03)_0%,_transparent_70%)]">
            {/* Floor grid pattern */}
            <div className="absolute inset-0 opacity-[0.03]" style={{
              backgroundImage: 'linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)',
              backgroundSize: '40px 40px'
            }} />

            <div className="relative p-6">
              {/* Leadership — top center */}
              <div className="flex justify-center mb-6">
                <div className={cn("rounded-2xl bg-gradient-to-b border p-4", DEPT_COLORS.Leadership)}>
                  <p className={cn("text-[10px] font-semibold uppercase tracking-wider mb-3 text-center", DEPT_TEXT.Leadership)}>
                    Leadership
                  </p>
                  <div className="flex gap-4 justify-center">
                    {byDept('Leadership').map(w => (
                      <Desk key={w.id} worker={w} onClick={() => onNavigate?.('live')} />
                    ))}
                  </div>
                </div>
              </div>

              {/* Middle row: Product (left) + Meeting (center) + Engineering (right) */}
              <div className="grid grid-cols-[1fr_auto_1fr] gap-6 items-start">
                {/* Product — left wing */}
                <div className={cn("rounded-2xl bg-gradient-to-b border p-4", DEPT_COLORS.Product)}>
                  <p className={cn("text-[10px] font-semibold uppercase tracking-wider mb-3 text-center", DEPT_TEXT.Product)}>
                    Product
                  </p>
                  <div className="grid grid-cols-2 gap-3">
                    {byDept('Product').map(w => (
                      <Desk key={w.id} worker={w} onClick={() => onNavigate?.('live')} />
                    ))}
                  </div>
                </div>

                {/* Meeting Table — center */}
                <div className="flex items-center justify-center pt-8">
                  <MeetingTable activeMissions={activeMissions} />
                </div>

                {/* Engineering — right wing */}
                <div className={cn("rounded-2xl bg-gradient-to-b border p-4", DEPT_COLORS.Engineering)}>
                  <p className={cn("text-[10px] font-semibold uppercase tracking-wider mb-3 text-center", DEPT_TEXT.Engineering)}>
                    Engineering
                  </p>
                  <div className="grid grid-cols-2 gap-3">
                    {byDept('Engineering').map(w => (
                      <Desk key={w.id} worker={w} onClick={() => onNavigate?.('live')} />
                    ))}
                    {/* 5th worker spans */}
                    {byDept('Engineering').length % 2 === 1 && <div />}
                  </div>
                </div>
              </div>

              {/* Platform — bottom */}
              <div className="flex justify-center mt-6">
                <div className={cn("rounded-2xl bg-gradient-to-b border p-4", DEPT_COLORS.Platform)}>
                  <p className={cn("text-[10px] font-semibold uppercase tracking-wider mb-3 text-center", DEPT_TEXT.Platform)}>
                    Platform
                  </p>
                  <div className="flex gap-4 justify-center">
                    {byDept('Platform').map(w => (
                      <Desk key={w.id} worker={w} onClick={() => onNavigate?.('live')} />
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Card>

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
