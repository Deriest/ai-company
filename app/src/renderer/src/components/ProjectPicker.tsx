import { useState, useEffect } from 'react'
import { FolderOpen, ChevronDown, Check, FolderSearch } from 'lucide-react'
import { cn } from '../lib/utils'
import { projectsApi, type ProjectRecord } from '../lib/api/projects'

export function ProjectPicker({ onProjectChange }: { onProjectChange?: (project: ProjectRecord | null) => void }) {
  const [projects, setProjects] = useState<ProjectRecord[]>([])
  const [active, setActive] = useState<ProjectRecord | null>(null)
  const [open, setOpen] = useState(false)
  const [browsing, setBrowsing] = useState(false)

  useEffect(() => {
    projectsApi.list().then(setProjects).catch(() => {})
    projectsApi.getActive().then(setActive).catch(() => {})
  }, [])

  const handleSelect = async (project: ProjectRecord) => {
    try {
      await projectsApi.activate(project.id)
      setActive(project)
      setOpen(false)
      onProjectChange?.(project)
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
    } catch (e) { console.error('Browse failed', e) }
    finally { setBrowsing(false) }
  }

  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-[11px] hover:bg-muted/50">
        <FolderOpen className="size-3 text-muted-foreground" />
        <span className="flex-1 truncate text-left">{active?.name || 'No project'}</span>
        <ChevronDown className="size-3 text-muted-foreground" />
      </button>
      {open && (
        <div className="absolute top-full left-0 right-0 z-50 mt-1 rounded-lg border border-border bg-card shadow-lg">
          {projects.map(p => (
            <button key={p.id} onClick={() => handleSelect(p)}
              className={cn("flex w-full items-center gap-2 px-3 py-2 text-[11px] hover:bg-muted/50",
                p.id === active?.id && "bg-primary/10"
              )}>
              {p.id === active?.id && <Check className="size-3 text-primary" />}
              <span className="truncate">{p.name}</span>
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
