/**
 * WorkflowSelector — task-type picker cards + progress stepper + mode banner.
 *
 * Renders the backend workflow types (WORKFLOW_PLANS) as selectable cards so
 * users can explicitly choose a pipeline (Build / Fix Bug / Audit / Refactor /
 * Test / Research / Docs / Infra). Also exposes a WorkflowStepper that shows
 * ONLY the phases a given workflow runs, and a WorkflowModeBanner that surfaces
 * the currently selected mode above the composer.
 */
import { memo, useState } from 'react'
import {
  Hammer, Bug, ScanSearch, Sparkles, TestTube, BookOpen, Search, Server,
  Check, Loader2, ChevronDown, X,
} from 'lucide-react'
import { cn } from '../lib/utils'
import {
  WORKFLOWS, primaryWorkflows, secondaryWorkflows, getWorkflow,
  WORKFLOW_PHASES, PHASE_LABELS, derivePhaseIndex,
  type WorkflowDef, type ExecutionPhase,
} from '../lib/workflows'
import type { WorkflowType } from '../lib/api/chat'

// ── Icon + accent maps (literal classes so Tailwind keeps them) ──

const ICON_MAP: Record<WorkflowDef['icon'], React.ComponentType<{ className?: string }>> = {
  hammer: Hammer,
  bug: Bug,
  scan: ScanSearch,
  sparkles: Sparkles,
  test: TestTube,
  book: BookOpen,
  search: Search,
  server: Server,
}

const ACCENT_MAP: Record<WorkflowDef['icon'], { text: string; ring: string; bg: string }> = {
  hammer: { text: 'text-primary', ring: 'border-primary/40', bg: 'bg-primary/10' },
  bug: { text: 'text-destructive', ring: 'border-destructive/40', bg: 'bg-destructive/10' },
  scan: { text: 'text-warning', ring: 'border-warning/40', bg: 'bg-warning/10' },
  sparkles: { text: 'text-success', ring: 'border-success/40', bg: 'bg-success/10' },
  test: { text: 'text-info', ring: 'border-info/40', bg: 'bg-info/10' },
  book: { text: 'text-muted-foreground', ring: 'border-border', bg: 'bg-muted/40' },
  search: { text: 'text-primary', ring: 'border-primary/40', bg: 'bg-primary/10' },
  server: { text: 'text-info', ring: 'border-info/40', bg: 'bg-info/10' },
}

// ── Card grid ─────────────────────────────────────────────

/**
 * Grid of workflow cards. `detailed` shows longer descriptions (onboarding);
 * the default compact layout fits the Command Center panel.
 */
export const WorkflowSelector = memo(function WorkflowSelector({
  selected,
  onSelect,
  detailed = false,
}: {
  selected: WorkflowType | null
  onSelect: (wf: WorkflowDef) => void
  detailed?: boolean
}) {
  const [showMore, setShowMore] = useState(false)
  const primary = primaryWorkflows()
  const secondary = secondaryWorkflows()
  const visible = showMore ? WORKFLOWS : primary

  return (
    <div className="space-y-2">
      <div className={cn('grid gap-2', detailed ? 'grid-cols-1 sm:grid-cols-2' : 'grid-cols-2 lg:grid-cols-3')}>
        {visible.map(wf => {
          const Icon = ICON_MAP[wf.icon]
          const accent = ACCENT_MAP[wf.icon]
          const isSelected = selected === wf.type
          return (
            <button
              key={wf.type}
              type="button"
              onClick={() => onSelect(wf)}
              aria-pressed={isSelected}
              className={cn(
                'group relative flex flex-col items-start gap-1.5 rounded-lg border p-3 text-left transition-all',
                'hover:-translate-y-px hover:shadow-md focus:outline-none focus:ring-2 focus:ring-primary/40',
                isSelected
                  ? cn('border-primary/60 bg-primary/10 ring-1 ring-primary/40')
                  : 'border-border/60 bg-card/60 hover:border-border hover:bg-card',
              )}
            >
              <div className="flex w-full items-center gap-2">
                <span className={cn('grid size-6 shrink-0 place-items-center rounded-md', accent.bg)}>
                  <Icon className={cn('size-3.5', accent.text)} />
                </span>
                <span className="min-w-0 flex-1 truncate text-[12px] font-semibold text-foreground">{wf.label}</span>
                {isSelected && <Check className="size-3.5 shrink-0 text-primary" />}
              </div>
              <p className="text-[10px] leading-snug text-muted-foreground">
                {detailed ? wf.detail : wf.description}
              </p>
              {!detailed && (
                <p className="mt-auto truncate font-mono text-[9px] text-muted-foreground/50">
                  “{wf.example}”
                </p>
              )}
            </button>
          )
        })}
      </div>

      {!detailed && secondary.length > 0 && (
        <button
          type="button"
          onClick={() => setShowMore(s => !s)}
          className="flex items-center gap-1 rounded-md px-2 py-1 text-[10px] font-medium text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground"
        >
          <ChevronDown className={cn('size-3 transition-transform', showMore && 'rotate-180')} />
          {showMore ? 'Show fewer' : `More workflows (${secondary.length})`}
        </button>
      )}
    </div>
  )
})

