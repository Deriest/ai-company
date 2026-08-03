/**
 * WorkspaceView — Live Office Floor
 *
 * 15 worker desks with real-time status, progress bars, and activity log.
 * Dispatcher (Hermes) always active when connected. Dark AIC ADE theme.
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Target, Users, Terminal, UserPlus, Command, X, Coins, Zap, FolderOpen,
  Brain, Shield, UserCog, Search, Palette, BookOpen,
  LayoutDashboard, Server, Code, TestTube2, Gauge,
  Database, GitBranch, Rocket, Lock, CheckCircle2, Loader2, Clock,
} from 'lucide-react'
import { Card, PageHeader, ProgressBar, Badge } from './kit'
import { cn } from '../lib/utils'
import { apiClient } from '../lib/api/client'
import { FileTree } from './FileTree'

// ── Types ──────────────────────────────────────────────

interface WorkspaceViewProps {
  onNavigate?: (view: string) => void
  projectRoot?: string | null
  projectName?: string | null
  showFileTree?: boolean
  onToggleFileTree?: () => void
}

interface WorkerDef {
  id: string
  name: string
  role: string
  tier: 'thinker' | 'crafter' | 'sprinter' | 'system'
  phase: string
  icon: React.ComponentType<{ className?: string }>
  section: string
  alwaysActive?: boolean
}

type WorkerStatus = 'working' | 'idle' | 'complete' | 'meeting'

interface WorkerState {
  status: WorkerStatus
  task: string
  progress: number
}

interface ActivityEntry {
  id: string
  timestamp: string
  workerName: string
  action: string
  tone: 'primary' | 'success' | 'warning' | 'muted'
}

// ── Canonical 15 workers ───────────────────────────────

const WORKERS: WorkerDef[] = [
  // Leadership
  { id: 'hermes', name: 'Hermes', role: 'System Dispatcher', tier: 'system', phase: 'All', icon: Brain, section: 'Leadership', alwaysActive: true },
  { id: 'rex', name: 'Rex', role: 'Governor / Compliance', tier: 'sprinter', phase: 'Closeout', icon: Shield, section: 'Leadership', alwaysActive: true },

  // Product
  { id: 'pm', name: 'Aria', role: 'Project Manager', tier: 'thinker', phase: 'Discovery', icon: UserCog, section: 'Product' },
  { id: 'research', name: 'Sage', role: 'Researcher', tier: 'thinker', phase: 'Investigate', icon: Search, section: 'Product' },
  { id: 'designer', name: 'Luna', role: 'UI/UX Designer', tier: 'crafter', phase: 'Planning', icon: Palette, section: 'Product' },
  { id: 'documentation', name: 'Echo', role: 'Technical Writer', tier: 'sprinter', phase: 'Closeout', icon: BookOpen, section: 'Product' },

  // Engineering
  { id: 'architect', name: 'Atlas', role: 'Software Architect', tier: 'thinker', phase: 'Planning', icon: LayoutDashboard, section: 'Engineering' },
  { id: 'backend', name: 'Hugo', role: 'Backend Engineer', tier: 'crafter', phase: 'Implementation', icon: Server, section: 'Engineering' },
  { id: 'frontend', name: 'Leo', role: 'Frontend Engineer', tier: 'crafter', phase: 'Implementation', icon: Code, section: 'Engineering' },
  { id: 'qa', name: 'Eve', role: 'QA Engineer', tier: 'sprinter', phase: 'Verification', icon: TestTube2, section: 'Engineering' },
  { id: 'perf', name: 'Pulse', role: 'Performance Engineer', tier: 'sprinter', phase: 'Verification', icon: Gauge, section: 'Engineering' },

  // Platform
  { id: 'data', name: 'Nova', role: 'Database Engineer', tier: 'crafter', phase: 'Planning', icon: Database, section: 'Platform' },
  { id: 'integration', name: 'Nexus', role: 'Integration Engineer', tier: 'crafter', phase: 'Planning', icon: GitBranch, section: 'Platform' },
  { id: 'infra', name: 'Flint', role: 'Infrastructure Engineer', tier: 'crafter', phase: 'Planning', icon: Rocket, section: 'Platform' },
  { id: 'security', name: 'Sentinel', role: 'Security Engineer', tier: 'crafter', phase: 'Planning', icon: Lock, section: 'Platform' },
]

const SECTIONS = ['Leadership', 'Product', 'Engineering', 'Platform']

const SECTION_COLORS: Record<string, string> = {
  Leadership: 'text-primary',
  Product: 'text-warning',
  Engineering: 'text-success',
  Platform: 'text-info',
}

const TIER_COLORS: Record<string, string> = {
  thinker: 'bg-primary/15 text-primary',
  crafter: 'bg-success/15 text-success',
  sprinter: 'bg-warning/15 text-warning',
  system: 'bg-info/15 text-info',
}

const STATUS_CONFIG: Record<WorkerStatus, { dot: string; label: string; text: string }> = {
  working: { dot: 'bg-primary animate-pulse', label: 'Working', text: 'text-primary' },
  idle: { dot: 'bg-muted-foreground/40', label: 'Available', text: 'text-muted-foreground' },
  complete: { dot: 'bg-success', label: 'Complete', text: 'text-success' },
  meeting: { dot: 'bg-warning animate-pulse', label: 'Meeting', text: 'text-warning' },
}

// ── Worker Desk Card ────────────────────────────────────

function DeskCard({ worker, state }: { worker: WorkerDef; state: WorkerState }) {
  const Icon = worker.icon
  const cfg = STATUS_CONFIG[state.status]
  const isActive = state.status === 'working' || state.status === 'meeting'

  return (
    <div className={cn(
      'group relative flex flex-col rounded-lg border p-2.5 transition-all duration-200',
      isActive
        ? 'border-primary/30 bg-primary/5 shadow-[0_0_12px_-2px_rgba(99,102,241,0.15)]'
        : state.status === 'complete'
          ? 'border-success/20 bg-success/5'
          : 'border-border bg-card/50 hover:border-border/80 hover:bg-card',
    )}>
      {/* Header: avatar + name + status dot */}
      <div className="flex items-center gap-2">
        <div className={cn(
          'grid size-7 shrink-0 place-items-center rounded-md transition-colors',
          isActive ? 'bg-primary/15' : 'bg-muted/40',
        )}>
          <Icon className={cn('size-3.5', isActive ? 'text-primary' : 'text-muted-foreground')} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="truncate text-[11px] font-semibold text-foreground">{worker.name}</span>
            <span className={cn('size-1.5 shrink-0 rounded-full', cfg.dot)} />
          </div>
          <p className="truncate text-[9px] text-muted-foreground">{worker.role}</p>
        </div>
      </div>

      {/* Tier badge + status label */}
      <div className="mt-1.5 flex items-center gap-1.5">
        <span className={cn('rounded px-1 py-px text-[8px] font-semibold uppercase', TIER_COLORS[worker.tier])}>
          {worker.tier}
        </span>
        <span className={cn('text-[9px] font-medium', cfg.text)}>{cfg.label}</span>
        {worker.alwaysActive && (
          <span className="ml-auto text-[8px] text-info">●</span>
        )}
      </div>

      {/* Progress bar (only when working) */}
      {isActive && (
        <div className="mt-2">
          <ProgressBar value={state.progress} tone="primary" className="h-1" />
          <p className="mt-1 truncate text-[9px] text-muted-foreground font-mono">
            {state.task || 'Processing…'}
          </p>
        </div>
      )}

      {/* Idle state */}
      {state.status === 'idle' && (
        <p className="mt-2 text-[9px] text-muted-foreground/50">Available</p>
      )}

      {/* Complete state */}
      {state.status === 'complete' && (
        <div className="mt-2 flex items-center gap-1">
          <CheckCircle2 className="size-3 text-success" />
          <p className="truncate text-[9px] text-success/70">{state.task || 'Done'}</p>
        </div>
      )}
    </div>
  )
}

