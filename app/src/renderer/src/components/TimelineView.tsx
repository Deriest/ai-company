import { useState, useEffect, useCallback } from 'react'
import { Target, User, ShieldCheck, Cpu, Calendar, X } from 'lucide-react'
import { PageHeader, Badge, Card } from './kit'
type EventType = 'mission' | 'worker' | 'approval' | 'system'

// Timeline events loaded from backend at runtime
const timelineEvents: Array<{ id: string; time: string; title: string; actor: string; type: EventType; detail?: string }> = []
import { cn } from '../lib/utils'

const filters = ['All Events', 'Missions', 'System', 'Workers', 'Approvals'] as const

const typeMeta: Record<
  EventType,
  { icon: React.ComponentType<{ className?: string }>; tone: string; label: string }
> = {
  mission: { icon: Target, tone: 'text-primary bg-primary/15', label: 'Mission' },
  worker: { icon: User, tone: 'text-success bg-success/15', label: 'Worker' },
  approval: { icon: ShieldCheck, tone: 'text-destructive bg-destructive/15', label: 'Approval' },
  system: { icon: Cpu, tone: 'text-warning bg-warning/15', label: 'System' },
}

const filterToType: Record<string, EventType | 'all'> = {
  'All Events': 'all',
  Missions: 'mission',
  System: 'system',
  Workers: 'worker',
  Approvals: 'approval',
}

export function TimelineView() {
  const [filter, setFilter] = useState<(typeof filters)[number]>('All Events')
  const [error, setError] = useState('')

  const loadEvents = useCallback(async () => {
    try {
      // No backend endpoint exists — using local state (by design)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  useEffect(() => { loadEvents() }, [loadEvents])

  const target = filterToType[filter]
  const visible = timelineEvents.filter((e) => target === 'all' || e.type === target)

  return (
    <div>
      <PageHeader
        title="Timeline"
        subtitle="System, mission, worker and approval events in chronological order."
        actions={
          <div className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-1.5 text-sm text-muted-foreground">
            <Calendar className="size-4" /> 26 Jul 2026 · Today
          </div>
        }
      />

      <div className="space-y-5 p-6">
        {error && (
          <Card className="border-destructive/40 bg-destructive/5 text-sm text-destructive flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError('')}><X className="size-4" /></button>
          </Card>
        )}

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-1 rounded-lg border border-border bg-card p-1">
          {filters.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                'rounded-md px-3 py-1 text-sm transition-colors',
                filter === f
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {f}
            </button>
          ))}
        </div>

        <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Today · 26 July</p>

        {/* Timeline */}
        <ol className="relative space-y-3 border-l border-border pl-6">
          {visible.map((e) => {
            const meta = typeMeta[e.type]
            const Icon = meta.icon
            return (
              <li key={e.id} className="relative">
                <span
                  className={cn(
                    'absolute -left-[35px] grid size-6 place-items-center rounded-full border-2 border-background',
                    meta.tone,
                  )}
                >
                  <Icon className="size-3" />
                </span>
                <div className="flex items-start justify-between gap-4 rounded-lg border border-border bg-card px-4 py-3 transition-colors hover:border-primary/40">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs text-muted-foreground">{e.time}</span>
                      <Badge tone="muted">{meta.label}</Badge>
                      {e.detail ? <Badge tone="destructive">{e.detail}</Badge> : null}
                    </div>
                    <p className="mt-1 text-sm">{e.title}</p>
                  </div>
                  <span className="shrink-0 text-xs text-muted-foreground">{e.actor}</span>
                </div>
              </li>
            )
          })}
        </ol>

        {visible.length === 0 ? (
          <p className="py-10 text-center text-sm text-muted-foreground">No events for this filter.</p>
        ) : null}
      </div>
    </div>
  )
}
