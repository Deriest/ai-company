import { useState, useEffect, useCallback } from 'react'
import { Plus, RefreshCw, XCircle, Pause, Play, ChevronDown, ChevronUp, X } from 'lucide-react'
import { Card, PageHeader, Badge, ProgressBar } from './kit'
import { cn } from '../lib/utils'
import {
  jobsApi,
  type JobRecord,
  type JobDetail,
  type JobStatus,
  type JobType,
} from '../lib/api/jobs'

const statusTone: Record<JobStatus, 'muted' | 'primary' | 'success' | 'warning' | 'destructive'> = {
  queued: 'muted',
  running: 'primary',
  completed: 'success',
  failed: 'destructive',
  cancelled: 'destructive',
  paused: 'warning',
}

const statusFilters: { label: string; value: JobStatus | 'all' }[] = [
  { label: 'All', value: 'all' },
  { label: 'Queued', value: 'queued' },
  { label: 'Running', value: 'running' },
  { label: 'Completed', value: 'completed' },
  { label: 'Failed', value: 'failed' },
]

const jobTypes: JobType[] = ['orchestration', 'chat', 'tool', 'custom']

export function JobsView() {
  // Pagination: cap the initial fetch at PAGE_SIZE jobs and reveal more with the
  // "Load more" button (avoids rendering unbounded lists for large job history).
  const PAGE_SIZE = 100
  const [jobs, setJobs] = useState<JobRecord[]>([])
  const [filter, setFilter] = useState<JobStatus | 'all'>('all')
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [jobDetail, setJobDetail] = useState<JobDetail | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [limit, setLimit] = useState(PAGE_SIZE)

  // Create form
  const [newTitle, setNewTitle] = useState('')
  const [newType, setNewType] = useState<JobType>('custom')
  const [newPriority, setNewPriority] = useState(0)

  const loadJobs = useCallback(async () => {
    try {
      const params = filter !== 'all' ? { status: filter, limit } : { limit }
      const data = await jobsApi.list(params)
      setJobs(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [filter, limit])

  useEffect(() => { loadJobs() }, [loadJobs])

  const loadDetail = async (id: string) => {
    if (expandedId === id) {
      setExpandedId(null)
      setJobDetail(null)
      return
    }
    try {
      const detail = await jobsApi.get(id)
      setExpandedId(id)
      setJobDetail(detail)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const handleCreate = async () => {
    if (!newTitle.trim()) return
    setLoading(true)
    setError(null)
    try {
      await jobsApi.create({ title: newTitle, job_type: newType, priority: newPriority })
      setShowCreate(false)
      setNewTitle('')
      setNewType('custom')
      setNewPriority(0)
      await loadJobs()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const handleCancel = async (id: string) => {
    try {
      await jobsApi.cancel(id)
      await loadJobs()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const handlePause = async (id: string) => {
    try {
      await jobsApi.pause(id)
      await loadJobs()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const handleResume = async (id: string) => {
    try {
      await jobsApi.resume(id)
      await loadJobs()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div>
      <PageHeader
        title="Jobs"
        subtitle="Monitor and manage background jobs, queues, and task execution."
        actions={
          <button
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="size-4" /> New Job
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
            <h3 className="text-sm font-semibold">Create Job</h3>
            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Title</label>
                <input
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="Job title"
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                />
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Type</label>
                <select
                  value={newType}
                  onChange={(e) => setNewType(e.target.value as JobType)}
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                >
                  {jobTypes.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Priority</label>
                <input
                  type="number"
                  value={newPriority}
                  onChange={(e) => setNewPriority(Number(e.target.value))}
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                />
              </div>
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

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1 rounded-lg border border-border bg-card p-1">
            {statusFilters.map((f) => (
              <button
                key={f.value}
                onClick={() => { setFilter(f.value); setLimit(PAGE_SIZE) }}
                className={cn(
                  'rounded-md px-3 py-1 text-sm transition-colors',
                  filter === f.value ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground',
                )}
              >
                {f.label}
              </button>
            ))}
          </div>
          <button onClick={loadJobs} className="text-muted-foreground hover:text-foreground">
            <RefreshCw className="size-4" />
          </button>
        </div>

        {/* Job list */}
        <div className="space-y-2">
          {jobs.length === 0 && <p className="text-xs text-muted-foreground">No jobs found.</p>}
          {jobs.map((job) => (
            <Card key={job.id} className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <button
                    onClick={() => loadDetail(job.id)}
                    className="text-muted-foreground hover:text-foreground"
                  >
                    {expandedId === job.id ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
                  </button>
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{job.title}</p>
                    <p className="text-[10px] font-mono text-muted-foreground">{job.id}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone="muted">P{job.priority}</Badge>
                  <Badge tone="muted">{job.jobType}</Badge>
                  <Badge tone={statusTone[job.status]}>{job.status}</Badge>
                  <div className="flex gap-1">
                    {(job.status === 'queued' || job.status === 'running') && (
                      <button
                        onClick={() => handlePause(job.id)}
                        className="inline-flex items-center gap-1 rounded-md border border-warning/40 px-2 py-1 text-xs text-warning hover:bg-warning/10"
                        title="Pause"
                      >
                        <Pause className="size-3" />
                      </button>
                    )}
                    {job.status === 'paused' && (
                      <button
                        onClick={() => handleResume(job.id)}
                        className="inline-flex items-center gap-1 rounded-md border border-primary/40 px-2 py-1 text-xs text-primary hover:bg-primary/10"
                        title="Resume"
                      >
                        <Play className="size-3" />
                      </button>
                    )}
                    {(job.status === 'queued' || job.status === 'running' || job.status === 'paused') && (
                      <button
                        onClick={() => handleCancel(job.id)}
                        className="inline-flex items-center gap-1 rounded-md border border-destructive/40 px-2 py-1 text-xs text-destructive hover:bg-destructive/10"
                        title="Cancel"
                      >
                        <XCircle className="size-3" />
                      </button>
                    )}
                  </div>
                </div>
              </div>

              <ProgressBar value={job.progress} />

              {/* Expanded logs */}
              {expandedId === job.id && jobDetail && (
                <div className="mt-2 rounded-lg border border-border bg-background/50 p-3">
                  <h4 className="text-xs font-semibold mb-2">Logs</h4>
                  {jobDetail.logs.length === 0 ? (
                    <p className="text-xs text-muted-foreground">No logs yet.</p>
                  ) : (
                    <div className="space-y-1 max-h-60 overflow-y-auto">
                      {jobDetail.logs.map((log, i) => (
                        <div key={i} className="flex gap-2 text-xs font-mono">
                          <span className={cn(
                            'shrink-0',
                            log.level === 'error' ? 'text-destructive' : log.level === 'warn' ? 'text-warning' : 'text-muted-foreground',
                          )}>
                            [{log.level}]
                          </span>
                          <span className="text-foreground">{log.message}</span>
                          <span className="shrink-0 text-muted-foreground ml-auto">{new Date(log.createdAt).toLocaleTimeString()}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {jobDetail.result && (
                    <div className="mt-2">
                      <h4 className="text-xs font-semibold mb-1">Result</h4>
                      <pre className="text-xs font-mono text-muted-foreground overflow-x-auto">{JSON.stringify(jobDetail.result, null, 2)}</pre>
                    </div>
                  )}
                </div>
              )}
            </Card>
          ))}
          {jobs.length >= limit && (
            <button
              onClick={() => setLimit((l) => l + PAGE_SIZE)}
              className="w-full rounded-lg border border-border py-2 text-sm text-muted-foreground hover:bg-muted"
            >
              Load more
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
