/**
 * WorkspaceView — Live Office Floor
 *
 * 15 worker desks with animated pixel-art worker sprites, real-time status,
 * progress bars, and activity log. Adapted from aic-skill office floor.
 * Theme: dark AIC ADE (oklch), not retro-CRT.
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Target, Users, Terminal, UserPlus, Command, X, Zap, FolderOpen, Activity,
  Brain, Shield, UserCog, Search, Palette, BookOpen,
  LayoutDashboard, Server, Code, TestTube2, Gauge,
  Database, GitBranch, Rocket, Lock, CheckCircle2, Clock,
} from 'lucide-react'
import { Card, PageHeader, ProgressBar } from './kit'
import { cn } from '../lib/utils'
import { apiClient } from '../lib/api/client'
import { connectWs } from '../lib/runtimeClient'
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
  skinColor: string
  shirtColor: string
  pantsColor: string
  hairColor: string
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

// ── Canonical 15 workers with sprite colors ────────────

const WORKERS: WorkerDef[] = [
  // Leadership
  { id: 'hermes', name: 'Hermes', role: 'System Dispatcher', tier: 'system', phase: 'All', icon: Brain, section: 'Leadership', skinColor: '#d4a574', shirtColor: '#dc143c', pantsColor: '#1a1a1a', hairColor: '#2a2a2a' },
  { id: 'rex', name: 'Rex', role: 'Governor / Compliance', tier: 'sprinter', phase: 'Closeout', icon: Shield, section: 'Leadership', skinColor: '#ffdbac', shirtColor: '#ffd700', pantsColor: '#2a2a2a', hairColor: '#1a1a1a' },

  // Product
  { id: 'pm', name: 'Aria', role: 'Project Manager', tier: 'thinker', phase: 'Discovery', icon: UserCog, section: 'Product', skinColor: '#ffcc99', shirtColor: '#3366cc', pantsColor: '#333366', hairColor: '#4a3728' },
  { id: 'research', name: 'Sage', role: 'Researcher', tier: 'thinker', phase: 'Investigate', icon: Search, section: 'Product', skinColor: '#e6c8b0', shirtColor: '#228b22', pantsColor: '#1a1a2a', hairColor: '#1a1a1a' },
  { id: 'designer', name: 'Luna', role: 'UI/UX Designer', tier: 'crafter', phase: 'Planning', icon: Palette, section: 'Product', skinColor: '#d4a574', shirtColor: '#ff69b4', pantsColor: '#2a1a2a', hairColor: '#8b4513' },
  { id: 'documentation', name: 'Echo', role: 'Technical Writer', tier: 'sprinter', phase: 'Closeout', icon: BookOpen, section: 'Product', skinColor: '#ffcc99', shirtColor: '#20b2aa', pantsColor: '#1a2a2a', hairColor: '#654321' },

  // Engineering
  { id: 'architect', name: 'Atlas', role: 'Software Architect', tier: 'thinker', phase: 'Planning', icon: LayoutDashboard, section: 'Engineering', skinColor: '#ffdbac', shirtColor: '#8b4513', pantsColor: '#2a2a2a', hairColor: '#654321' },
  { id: 'backend', name: 'Hugo', role: 'Backend Engineer', tier: 'crafter', phase: 'Implementation', icon: Server, section: 'Engineering', skinColor: '#d4a574', shirtColor: '#9932cc', pantsColor: '#1a1a1a', hairColor: '#1a1a1a' },
  { id: 'frontend', name: 'Leo', role: 'Frontend Engineer', tier: 'crafter', phase: 'Implementation', icon: Code, section: 'Engineering', skinColor: '#e6c8b0', shirtColor: '#00bfff', pantsColor: '#1a1a1a', hairColor: '#2a2a2a' },
  { id: 'qa', name: 'Eve', role: 'QA Engineer', tier: 'sprinter', phase: 'Verification', icon: TestTube2, section: 'Engineering', skinColor: '#e6c8b0', shirtColor: '#00ced1', pantsColor: '#1a2a1a', hairColor: '#654321' },
  { id: 'performance', name: 'Pulse', role: 'Performance Engineer', tier: 'sprinter', phase: 'Verification', icon: Gauge, section: 'Engineering', skinColor: '#ffdbac', shirtColor: '#ff6347', pantsColor: '#2a1a1a', hairColor: '#8b4513' },

  // Platform
  { id: 'database', name: 'Nova', role: 'Database Engineer', tier: 'crafter', phase: 'Planning', icon: Database, section: 'Platform', skinColor: '#e6c8b0', shirtColor: '#ff8c00', pantsColor: '#2a2a1a', hairColor: '#2a2a2a' },
  { id: 'nexus', name: 'Nexus', role: 'Integration Engineer', tier: 'crafter', phase: 'Planning', icon: GitBranch, section: 'Platform', skinColor: '#d4a574', shirtColor: '#9370db', pantsColor: '#1a1a2a', hairColor: '#1a1a1a' },
  { id: 'flint', name: 'Flint', role: 'Infrastructure Engineer', tier: 'crafter', phase: 'Planning', icon: Rocket, section: 'Platform', skinColor: '#ffcc99', shirtColor: '#ff4500', pantsColor: '#2a1a1a', hairColor: '#8b4513' },
  { id: 'security', name: 'Sentinel', role: 'Security Engineer', tier: 'crafter', phase: 'Planning', icon: Lock, section: 'Platform', skinColor: '#e6c8b0', shirtColor: '#2f4f4f', pantsColor: '#1a1a1a', hairColor: '#2a2a2a' },
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

const STATUS_CONFIG: Record<WorkerStatus, { dot: string; label: string; text: string; cardBorder: string; cardBg: string }> = {
  working: { dot: 'bg-primary animate-pulse', label: 'Working', text: 'text-primary', cardBorder: 'border-primary/40', cardBg: 'bg-primary/5' },
  idle: { dot: 'bg-muted-foreground/40', label: 'Idle', text: 'text-muted-foreground', cardBorder: 'border-border', cardBg: 'bg-card/50' },
  complete: { dot: 'bg-success', label: 'Complete', text: 'text-success', cardBorder: 'border-success/30', cardBg: 'bg-success/5' },
  meeting: { dot: 'bg-warning animate-pulse', label: 'Meeting', text: 'text-warning', cardBorder: 'border-warning/30', cardBg: 'bg-warning/5' },
}

// ── Pixel character renderer ───────────────────────────

function drawPixelCharacter(
  canvas: HTMLCanvasElement,
  worker: WorkerDef,
  isWorking: boolean,
  frame: number,
  eyeFrame: number,
): void {
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const s = 3
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  // Hair
  ctx.fillStyle = worker.hairColor
  ctx.fillRect(5 * s, 0, 4 * s, 2 * s)
  ctx.fillRect(4 * s, 1 * s, 6 * s, 2 * s)

  // Head/skin
  ctx.fillStyle = worker.skinColor
  ctx.fillRect(5 * s, 2 * s, 4 * s, 4 * s)

  // Eyes
  ctx.fillStyle = '#000'
  if (eyeFrame === 1) {
    ctx.fillRect(6 * s, 3 * s, s, Math.max(1, Math.floor(s / 3)))
    ctx.fillRect(8 * s, 3 * s, s, Math.max(1, Math.floor(s / 3)))
  } else {
    ctx.fillRect(6 * s, 3 * s, s, s)
    ctx.fillRect(8 * s, 3 * s, s, s)
  }

  // Mouth
  if (isWorking) {
    ctx.fillStyle = '#ff6666'
    ctx.fillRect(7 * s, 5 * s, s, s)
  }

  // Shirt
  ctx.fillStyle = worker.shirtColor
  ctx.fillRect(4 * s, 6 * s, 6 * s, 4 * s)
  ctx.fillRect(3 * s, 7 * s, 2 * s, 3 * s)
  ctx.fillRect(9 * s, 7 * s, 2 * s, 3 * s)

  // Pants
  ctx.fillStyle = worker.pantsColor
  ctx.fillRect(4 * s, 10 * s, 3 * s, 3 * s)
  ctx.fillRect(7 * s, 10 * s, 3 * s, 3 * s)

  // Arms
  ctx.fillStyle = worker.skinColor
  if (isWorking) {
    if (frame === 0) {
      ctx.fillRect(2 * s, 8 * s, 2 * s, 2 * s)
      ctx.fillRect(10 * s, 8 * s, 2 * s, 2 * s)
    } else {
      ctx.fillRect(2 * s, 7 * s, 2 * s, 2 * s)
      ctx.fillRect(10 * s, 9 * s, 2 * s, 2 * s)
    }
  } else {
    ctx.fillRect(2 * s, 9 * s, 2 * s, 2 * s)
    ctx.fillRect(10 * s, 9 * s, 2 * s, 2 * s)
  }
}

// ── Worker sprite with animation ───────────────────────

function WorkerSprite({ worker, status }: { worker: WorkerDef; status: WorkerStatus }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const frameRef = useRef(0)
  const eyeRef = useRef(0)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const isWorking = status === 'working' || status === 'meeting'
    const tick = isWorking ? 200 : 3000

    frameRef.current = 0
    eyeRef.current = 0
    drawPixelCharacter(canvas, worker, isWorking, 0, 0)

    let blinkCounter = 0
    // L7: track the pending blink-close timeout so the effect cleanup can clear
    // it — previously every blink scheduled a 100ms timer that was never
    // cleared on unmount/status change (one leaked timer per idle tick).
    let blinkTimeoutId: ReturnType<typeof setTimeout> | undefined
    const interval = setInterval(() => {
      if (isWorking) {
        frameRef.current = frameRef.current === 0 ? 1 : 0
        eyeRef.current = eyeRef.current === 0 ? 1 : 0
        drawPixelCharacter(canvas, worker, true, frameRef.current, eyeRef.current)
      } else {
        blinkCounter++
        if (blinkCounter % 4 === 0) {
          eyeRef.current = 1
          drawPixelCharacter(canvas, worker, false, 0, 1)
          blinkTimeoutId = setTimeout(() => {
            eyeRef.current = 0
            drawPixelCharacter(canvas, worker, false, 0, 0)
          }, 100)
        }
      }
    }, tick)

    return () => {
      if (blinkTimeoutId !== undefined) clearTimeout(blinkTimeoutId)
      clearInterval(interval)
    }
  }, [worker, status])

  // Shake animation for working status via CSS class
  const animClass = status === 'working'
    ? 'animate-bounce'
    : status === 'meeting'
      ? 'animate-pulse'
      : status === 'complete'
        ? ''
        : ''

  return (
    <div className={cn('flex justify-center', animClass)} style={{ imageRendering: 'pixelated' }}>
      <canvas ref={canvasRef} width={42} height={45} className="block" style={{ imageRendering: 'pixelated' }} />
    </div>
  )
}

// ── Desk computer (pixel screen) ────────────────────────

function DeskScreen({ status }: { status: WorkerStatus }) {
  const screenColor = status === 'working' ? 'bg-primary/60' : status === 'complete' ? 'bg-success/60' : status === 'meeting' ? 'bg-warning/60' : 'bg-muted-foreground/30'
  return (
    <div className="mx-auto mb-0.5 flex h-3 w-7 items-center justify-center rounded-sm border border-border/60 bg-[#2a2a2a]">
      <div className={cn('h-1.5 w-5 rounded-sm', screenColor, status === 'working' && 'animate-pulse')} />
    </div>
  )
}

// ── Worker Desk Card ────────────────────────────────────

function DeskCard({ worker, state }: { worker: WorkerDef; state: WorkerState }) {
  const cfg = STATUS_CONFIG[state.status]
  const isActive = state.status === 'working' || state.status === 'meeting'
  const Icon = worker.icon

  return (
    <div className={cn(
      'group relative flex flex-col rounded-lg border-2 p-2 transition-all duration-300',
      cfg.cardBorder, cfg.cardBg,
      isActive && 'shadow-[0_0_12px_-2px_rgba(99,102,241,0.2)]',
    )}>
      {/* Status bubble */}
      <div className="absolute -top-1.5 left-1/2 -translate-x-1/2 whitespace-nowrap z-20">
        <span className={cn(
          'rounded border px-1.5 py-px text-[9px] font-bold tracking-wider',
          cfg.cardBg, cfg.text, cfg.cardBorder,
        )}>
          {cfg.label.toUpperCase()}
        </span>
      </div>

      {/* Character + screen area */}
      <div className="flex h-[60px] flex-col items-center justify-end pt-2">
        <DeskScreen status={state.status} />
        <WorkerSprite worker={worker} status={state.status} />
      </div>

      {/* Desk surface */}
      <div className="mx-auto h-2 w-[80%] rounded-sm bg-gradient-to-b from-[#4a3728] to-[#3d2d1f] border border-[#2a1f15]" />

      {/* Worker info */}
      <div className="mt-1.5 flex items-center gap-1.5">
        <div className={cn(
          'grid size-5 shrink-0 place-items-center rounded',
          isActive ? 'bg-primary/15' : 'bg-muted/40',
        )}>
          <Icon className={cn('size-2.5', isActive ? 'text-primary' : 'text-muted-foreground')} />
        </div>
        <div className="min-w-0 flex-1">
          <span className="truncate text-[10px] font-semibold text-foreground">{worker.name}</span>
          <p className="truncate text-[10px] text-muted-foreground">{worker.role}</p>
        </div>
        <span className={cn('rounded px-1 py-px text-[9px] font-bold uppercase', TIER_COLORS[worker.tier])}>
          {worker.tier}
        </span>
      </div>

      {/* Progress bar (only when working) */}
      {isActive && (
        <div className="mt-1.5">
          <ProgressBar value={state.progress} tone="primary" className="h-1" />
          <p className="mt-0.5 truncate text-[10px] text-muted-foreground font-mono">
            {state.task || 'Processing…'}
          </p>
        </div>
      )}

      {/* Idle / complete states */}
      {state.status === 'idle' && (
        <p className="mt-1.5 text-[10px] text-muted-foreground/50">Available</p>
      )}
      {state.status === 'complete' && (
        <div className="mt-1.5 flex items-center gap-1">
          <CheckCircle2 className="size-2.5 text-success" />
          <p className="truncate text-[10px] text-success/70">{state.task || 'Done'}</p>
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
                <span className={cn(
                  'shrink-0 font-medium',
                  e.tone === 'primary' ? 'text-primary'
                    : e.tone === 'success' ? 'text-success'
                      : e.tone === 'warning' ? 'text-warning'
                        : 'text-muted-foreground',
                )}>
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
  const [totalWorkforce] = useState(15)
  const [activeMissions, setActiveMissions] = useState(0)
  const [totalTokens, setTotalTokens] = useState(0)
  const [totalRequests, setTotalRequests] = useState(0)
  const [loading, setLoading] = useState(true)
  const [workerStates, setWorkerStates] = useState<Record<string, WorkerState>>({})
  const [activities, setActivities] = useState<ActivityEntry[]>([])
  const prevStatesRef = useRef<Record<string, WorkerStatus>>({})
  const loggedCompletedRef = useRef<Set<string>>(new Set())
  // Monotonic request sequence — a slow poll response must never overwrite a
  // newer one (the 4s poll races against ~30s TTL backend responses).
  const loadSeqRef = useRef(0)

  const addActivity = useCallback((workerName: string, action: string, tone: ActivityEntry['tone'] = 'muted') => {
    const now = new Date()
    const timestamp = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    setActivities(prev => [...prev.slice(-49), {
      id: `${now.getTime()}-${Math.random().toString(36).slice(2, 7)}`,
      timestamp, workerName, action, tone,
    }])
  }, [])

  const loadData = useCallback(async () => {
    const requestId = ++loadSeqRef.current
    try {
      const [tasksRes, workersRes, usageRes] = await Promise.allSettled([
        apiClient.get<any[]>('/tasks?limit=50'),
        apiClient.get<any[]>('/runtime/workforce'),
        // Keep token/cost data consistent with Live Company.
        apiClient.get<any>('/api/usage/stats?days=30'),
      ])

      // A slow response from an older poll must never overwrite a newer one.
      if (requestId !== loadSeqRef.current) return

      const tasks = tasksRes.status === 'fulfilled' ? (tasksRes.value || []) : []
      const activeTasks = tasks.filter(
        (t: any) => !['completed', 'cancelled', 'failed', 'blocked'].includes(t.status),
      )
      setActiveMissions(activeTasks.length)

      const runtimeWorkers = workersRes.status === 'fulfilled' ? (workersRes.value || []) : []

      // Build worker states
      const newStates: Record<string, WorkerState> = {}
      const prevStates = prevStatesRef.current

      for (const w of WORKERS) {
        const hasActiveTask = activeTasks.some((t: any) =>
          t.worker_type === w.id || t.worker_type === w.name.toLowerCase(),
        )
        const task = activeTasks.find((t: any) =>
          t.worker_type === w.id || t.worker_type === w.name.toLowerCase(),
        )

        const result: WorkerState = { status: 'idle', task: '', progress: 0 }

        // QA-FIX: drop the `alwaysActive` fake-status branch. A worker only shows
        // "working" when there is a real dispatch targeting them (active task
        // matching worker_type) or the runtime worker reports busy/working.
        if (hasActiveTask && task) {
          result.status = 'working'
          result.task = task.title || task.description || 'Working on task'
          result.progress = typeof task.progress === 'number' ? task.progress : 0
        } else if (w.id === 'hermes' && activeTasks.length > 0) {
          // Hermes (System Dispatcher) coordinates any in-flight dispatch — only
          // "working" when there is genuinely a task routing through it.
          result.status = 'working'
          result.task = 'Dispatching tasks'
          result.progress = 0
        } else {
          const rtWorker = runtimeWorkers.find((rw: any) =>
            rw.id === w.id || rw.id === w.name.toLowerCase(),
          )
          if (rtWorker?.currentlyRunning) {
            result.status = 'working'
            const taskInfo = rtWorker.activeTaskInfo
            result.task = taskInfo?.taskTitle || rtWorker.task || 'Processing'
            result.progress = typeof taskInfo?.progress === 'number' ? taskInfo.progress : (typeof rtWorker.progress === 'number' ? rtWorker.progress : 0)
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

      // Log completed tasks — dedup by task ID to avoid repeated entries (BUG-10 fix)
      const completedTasks = tasks.filter((t: any) => t.status === 'completed')
      for (const ct of completedTasks) {
        const taskId = ct.id || ct.title || ''
        if (taskId && !loggedCompletedRef.current.has(taskId)) {
          loggedCompletedRef.current.add(taskId)
          const workerDef = WORKERS.find(w =>
            w.id === ct.worker_type || w.name.toLowerCase() === ct.worker_type,
          )
          if (workerDef) {
            addActivity(workerDef.name, `completed: ${(ct.title || 'task').slice(0, 40)}`, 'success')
          }
        }
      }

      prevStatesRef.current = Object.fromEntries(
        Object.entries(newStates).map(([k, v]) => [k, v.status]),
      )
      setWorkerStates(newStates)

      // Shared usage source with Live Company.
      if (usageRes.status === 'fulfilled' && usageRes.value) {
        setTotalTokens(usageRes.value.total_tokens || 0)
        setTotalRequests(usageRes.value.total_requests || 0)
      }
    } catch (e: unknown) {
      if (requestId === loadSeqRef.current) {
        setError(e instanceof Error ? e.message : String(e))
      }
    } finally {
      if (requestId === loadSeqRef.current) setLoading(false)
    }
  }, [addActivity])

  // Initial load
  useEffect(() => { loadData() }, [loadData])

  // Poll every 4 seconds
  useEffect(() => {
    const interval = setInterval(loadData, 4000)
    return () => clearInterval(interval)
  }, [loadData])

  // WS-1: Instant refresh AND activity logging when backend broadcasts worker events
  useEffect(() => {
    const wsRefreshRef = { current: null as ReturnType<typeof setTimeout> | null }
    const cleanup = connectWs(
      'general',  // Primary channel - dispatcher broadcasts here
      (msg) => {
        const m = msg as { type?: string; data?: any }
        if (!m?.type?.startsWith('worker.')) return
        
        // Extract relevant fields from worker event
        const eventType = m.type.split('.').pop()?.toLowerCase() || ''
        const taskTitle = m.data?.title || m.data?.task_title || ''
        const workerId = m.data?.worker_id || m.data?.worker_type || ''
        
        // Add activity entry immediately based on event type (no delay!)
        switch (eventType) {
          case 'started':
            addActivity(workerId || 'unknown', 'started working', 'primary')
            break
          case 'completed':
            addActivity(workerId || 'unknown', `completed: ${(taskTitle || '').slice(0, 40)}`, 'success')
            break
          case 'failed':
            addActivity(workerId || 'unknown', 'failed with error', 'error')
            break
          default:
            break
        }
        
        // Also refresh state via loadData
        if (wsRefreshRef.current) clearTimeout(wsRefreshRef.current)
        wsRefreshRef.current = setTimeout(() => { void loadData() }, 800)
      },
      () => { /* status changes ignored; polling is the fallback */ },
      [] // extraChannels - not needed since we only listen to general channel
    )
    return () => {
      if (wsRefreshRef.current) clearTimeout(wsRefreshRef.current)
      cleanup()
    }
  }, [loadData, addActivity])

  const workingCount = Object.values(workerStates).filter(s => s.status === 'working' || s.status === 'meeting').length

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      {/* Project header removed — showing under mission stats instead */}

      <PageHeader
        title="AIC Engineering Office"
        subtitle={loading ? 'Loading office…' : `${totalWorkforce} workers · ${workingCount} active · ${activeMissions} missions`}
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
              <Activity className="size-4 text-info" />
            </div>
            <div>
              <p className="text-lg font-bold leading-none">{totalRequests}</p>
              <p className="text-[10px] text-muted-foreground">Requests (30d)</p>
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
              <FileTree rootPath={projectRoot} onFileSelect={(path) => void window.aic?.openPath?.(path)?.catch(() => {})} />
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
                        state={workerStates[w.id] || { status: 'idle' as WorkerStatus, task: '', progress: 0 }}
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