// ── Progress stepper ──────────────────────────────────────

/**
 * Mini phase stepper for a running workflow. Shows ONLY the phases allowed for
 * the task type (mirrors backend WORKFLOW_PLANS) — a bugfix never shows the
 * Planning/Closeout steps. `activity` is a 0..1 progress signal derived from
 * stream activity (tool calls + content).
 */
export const WorkflowStepper = memo(function WorkflowStepper({
  type,
  status,
  activity,
}: {
  type: WorkflowType
  status: 'queued' | 'executing' | 'completed' | string
  activity: number
}) {
  const phases: ExecutionPhase[] = WORKFLOW_PHASES[type] ?? WORKFLOW_PHASES.build
  const activeIdx = derivePhaseIndex(type, status, activity)
  const isQueued = status === 'queued'
  const isDone = activeIdx >= phases.length

  if (isQueued) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 className="size-3 animate-spin" />
        <span>Queued — waiting for a free agent slot…</span>
      </div>
    )
  }

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        {isDone ? <Check className="size-3 text-success" /> : <Loader2 className="size-3 animate-spin text-primary" />}
        <span>
          {isDone
            ? 'Completed'
            : activeIdx >= 0
              ? `${PHASE_LABELS[phases[activeIdx]]}…`
              : 'Starting…'}
        </span>
      </div>
      {/* Phase dots + connectors */}
      <div className="flex items-center gap-1">
        {phases.map((ph, i) => {
          const done = isDone || i < activeIdx
          const active = !isDone && i === activeIdx
          return (
            <div key={ph} className="flex items-center gap-1" title={PHASE_LABELS[ph]}>
              <span
                className={cn(
                  'grid size-4 place-items-center rounded-full border text-[8px] font-semibold transition-colors',
                  done && 'border-success/60 bg-success/20 text-success',
                  active && 'border-primary/60 bg-primary/15 text-primary',
                  !done && !active && 'border-border/60 bg-muted/30 text-muted-foreground/40',
                )}
              >
                {done ? <Check className="size-2.5" /> : active ? <Loader2 className="size-2.5 animate-spin" /> : i + 1}
              </span>
              {i < phases.length - 1 && (
                <span className={cn('h-px w-3', done ? 'bg-success/40' : 'bg-border/60')} />
              )}
            </div>
          )
        })}
      </div>
      {/* Phase labels (only when few phases, to avoid clutter) */}
      {phases.length <= 4 && (
        <div className="flex items-center gap-1 text-[9px] text-muted-foreground/60">
          {phases.map((ph, i) => {
            const done = isDone || i < activeIdx
            const active = !isDone && i === activeIdx
            return (
              <span
                key={ph}
                className={cn(
                  'rounded px-1 py-0.5',
                  active ? 'bg-primary/10 text-primary' : done ? 'text-success/70' : '',
                )}
              >
                {PHASE_LABELS[ph]}
              </span>
            )
          })}
        </div>
      )}
    </div>
  )
})

// ── Mode banner ───────────────────────────────────────────

/**
 * Banner shown above the composer when a workflow mode is selected for the next
 * message. Surfaces the mode label, the pipeline it will run, and controls to
 * change or clear the mode.
 */
export const WorkflowModeBanner = memo(function WorkflowModeBanner({
  type,
  onChangeType,
  onClear,
}: {
  type: WorkflowType
  onChangeType: () => void
  onClear: () => void
}) {
  const wf = getWorkflow(type)
  if (!wf) return null
  const Icon = ICON_MAP[wf.icon]
  const accent = ACCENT_MAP[wf.icon]

  return (
    <div className="mb-2 flex items-center gap-2 rounded-md border border-border/60 bg-card/60 px-2.5 py-1.5">
      <span className={cn('grid size-5 shrink-0 place-items-center rounded', accent.bg)}>
        <Icon className={cn('size-3', accent.text)} />
      </span>
      <div className="min-w-0 flex-1">
        <span className="block truncate text-[11px] font-semibold text-foreground">
          Mode: {wf.label}
        </span>
        <span className="block truncate text-[9px] text-muted-foreground/70">{wf.pipeline}</span>
      </div>
      <button
        type="button"
        onClick={onChangeType}
        className="shrink-0 rounded border border-border/60 px-2 py-0.5 text-[10px] font-medium text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground"
      >
        Change type
      </button>
      <button
        type="button"
        onClick={onClear}
        aria-label="Clear workflow mode"
        className="shrink-0 rounded p-0.5 text-muted-foreground/60 transition-colors hover:bg-muted/50 hover:text-foreground"
      >
        <X className="size-3" />
      </button>
    </div>
  )
})
