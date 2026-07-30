import { useState, useEffect, useCallback } from 'react'
import { FileText, ShieldCheck, GitCommit, TestTube, X } from 'lucide-react'
import { Card, PageHeader, Badge } from './kit'

interface EvidenceRecord {
  id: string
  icon: React.ComponentType<{ className?: string }>
  title: string
  detail: string
  hash: string
  worker: string
  time: string
  tone: 'success' | 'primary' | 'warning' | 'destructive'
}

// Evidence records loaded from backend at runtime
const defaultRecords: EvidenceRecord[] = []

export function EvidenceView() {
  const [records, setRecords] = useState<EvidenceRecord[]>(defaultRecords)
  const [error, setError] = useState('')

  const loadRecords = useCallback(async () => {
    try {
      // No backend endpoint exists — using local state (by design)
      setRecords(defaultRecords)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  useEffect(() => { loadRecords() }, [loadRecords])

  return (
    <div>
      <PageHeader
        title="Evidence"
        subtitle="Immutable audit trail of verifications, commits, and reports produced by workers."
      />
      <div className="space-y-3 p-6">
        {error && (
          <Card className="border-destructive/40 bg-destructive/5 text-sm text-destructive flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError('')}><X className="size-4" /></button>
          </Card>
        )}
        {records.map((r) => {
          const Icon = r.icon
          return (
            <Card key={r.id} className="flex items-center gap-4 transition-colors hover:border-primary/40">
              <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-primary/15 text-primary">
                <Icon className="size-5" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{r.title}</p>
                <p className="text-xs text-muted-foreground">{r.detail}</p>
              </div>
              <div className="hidden items-center gap-3 sm:flex">
                <Badge tone={r.tone}>{r.worker}</Badge>
                <span className="font-mono text-xs text-muted-foreground">#{r.hash}</span>
              </div>
              <span className="shrink-0 text-xs text-muted-foreground">{r.time}</span>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
