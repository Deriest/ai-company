import { cn } from '../lib/utils'

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string
  subtitle?: string
  actions?: React.ReactNode
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border px-6 py-5">
      <div className="min-w-0">
        <h1 className="text-lg font-semibold text-balance">{title}</h1>
        {subtitle ? (
          <p className="mt-0.5 text-sm text-muted-foreground text-pretty">{subtitle}</p>
        ) : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  )
}

export function Card({
  className,
  children,
}: {
  className?: string
  children: React.ReactNode
}) {
  return (
    <div
      className={cn(
        'rounded-xl border border-border bg-card p-3 shadow-sm',
        className,
      )}
    >
      {children}
    </div>
  )
}

export function ProgressBar({
  value,
  className,
  tone = 'primary',
}: {
  value: number
  className?: string
  tone?: 'primary' | 'success' | 'warning'
}) {
  const tones = {
    primary: 'bg-primary',
    success: 'bg-success',
    warning: 'bg-warning',
  }
  return (
    <div className={cn('h-1.5 w-full overflow-hidden rounded-full bg-muted', className)}>
      <div
        className={cn('h-full rounded-full', tones[tone])}
        style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
      />
    </div>
  )
}

type BadgeTone = 'primary' | 'success' | 'warning' | 'destructive' | 'muted'

export function Badge({
  children,
  tone = 'muted',
  className,
}: {
  children: React.ReactNode
  tone?: BadgeTone
  className?: string
}) {
  const tones: Record<BadgeTone, string> = {
    primary: 'bg-primary/15 text-primary border-primary/30',
    success: 'bg-success/15 text-success border-success/30',
    warning: 'bg-warning/15 text-warning border-warning/30',
    destructive: 'bg-destructive/15 text-destructive border-destructive/30',
    muted: 'bg-muted text-muted-foreground border-border',
  }
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium',
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}

export function Avatar({
  initial,
  className,
}: {
  initial: string
  className?: string
}) {
  return (
    <div
      className={cn(
        'grid size-9 shrink-0 place-items-center rounded-lg bg-accent text-sm font-semibold text-accent-foreground',
        className,
      )}
    >
      {initial}
    </div>
  )
}
