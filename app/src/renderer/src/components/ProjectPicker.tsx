import { useState, useEffect } from 'react'
import { FolderOpen, ChevronDown, Check, FolderSearch } from 'lucide-react'
import { cn } from '../lib/utils'
import { projectsApi, type ProjectRecord } from '../lib/api/projects'

/**
 * Project picker — used in the AppShell rail AND the Command Center sidebar.
 *
 * `refreshKey` re-fetches the active project so an activation anywhere in the
 * app (rail, Command Center, restore) is reflected immediately instead of only
 * on mount. `onActiveChange` notifies the parent when the active project loads,
 * so parents can send `project_id`/`workspace` with chat requests later.
 */
export function ProjectPicker({
  onProjectChange,
  onActiveChange,
  refreshKey = 0,
  fallbackLabel,
  fallbackPath,
  dropdownUp = false,
}: {
  onProjectChange?: (project: ProjectRecord | null) => void
  onActiveChange?: (project: ProjectRecord | null) => void
  refreshKey?: number
  fallbackLabel?: string | null
  fallbackPath?: string | null
  /** Open the menu above the trigger (use when the picker sits at the bottom). */
  dropdownUp?: boolean
}) {
  const [projects, setProjects] = useState<ProjectRecord[]>([])
  const [active, setActive] = useState<ProjectRecord | null>(null)
  const [open, setOpen] = useState(false)
  const [browsing, setBrowsing] = useState(false)

  useEffect(() => {
    projectsApi.list().then(setProjects).catch(() => {})
    projectsApi.getActive().then((p) => {
      setActive(p)
      onActiveChange?.(p)
    }).catch(() => {})
  }, [refreshKey]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSelect = async (project: ProjectRecord) => {
    try {
      await projectsApi.activate(project.id)
      setActive(project)
      setOpen(false)
      onProjectChange?.(project)
      onActiveChange?.(project)
    } catch (e) { console.error(e) }
  }

  const handleBrowse = async () => {
    if (!window.aic?.selectDirectory || browsing) return
    setBrowsing(true)
    try {
      const dirPath = await window.aic.selectDirectory()
      if (!dirPath) return
      const dirName = dirPath.split('/').pop() || dirPath.split('\\').pop() || dirPath
      const project = await projectsApi.create({ name: dirName, repo_path: dirPath })
      await projectsApi.activate(project.id)
      setProjects(prev => [...prev, project])
      setActive(project)
      setOpen(false)
      onProjectChange?.(project)
      onActiveChange?.(project)
    } catch (e) { console.error('Browse failed', e) }
    finally { setBrowsing(false) }
  }

  const label = active?.name || fallbackLabel || 'No project'
  const pathLabel = active?.repo_path || fallbackPath || ''

  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-[11px] hover:bg-muted/50 text-left">
        <FolderOpen className="size-3 text-muted-foreground shrink-0" />
        <span className="min-w-0 flex-1">
          <span className="block truncate">{label}</span>
          {pathLabel && <span className="block truncate font-mono text-[9px] text-muted-foreground/50">{pathLabel}</span>}
        </span>
        <ChevronDown className="size-3 text-muted-foreground shrink-0" />
      </button>
      {open && (
        <div className={cn(
          "absolute left-0 right-0 z-50 mt-1 rounded-lg border border-border bg-card shadow-lg",
          dropdownUp ? "bottom-full mb-1" : "top-full",
        )}>
          {projects.map(p => (
            <button key={p.id} onClick={() => handleSelect(p)}
              className={cn("flex w-full items-center gap-2 px-3 py-2 text-[11px] hover:bg-muted/50",
                p.id === active?.id && "bg-primary/10"
              )}>
              {p.id === active?.id && <Check className="size-3 text-primary" />}
              <span className="min-w-0 flex-1">
                <span className="block truncate">{p.name}</span>
                <span className="block truncate font-mono text-[9px] text-muted-foreground/40">{p.repo_path}</span>
              </span>
            </button>
          ))}
          {projects.length === 0 && <p className="border-b border-border px-3 py-2 text-[10px] text-muted-foreground">No saved projects yet</p>}
          <button onClick={handleBrowse} disabled={browsing}
            className="flex w-full items-center gap-2 border-t border-border px-3 py-2 text-[11px] text-primary hover:bg-muted/50 disabled:opacity-50">
            <FolderSearch className="size-3" />
            <span>{browsing ? 'Selecting…' : 'Browse…'}</span>
          </button>
        </div>
      )}
    </div>
  )
}