// ── Activity Log ────────────────────────────────────────

function ActivityLog({ entries }: { entries: ActivityEntry[] }) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [entries])

  return (
    <Card className="flex flex-col overflow-hidden p-0">
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <Clock className="size-3 text-muted-foreground" />
        <span className="text-[11px] font-semibold">Activity Log</span>
        <span className="ml-auto text-[9px] text-muted-foreground">{entries.length} events</span>
      </div>
      <div ref={scrollRef} className="max-h-48 flex-1 overflow-y-auto scroll-thin px-3 py-1.5">
        {entries.length === 0 ? (
          <p className="py-4 text-center text-[10px] text-muted-foreground/50">No activity yet</p>
        ) : (
          <div className="space-y-1">
            {entries.map((e) => (
              <div key={e.id} className="flex items-start gap-2 text-[10px]">
                <span className="shrink-0 font-mono text-muted-foreground/50 tabular-nums">
                  {e.timestamp}
                </span>
                <span className={cn('shrink-0 font-medium', `text-${e.tone}` === 'text-primary' ? 'text-primary' : e.tone === 'success' ? 'text-success' : e.tone === 'warning' ? 'text-warning' : 'text-muted-foreground')}>
                  {e.workerName}
                </span>
                <span className="min-w-0 flex-1 truncate text-muted-foreground">{e.action}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  )
}

// ── Main Component ─────────────────────────────────────

export function WorkspaceView({ onNavigate, projectRoot, projectName, showFileTree = true, onToggleFileTree }: WorkspaceViewProps) {
  const [error, setError] = useState('')
  const [totalWorkforce, setTotalWorkforce] = useState(15)
  const [activeMissions, setActiveMissions] = useState(0)
  const [totalTokens, setTotalTokens] = useState(0)
  const [totalCost, setTotalCost] = useState(0)
  const [loading, setLoading] = useState(true)
  const [connected, setConnected] = useState(false)
  const [workerStates, setWorkerStates] = useState<Record<string, WorkerState>>({})
  const [activities, setActivities] = useState<ActivityEntry[]>([])
  const prevStatesRef = useRef<Record<string, WorkerStatus>>({})

  const addActivity = useCallback((workerName: string, action: string, tone: ActivityEntry['tone'] = 'muted') => {
    const now = new Date()
    const timestamp = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    setActivities(prev => [...prev.slice(-49), {
      id: `${now.getTime()}-${Math.random().toString(36).slice(2, 7)}`,
      timestamp, workerName, action, tone,
    }])
  }, [])

  const loadData = useCallback(async () => {
    try {
      const [tasksRes, workersRes, usageRes, dashboardRes] = await Promise.allSettled([
        apiClient.get<any[]>('/tasks?limit=50'),
        apiClient.get<any[]>('/runtime/workers'),
        apiClient.get<any>('/api/usage/stats?days=30'),
        apiClient.get<any>('/dashboard'),
      ])

      const tasks = tasksRes.status === 'fulfilled' ? (tasksRes.value || []) : []
      const activeTasks = tasks.filter(
        (t: any) => !['completed', 'cancelled', 'failed', 'blocked'].includes(t.status)
      )
      setActiveMissions(activeTasks.length)

      const runtimeWorkers = workersRes.status === 'fulfilled' ? (workersRes.value || []) : []
      setConnected(runtimeWorkers.length > 0 || tasks.length > 0)

      if (dashboardRes.status === 'fulfilled' && dashboardRes.value) {
        setTotalWorkforce(dashboardRes.value.workers || 15)
      }

      // Build worker states
      const newStates: Record<string, WorkerState> = {}
      const prevStates = prevStatesRef.current

      for (const w of WORKERS) {
        const hasActiveTask = activeTasks.some((t: any) =>
          t.worker_type === w.id || t.worker_type === w.role.toLowerCase()
        )
        const task = activeTasks.find((t: any) =>
          t.worker_type === w.id || t.worker_type === w.role.toLowerCase()
        )

        const result: WorkerState = { status: 'idle', task: '', progress: 0 }

        if (w.alwaysActive && (runtimeWorkers.length > 0 || tasks.length > 0)) {
          result.status = 'working'
          result.task = w.id === 'hermes' ? 'Dispatching tasks' : 'Monitoring compliance'
          result.progress = 30 + Math.floor(Math.random() * 40)
        } else if (hasActiveTask && task) {
          result.status = 'working'
          result.task = task.title || task.description || 'Working on task'
          result.progress = task.progress || (20 + Math.floor(Math.random() * 60))
        } else {
          // Check runtime worker state
          const rtWorker = runtimeWorkers.find((rw: any) =>
            rw.role === w.id || rw.role === w.role.toLowerCase()
          )
          if (rtWorker?.state === 'busy' || rtWorker?.state === 'working') {
            result.status = 'working'
            result.task = rtWorker.task || 'Processing'
            result.progress = 25 + Math.floor(Math.random() * 50)
          } else if (rtWorker?.state === 'meeting') {
            result.status = 'meeting'
            result.task = 'In meeting'
            result.progress = 50
          } else {
            result.status = 'idle'
          }
        }

        newStates[w.id] = result

        // Detect state changes for activity log
        const prevStatus = prevStates[w.id]
        if (prevStatus && prevStatus !== result.status) {
          if (result.status === 'working') addActivity(w.name, 'started working', 'primary')
          else if (result.status === 'idle') addActivity(w.name, 'went idle', 'muted')
          else if (result.status === 'meeting') addActivity(w.name, 'entered meeting', 'warning')
        }
      }

      // Check for recently completed tasks
      const completedTasks = tasks
        .filter((t: any) => t.status === 'completed')
        .slice(0, 3)
      for (const ct of completedTasks) {
        const workerDef = WORKERS.find(w =>
          w.id === ct.worker_type || w.role.toLowerCase() === ct.worker_type
        )
        if (workerDef) {
          addActivity(workerDef.name, `completed: ${(ct.title || 'task').slice(0, 40)}`, 'success')
        }
      }

      prevStatesRef.current = Object.fromEntries(
        Object.entries(newStates).map(([k, v]) => [k, v.status])
      )
      setWorkerStates(newStates)

      // Usage stats
      if (usageRes.status === 'fulfilled' && usageRes.value) {
        setTotalTokens(usageRes.value.total_tokens || 0)
        setTotalCost(usageRes.value.total_cost || 0)
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [addActivity])

  // Initial load
  useEffect(() => { loadData() }, [loadData])

  // Poll every 4 seconds
  useEffect(() => {
    const interval = setInterval(loadData, 4000)
    return () => clearInterval(interval)
  }, [loadData])

  const workingCount = Object.values(workerStates).filter(s => s.status === 'working' || s.status === 'meeting').length

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      {projectRoot && (
        <div className="mx-6 mt-3 flex items-center gap-3 rounded-lg border border-primary/20 bg-primary/5 px-3 py-1.5">
          <FolderOpen className="size-4 text-primary" />
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-semibold text-primary truncate">{projectName || 'Active Project'}</p>
            <p className="text-[10px] text-muted-foreground truncate font-mono">{projectRoot}</p>
          </div>
        </div>
      )}

      <PageHeader
        title="AIC Engineering Office"
        subtitle={loading ? "Loading office…" : `${totalWorkforce} workers · ${workingCount} active · ${activeMissions} missions`}
        actions={
          <button
            onClick={() => onNavigate?.('hermes')}
            className="inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-4 py-2 text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <Terminal className="size-4" /> Command Center
          </button>
        }
      />

      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-3 pb-4 space-y-3 scroll-thin">
        {error && (
          <Card className="border-destructive/40 bg-destructive/5 text-sm text-destructive flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError('')}><X className="size-4" /></button>
          </Card>
        )}

        {/* Quick Stats Bar */}
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 sm:gap-3">
          <Card className="flex items-center gap-3 py-2.5">
            <div className="grid size-8 place-items-center rounded-lg bg-primary/15">
              <Target className="size-4 text-primary" />
            </div>
            <div>
              <p className="text-lg font-bold leading-none">{activeMissions}</p>
              <p className="text-[10px] text-muted-foreground">Active Missions</p>
            </div>
          </Card>
          <Card className="flex items-center gap-3 py-2.5">
            <div className="grid size-8 place-items-center rounded-lg bg-success/15">
              <Users className="size-4 text-success" />
            </div>
            <div>
              <p className="text-lg font-bold leading-none">{workingCount}</p>
              <p className="text-[10px] text-muted-foreground">Workers Active</p>
            </div>
          </Card>
          <Card className="flex items-center gap-3 py-2.5">
            <div className="grid size-8 place-items-center rounded-lg bg-warning/15">
              <Zap className="size-4 text-warning" />
            </div>
            <div>
              <p className="text-lg font-bold leading-none">{totalTokens > 1000 ? `${(totalTokens / 1000).toFixed(0)}k` : totalTokens}</p>
              <p className="text-[10px] text-muted-foreground">Tokens (30d)</p>
            </div>
          </Card>
          <Card className="flex items-center gap-3 py-2.5">
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
        {projectRoot && showFileTree && (
          <Card className="overflow-hidden">
            <div className="flex items-center gap-2 border-b border-border px-4 py-2">
              <FolderOpen className="size-3.5 text-primary" />
              <span className="text-[11px] font-semibold">Project Files</span>
              <span className="text-[10px] text-muted-foreground truncate">— {projectName || projectRoot}</span>
              <button
                onClick={onToggleFileTree}
                className="ml-auto text-muted-foreground hover:text-foreground transition-colors"
                title="Hide file tree"
              >
                <X className="size-3.5" />
              </button>
            </div>
            <div className="max-h-64 overflow-y-auto scroll-thin">
              <FileTree rootPath={projectRoot} onFileSelect={(path) => window.aic?.openPath?.(path)} />
            </div>
          </Card>
        )}

        {/* Office Floor: desk grid + activity log */}
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_280px]">
          {/* Desk grid grouped by section */}
          <div className="space-y-3">
            {SECTIONS.map(section => {
              const sectionWorkers = WORKERS.filter(w => w.section === section)
              const sectionWorking = sectionWorkers.filter(w => {
                const s = workerStates[w.id]
                return s && (s.status === 'working' || s.status === 'meeting')
              }).length
              return (
                <div key={section}>
                  {/* Section header */}
                  <div className="mb-1.5 flex items-center gap-2 px-1">
                    <span className={cn('text-[10px] font-bold uppercase tracking-widest', SECTION_COLORS[section])}>
                      {section}
                    </span>
                    <span className="text-[9px] text-muted-foreground">
                      {sectionWorking}/{sectionWorkers.length} active
                    </span>
                    <div className="h-px flex-1 bg-border/50" />
                  </div>
                  {/* Desk cards */}
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-5">
                    {sectionWorkers.map(w => (
                      <DeskCard
                        key={w.id}
                        worker={w}
                        state={workerStates[w.id] || { status: 'idle', task: '', progress: 0 }}
                      />
                    ))}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Activity Log sidebar */}
          <div className="lg:sticky lg:top-0 lg:self-start">
            <ActivityLog entries={activities} />
          </div>
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3 sm:gap-3">
          <button
            onClick={() => onNavigate?.('hermes')}
            className="flex items-center gap-3 rounded-xl border border-border bg-card p-3 text-left transition-all hover:border-primary/30 hover:bg-muted/50"
          >
            <div className="grid size-10 place-items-center rounded-lg bg-primary/15">
              <Terminal className="size-5 text-primary" />
            </div>
            <div>
              <p className="text-sm font-semibold">Start a Mission</p>
              <p className="text-[11px] text-muted-foreground">Create work in Command Center</p>
            </div>
          </button>
          <button
            onClick={() => onNavigate?.('live')}
            className="flex items-center gap-3 rounded-xl border border-border bg-card p-3 text-left transition-all hover:border-primary/30 hover:bg-muted/50"
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
            className="flex items-center gap-3 rounded-xl border border-border bg-card p-3 text-left transition-all hover:border-primary/30 hover:bg-muted/50"
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
