import { useState, useEffect } from 'react'
import { Card, PageHeader, Badge } from './kit'
import { cn } from '../lib/utils'
import { apiClient } from '../lib/api/client'
import {
  Users, Cpu, Shield, Code, Palette, Database,
  Server, BookOpen, Search, Zap, TestTube2,
  GitBranch, Lock, Rocket, Gauge, LayoutDashboard,
  UserCog, Brain, Coins,
} from 'lucide-react'

// ── Workforce data (canonical 15 workers × 4 departments) ──

interface WorkerDef {
  id: string
  name: string
  role: string
  tier: 'thinker' | 'crafter' | 'sprinter'
  phase: string
  icon: React.ComponentType<{ className?: string }>
}

interface Department {
  name: string
  color: string
  workers: WorkerDef[]
}

const DEPARTMENTS: Department[] = [
  {
    name: 'Leadership',
    color: 'text-primary',
    workers: [
      { id: 'hermes', name: 'Hermes', role: 'System Dispatcher', tier: 'thinker', phase: 'All', icon: Brain },
      { id: 'rex', name: 'Rex', role: 'Governor / Compliance', tier: 'sprinter', phase: 'Closeout', icon: Shield },
    ],
  },
  {
    name: 'Product',
    color: 'text-warning',
    workers: [
      { id: 'pm', name: 'Aria', role: 'Project Manager', tier: 'thinker', phase: 'Discovery–Closeout', icon: UserCog },
      { id: 'research', name: 'Sage', role: 'Researcher', tier: 'thinker', phase: 'Investigate', icon: Search },
      { id: 'designer', name: 'Luna', role: 'UI/UX Designer', tier: 'thinker', phase: 'Planning', icon: Palette },
      { id: 'documentation', name: 'Echo', role: 'Technical Writer', tier: 'crafter', phase: 'Closeout', icon: BookOpen },
    ],
  },
  {
    name: 'Engineering',
    color: 'text-success',
    workers: [
      { id: 'architect', name: 'Atlas', role: 'Software Architect', tier: 'thinker', phase: 'Planning', icon: LayoutDashboard },
      { id: 'backend', name: 'Hugo', role: 'Backend Engineer', tier: 'crafter', phase: 'Implementation', icon: Server },
      { id: 'frontend', name: 'Leo', role: 'Frontend Engineer', tier: 'crafter', phase: 'Implementation', icon: Code },
      { id: 'qa', name: 'Eve', role: 'QA Engineer', tier: 'crafter', phase: 'Verification', icon: TestTube2 },
      { id: 'performance', name: 'Pulse', role: 'Performance Engineer', tier: 'crafter', phase: 'Verification', icon: Gauge },
    ],
  },
  {
    name: 'Platform',
    color: 'text-info',
    workers: [
      { id: 'database', name: 'Nova', role: 'Database Engineer', tier: 'crafter', phase: 'Planning–Impl', icon: Database },
      { id: 'nexus', name: 'Nexus', role: 'Integration Engineer', tier: 'crafter', phase: 'Planning', icon: GitBranch },
      { id: 'flint', name: 'Flint', role: 'Infrastructure Engineer', tier: 'crafter', phase: 'Planning', icon: Rocket },
      { id: 'security', name: 'Sentinel', role: 'Security Engineer', tier: 'thinker', phase: 'Planning', icon: Lock },
    ],
  },
]

const tierColors: Record<string, string> = {
  thinker: 'bg-primary/20 text-primary',
  crafter: 'bg-success/20 text-success',
  sprinter: 'bg-warning/20 text-warning',
}

// ── Component ──────────────────────────────────────────

interface LiveCompanyViewProps {
  onWorkerSelect?: (workerId: string) => void
}

