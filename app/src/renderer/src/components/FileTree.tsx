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

function filterNodes(nodes: DirTreeNode[], q: string): DirTreeNode[] {
  const lower = q.toLowerCase()
  return nodes.reduce<DirTreeNode[]>((acc, node) => {
    const nameMatch = node.name.toLowerCase().includes(lower)
    const children = node.children ? filterNodes(node.children, q) : []
    if (nameMatch || children.length > 0) {
      acc.push({ ...node, children: children.length > 0 ? children : node.children })
    }
    return acc
  }, [])
}

export function FileTree({ rootPath, onFileSelect, rootLabel, filter = '' }: { rootPath: string; onFileSelect: (path: string) => void; rootLabel?: string; filter?: string }) {
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

  const filteredTree = filter.trim() ? filterNodes(tree, filter) : tree

  if (loading) return <div className="px-3 py-2 text-[10px] text-muted-foreground/50">Loading…</div>
  if (!tree.length) return <div className="px-3 py-2 text-[10px] text-muted-foreground/50">Empty project</div>
  if (filter.trim() && !filteredTree.length) return <div className="px-3 py-2 text-[10px] text-muted-foreground/50">No files match “{filter.trim()}”</div>

  // Workspace → Project Folder → Files. The root label (project folder name) falls
  // back to the last path segment of the workspace root.
  const workspaceName =
    rootLabel ||
    rootPath.split('/').pop() ||
    rootPath.split('\\').pop() ||
    rootPath

  return (
    <div className="overflow-y-auto scroll-thin py-1">
      {/* Workspace root */}
      <div className="flex items-center gap-1.5 rounded px-2 py-1 text-[11px] font-semibold text-foreground">
        <Folder className="size-3 shrink-0 text-primary" />
        <span className="truncate">Workspace</span>
        <ChevronDown className="size-3 shrink-0 text-muted-foreground/60" />
      </div>
      {/* Project folder (child of Workspace) */}
      <div className="ml-2 border-l border-border/60 pl-1">
        <div className="flex items-center gap-1.5 rounded px-2 py-0.5 text-[11px] font-medium text-foreground/90">
          <Folder className="size-3 shrink-0 text-primary/80" />
          <span className="truncate">{workspaceName}</span>
        </div>
        {/* Files (leaves) */}
        <div className="ml-2 border-l border-border/60 pl-1">
          {filteredTree.map(node => <TreeNode key={node.path} node={node} depth={0} onSelect={onFileSelect} />)}
        </div>
      </div>
    </div>
  )
}
