import { useState, useEffect, useCallback } from 'react'
import { ChevronRight, ChevronDown, Folder, File, FileCode, FileText, FileJson, Image } from 'lucide-react'
import { cn } from '../lib/utils'
import type { DirTreeNode } from '../types'

function getFileIcon(name: string) {
  const ext = name.split('.').pop()?.toLowerCase()
  if (['ts', 'tsx', 'js', 'jsx'].includes(ext || '')) return FileCode
  if (['json'].includes(ext || '')) return FileJson
  if (['md', 'txt'].includes(ext || '')) return FileText
  if (['png', 'jpg', 'svg', 'gif'].includes(ext || '')) return Image
  return File
}

function TreeNode({ node, depth, onSelect }: { node: DirTreeNode; depth: number; onSelect: (path: string) => void }) {
  const [expanded, setExpanded] = useState(depth < 2)
  const isDir = node.isDirectory
  const Icon = isDir ? Folder : getFileIcon(node.name)

  return (
    <div>
      <button
        onClick={() => { if (isDir) setExpanded(!expanded); else onSelect(node.path) }}
        className="flex w-full items-center gap-1.5 rounded px-2 py-0.5 text-[11px] hover:bg-muted/50 text-left"
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        {isDir ? (
          expanded ? <ChevronDown className="size-3 shrink-0 text-muted-foreground" /> : <ChevronRight className="size-3 shrink-0 text-muted-foreground" />
        ) : <span className="w-3" />}
        <Icon className={cn("size-3 shrink-0", isDir ? "text-primary/70" : "text-muted-foreground/60")} />
        <span className="truncate">{node.name}</span>
      </button>
      {isDir && expanded && node.children?.map(child => (
        <TreeNode key={child.path} node={child} depth={depth + 1} onSelect={onSelect} />
      ))}
    </div>
  )
}

export function FileTree({ rootPath, onFileSelect }: { rootPath: string; onFileSelect: (path: string) => void }) {
  const [tree, setTree] = useState<DirTreeNode[]>([])
  const [loading, setLoading] = useState(true)

  const loadTree = useCallback(async () => {
    try {
      const result = await window.aic?.readDirTree?.(rootPath)
      if (result) setTree(result)
    } catch (e) { console.error('Failed to load file tree', e) }
    finally { setLoading(false) }
  }, [rootPath])

  useEffect(() => { loadTree() }, [loadTree])

  // Poll for file changes every 5s.
  useEffect(() => {
    const id = setInterval(loadTree, 5000)
    return () => clearInterval(id)
  }, [loadTree])

  if (loading) return <div className="px-3 py-2 text-[10px] text-muted-foreground/50">Loading…</div>
  if (!tree.length) return <div className="px-3 py-2 text-[10px] text-muted-foreground/50">Empty project</div>

  return (
    <div className="overflow-y-auto scroll-thin py-1">
      {tree.map(node => <TreeNode key={node.path} node={node} depth={0} onSelect={onFileSelect} />)}
    </div>
  )
}