export function LiveCompanyView({ onWorkerSelect }: LiveCompanyViewProps) {
  const [selectedWorker, setSelectedWorker] = useState<WorkerDef | null>(null)
  const [workerStats, setWorkerStats] = useState<Record<string, any>>({})
  const [usageStats, setUsageStats] = useState<{ total_tokens: number; total_cost: number; total_requests: number } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Fetch worker runtime stats
    apiClient.get<any[]>('/runtime/workers')
      .then((workers) => {
        const stats: Record<string, any> = {}
        for (const w of workers || []) {
          stats[w.role] = {
            isEnabled: w.isEnabled,
            modelId: w.modelId,
            metrics: w.metrics,
          }
        }
        setWorkerStats(stats)
      })
      .catch(() => { /* graceful */ })
      .finally(() => setLoading(false))

    // Fetch usage/token cost stats
    apiClient.get<any>('/api/usage/stats?days=30')
      .then((data) => {
        setUsageStats({
          total_tokens: data.total_tokens || 0,
          total_cost: data.total_cost || 0,
          total_requests: data.total_requests || 0,
        })
      })
      .catch(() => { /* graceful — usage is optional */ })
  }, [])

  useEffect(() => {
    const interval = setInterval(() => {
      apiClient.get<any[]>('/runtime/workers')
        .then((workers) => {
          const stats: Record<string, any> = {}
          for (const w of workers || []) {
            stats[w.role] = {
              isEnabled: w.isEnabled,
              modelId: w.modelId,
              metrics: w.metrics,
            }
          }
          setWorkerStats(stats)
        })
        .catch(() => {})
    }, 30000)
    return () => clearInterval(interval)
  }, [])

  const handleSelect = (worker: WorkerDef) => {
    setSelectedWorker(worker)
    onWorkerSelect?.(worker.id)
  }

  return (
    <div className="flex min-h-full">
      {/* Main: Org Chart */}
      <div className="min-w-0 flex-1">
        <PageHeader
          title="Engineering Workforce"
          subtitle="15 specialized AI workers across 4 departments"
        />

        {/* Token Cost Summary */}
        {usageStats && (
          <div className="grid grid-cols-3 gap-3 px-6 pt-4">
            <Card className="flex items-center gap-3">
              <div className="grid size-9 place-items-center rounded-lg bg-primary/15">
                <Coins className="size-4 text-primary" />
              </div>
              <div>
                <p className="text-lg font-bold leading-none">${usageStats.total_cost.toFixed(2)}</p>
                <p className="text-[10px] text-muted-foreground">Total Cost (30d)</p>
              </div>
            </Card>
            <Card className="flex items-center gap-3">
              <div className="grid size-9 place-items-center rounded-lg bg-success/15">
                <Zap className="size-4 text-success" />
              </div>
              <div>
                <p className="text-lg font-bold leading-none">{(usageStats.total_tokens / 1000).toFixed(0)}k</p>
                <p className="text-[10px] text-muted-foreground">Tokens Used (30d)</p>
              </div>
            </Card>
            <Card className="flex items-center gap-3">
              <div className="grid size-9 place-items-center rounded-lg bg-warning/15">
                <Cpu className="size-4 text-warning" />
              </div>
              <div>
                <p className="text-lg font-bold leading-none">{usageStats.total_requests}</p>
                <p className="text-[10px] text-muted-foreground">LLM Requests (30d)</p>
              </div>
            </Card>
          </div>
        )}

        <div className="space-y-6 p-6">
          {DEPARTMENTS.map((dept) => (
            <div key={dept.name}>
              <div className="mb-3 flex items-center gap-2">
                <Users className={cn('size-4', dept.color)} />
                <h2 className={cn('text-sm font-semibold', dept.color)}>
                  {dept.name}
                </h2>
                <span className="text-xs text-muted-foreground">
                  ({dept.workers.length} workers)
                </span>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {dept.workers.map((worker) => {
                  const stats = workerStats[worker.id] || {}
                  const isActive = stats.isEnabled !== false
                  const isSelected = selectedWorker?.id === worker.id
                  const Icon = worker.icon

                  return (
                    <button
                      key={worker.id}
                      onClick={() => handleSelect(worker)}
                      className={cn(
                        'flex flex-col gap-3 rounded-xl border p-4 text-left transition-all',
                        isSelected
                          ? 'border-primary bg-primary/5 ring-1 ring-primary/30'
                          : 'border-border bg-card hover:border-primary/30 hover:bg-muted/50'
                      )}
                    >
                      <div className="flex items-center gap-3">
                        <div className={cn(
                          'grid size-10 place-items-center rounded-lg',
                          isActive ? 'bg-success/15' : 'bg-muted',
                        )}>
                          <Icon className={cn('size-5', isActive ? dept.color : 'text-muted-foreground')} />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-semibold">{worker.name}</p>
                          <p className="truncate text-[11px] text-muted-foreground">{worker.role}</p>
                        </div>
                        <span className={cn(
                          'size-2 rounded-full',
                          isActive ? 'bg-success' : 'bg-muted-foreground/40'
                        )} />
                      </div>

                      <div className="flex items-center gap-2">
                        <span className={cn('rounded px-1.5 py-0.5 text-[10px] font-medium', tierColors[worker.tier])}>
                          {worker.tier}
                        </span>
                        <span className="text-[10px] text-muted-foreground">
                          {worker.phase}
                        </span>
                        {stats.metrics && (
                          <span className="ml-auto text-[10px] text-muted-foreground">
                            {stats.metrics.totalExecutions || 0} tasks
                          </span>
                        )}
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Side Panel: Worker Detail */}
      {selectedWorker && (
        <aside className="hidden w-80 shrink-0 border-l border-border bg-sidebar lg:block">
          <WorkerDetail
            worker={selectedWorker}
            stats={workerStats[selectedWorker.id] || {}}
            onClose={() => setSelectedWorker(null)}
          />
        </aside>
      )}
    </div>
  )
}

// ── Worker Detail Panel ────────────────────────────────

function WorkerDetail({
  worker,
  stats,
  onClose,
}: {
  worker: WorkerDef
  stats: any
  onClose: () => void
}) {
  const Icon = worker.icon
  const metrics = stats.metrics || {}

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between border-b border-border px-4 py-4">
        <div className="flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-lg bg-primary/15">
            <Icon className="size-5 text-primary" />
          </div>
          <div>
            <h2 className="text-sm font-semibold">{worker.name}</h2>
            <p className="text-[11px] text-muted-foreground">{worker.role}</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="text-muted-foreground hover:text-foreground"
        >
          ×
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Identity */}
        <Card>
          <h3 className="text-xs font-semibold text-muted-foreground mb-2">Identity</h3>
          <div className="space-y-1.5 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Agent ID</span>
              <code className="text-xs font-mono">{worker.id}</code>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Model Tier</span>
              <Badge tone={worker.tier === 'thinker' ? 'primary' : worker.tier === 'crafter' ? 'success' : 'warning'}>
                {worker.tier}
              </Badge>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Active Phase</span>
              <span className="text-xs">{worker.phase}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Status</span>
              <span className={cn('text-xs', stats.isEnabled !== false ? 'text-success' : 'text-muted-foreground')}>
                {stats.isEnabled !== false ? 'Online' : 'Disabled'}
              </span>
            </div>
          </div>
        </Card>

        {/* Runtime Config */}
        {stats.modelId && (
          <Card>
            <h3 className="text-xs font-semibold text-muted-foreground mb-2">Runtime</h3>
            <div className="space-y-1.5 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Model</span>
                <code className="text-xs font-mono truncate max-w-[140px]">{stats.modelId}</code>
              </div>
            </div>
          </Card>
        )}

        {/* Performance Metrics */}
        <Card>
          <h3 className="text-xs font-semibold text-muted-foreground mb-2">Performance</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="text-center">
              <p className="text-lg font-bold">{metrics.totalExecutions || 0}</p>
              <p className="text-[10px] text-muted-foreground">Total Tasks</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-bold">{metrics.completed || 0}</p>
              <p className="text-[10px] text-muted-foreground">Completed</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-bold text-destructive">{metrics.errors || 0}</p>
              <p className="text-[10px] text-muted-foreground">Errors</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-bold">{metrics.avgLatencyMs ? `${(metrics.avgLatencyMs / 1000).toFixed(1)}s` : '—'}</p>
              <p className="text-[10px] text-muted-foreground">Avg Latency</p>
            </div>
          </div>
        </Card>

        {/* Pipeline Phase */}
        <Card>
          <h3 className="text-xs font-semibold text-muted-foreground mb-2">Pipeline Role</h3>
          <div className="flex flex-wrap gap-1">
            {['Discovery', 'Investigate', 'Planning', 'Implementation', 'Verification', 'Closeout'].map((phase) => {
              const isActive = worker.phase.toLowerCase().includes(phase.toLowerCase().slice(0, 4))
              return (
                <span
                  key={phase}
                  className={cn(
                    'rounded px-2 py-1 text-[10px] font-medium',
                    isActive ? 'bg-primary/20 text-primary' : 'bg-muted text-muted-foreground/50'
                  )}
                >
                  {phase}
                </span>
              )
            })}
          </div>
        </Card>
      </div>
    </div>
  )
}
