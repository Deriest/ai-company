import { useState, useEffect, useCallback } from 'react'
import { Plus, Search, X, FolderOpen, Calendar, CheckCircle } from 'lucide-react'
import { Card, PageHeader, Badge } from './kit'
import { cn } from '../lib/utils'
import { projectsApi, ProjectRecord } from '../lib/api/projects'

const filters = ['All', 'Active', 'Archived'] as const

export function ProjectsView() {
  const [projects, setProjects] = useState<ProjectRecord[]>([])
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null)
  const [filter, setFilter] = useState<(typeof filters)[number]>('All')
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [formName, setFormName] = useState('')
  const [formDesc, setFormDesc] = useState('')
  const [formRepo, setFormRepo] = useState('')
  const [creating, setCreating] = useState(false)

  const loadProjects = useCallback(async () => {
    try {
      const data = await projectsApi.list()
      setProjects(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }

    try {
      const active = await projectsApi.getActive()
      setActiveProjectId(active?.id ?? null)
    } catch {
      setActiveProjectId(null)
    }
  }, [])

  useEffect(() => { loadProjects() }, [loadProjects])

  const handleCreate = async () => {
    if (!formName.trim()) return
    setCreating(true)
    try {
      await projectsApi.create({
        name: formName.trim(),
        description: formDesc.trim() || undefined,
        repo_path: formRepo.trim() || undefined,
      })
      setShowForm(false)
      setFormName('')
      setFormDesc('')
      setFormRepo('')
      await loadProjects()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setCreating(false)
    }
  }

  const handleActivate = async (id: string) => {
    try {
      await projectsApi.activate(id)
      setActiveProjectId(id)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const visible = projects.filter((p) => {
    const matchFilter = filter === 'All' || p.status === filter.toLowerCase()
    const matchQuery = p.name.toLowerCase().includes(query.toLowerCase())
    return matchFilter && matchQuery
  })

  return (
    <div>
      <PageHeader
        title="Projects"
        subtitle="Organize engineering work across projects."
        actions={
          <button
            onClick={() => setShowForm(!showForm)}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="size-4" /> New Project
          </button>
        }
      />

      <div className="space-y-5 p-6">
        {error && (
          <Card className="border-destructive/40 bg-destructive/5 text-sm text-destructive flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError('')}><X className="size-4" /></button>
          </Card>
        )}

        {showForm && (
          <Card className="border-primary/40">
            <h3 className="text-sm font-semibold mb-3">Create New Project</h3>
            <div className="space-y-3">
              <input
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="Project name *"
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              />
              <input
                value={formDesc}
                onChange={(e) => setFormDesc(e.target.value)}
                placeholder="Description (optional)"
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              />
              <input
                value={formRepo}
                onChange={(e) => setFormRepo(e.target.value)}
                placeholder="Repository path (optional)"
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              />
              <div className="flex gap-2">
                <button
                  onClick={handleCreate}
                  disabled={creating || !formName.trim()}
                  className="rounded-lg bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  {creating ? 'Creating...' : 'Create'}
                </button>
                <button
                  onClick={() => setShowForm(false)}
                  className="rounded-lg border border-border px-4 py-1.5 text-sm text-muted-foreground hover:text-foreground"
                >
                  Cancel
                </button>
              </div>
            </div>
          </Card>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1 rounded-lg border border-border bg-card p-1">
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

          <div className="flex min-w-52 flex-1 items-center gap-2 rounded-lg border border-border bg-card px-3 py-1.5">
            <Search className="size-4 text-muted-foreground" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search projects..."
              className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {visible.map((p) => {
            const isActive = p.id === activeProjectId
            return (
              <Card
                key={p.id}
                className={cn(
                  'flex flex-col gap-3 transition-colors hover:border-primary/40',
                  isActive && 'border-primary/60 ring-1 ring-primary/20',
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="grid size-10 place-items-center rounded-lg bg-primary/15 text-sm font-bold text-primary">
                      {p.name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase()}
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold leading-tight">{p.name}</h3>
                      <p className="text-xs text-muted-foreground">{p.slug}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {isActive && (
                      <Badge tone="success">Active</Badge>
                    )}
                    <Badge tone={p.status === 'active' ? 'success' : 'muted'}>{p.status}</Badge>
                  </div>
                </div>

                {p.description && (
                  <p className="text-xs text-muted-foreground line-clamp-2">{p.description}</p>
                )}

                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  {p.repo_path && (
                    <span className="flex items-center gap-1">
                      <FolderOpen className="size-3" /> {p.repo_path.split('/').pop()}
                    </span>
                  )}
                  <span className="flex items-center gap-1">
                    <Calendar className="size-3" /> {new Date(p.created_at).toLocaleDateString()}
                  </span>
                </div>

                <div className="mt-auto flex gap-2">
                  {!isActive && (
                    <button
                      onClick={() => handleActivate(p.id)}
                      className="flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground hover:border-primary/40"
                    >
                      <CheckCircle className="size-3" /> Set Active
                    </button>
                  )}
                </div>
              </Card>
            )
          })}
        </div>

        {visible.length === 0 ? (
          <p className="py-10 text-center text-sm text-muted-foreground">
            {projects.length === 0 ? 'No projects yet. Create one to get started.' : 'No projects match your filters.'}
          </p>
        ) : null}
      </div>
    </div>
  )
}
