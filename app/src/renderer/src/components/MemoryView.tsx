import { useState, useEffect, useCallback } from 'react'
import { Plus, Search, Trash2, Archive, X } from 'lucide-react'
import { Card, PageHeader, Badge } from './kit'
import { cn } from '../lib/utils'
import {
  memoryApi,
  type MemoryEntryRecord,
  type MemoryStats,
  type MemoryScope,
  type MemoryCategory,
} from '../lib/api/memory'

const scopes: MemoryScope[] = ['session', 'conversation', 'workspace', 'project', 'user']
const categories: MemoryCategory[] = ['fact', 'preference', 'context', 'summary']

export function MemoryView() {
  const [entries, setEntries] = useState<MemoryEntryRecord[]>([])
  const [stats, setStats] = useState<MemoryStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Store form
  const [showStore, setShowStore] = useState(false)
  const [storeScope, setStoreScope] = useState<MemoryScope>('workspace')
  const [storeKey, setStoreKey] = useState('')
  const [storeValue, setStoreValue] = useState('')
  const [storeCategory, setStoreCategory] = useState<MemoryCategory>('fact')
  const [storeImportance, setStoreImportance] = useState(5)

  // Retrieve filters
  const [retScope, setRetScope] = useState<MemoryScope>('workspace')
  const [retCategory, setRetCategory] = useState<MemoryCategory | ''>('')

  // Compress
  const [compressScope, setCompressScope] = useState<MemoryScope>('workspace')

  const loadEntries = useCallback(async () => {
    try {
      const params: { scope: MemoryScope; category?: MemoryCategory } = { scope: retScope }
      if (retCategory) params.category = retCategory
      const data = await memoryApi.retrieve(params)
      setEntries(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [retScope, retCategory])

  const loadStats = useCallback(async () => {
    try {
      const data = await memoryApi.stats()
      setStats(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  useEffect(() => {
    loadEntries()
    loadStats()
  }, [loadEntries, loadStats])

  const handleStore = async () => {
    if (!storeKey.trim()) return
    setLoading(true)
    setError(null)
    try {
      let parsedValue: unknown
      try { parsedValue = JSON.parse(storeValue) } catch { parsedValue = storeValue }
      await memoryApi.store({
        scope: storeScope,
        key: storeKey,
        value: parsedValue,
        category: storeCategory,
        importance: storeImportance,
      })
      setShowStore(false)
      setStoreKey('')
      setStoreValue('')
      await loadEntries()
      await loadStats()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const handleForget = async (id: string) => {
    try {
      await memoryApi.forget(id)
      await loadEntries()
      await loadStats()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const handleCompress = async () => {
    setLoading(true)
    setError(null)
    try {
      await memoryApi.compress({ scope: compressScope })
      await loadEntries()
      await loadStats()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Memory"
        subtitle="Store, retrieve, and manage agent memory entries across scopes."
        actions={
          <button
            onClick={() => setShowStore(true)}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="size-4" /> Store Memory
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

        {/* Stats */}
        {stats && (
          <div className="grid gap-4 sm:grid-cols-3">
            <Card>
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Total Entries</p>
              <p className="mt-1 text-2xl font-bold">{stats.total_entries}</p>
            </Card>
            <Card>
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Avg Importance</p>
              <p className="mt-1 text-2xl font-bold">{stats.avg_importance.toFixed(1)}</p>
            </Card>
            <Card>
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Total Accesses</p>
              <p className="mt-1 text-2xl font-bold">{stats.total_accesses}</p>
            </Card>
          </div>
        )}

        {/* Store form */}
        {showStore && (
          <Card className="space-y-3">
            <h3 className="text-sm font-semibold">Store Memory</h3>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Scope</label>
                <select
                  value={storeScope}
                  onChange={(e) => setStoreScope(e.target.value as MemoryScope)}
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                >
                  {scopes.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Key</label>
                <input
                  value={storeKey}
                  onChange={(e) => setStoreKey(e.target.value)}
                  placeholder="Memory key"
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                />
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Category</label>
                <select
                  value={storeCategory}
                  onChange={(e) => setStoreCategory(e.target.value as MemoryCategory)}
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                >
                  {categories.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div className="sm:col-span-2">
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Value</label>
                <textarea
                  value={storeValue}
                  onChange={(e) => setStoreValue(e.target.value)}
                  rows={3}
                  placeholder="Memory value (JSON or text)"
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 font-mono text-xs outline-none focus:border-primary"
                />
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Importance (1-10)</label>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={storeImportance}
                  onChange={(e) => setStoreImportance(Number(e.target.value))}
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleStore}
                disabled={loading}
                className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {loading ? 'Storing...' : 'Store'}
              </button>
              <button onClick={() => setShowStore(false)} className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-muted">
                Cancel
              </button>
            </div>
          </Card>
        )}

        {/* Retrieve filters + Compress */}
        <Card className="flex flex-wrap items-end gap-3">
          <div>
            <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Scope</label>
            <select
              value={retScope}
              onChange={(e) => setRetScope(e.target.value as MemoryScope)}
              className="mt-1 rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
            >
              {scopes.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Category</label>
            <select
              value={retCategory}
              onChange={(e) => setRetCategory(e.target.value as MemoryCategory | '')}
              className="mt-1 rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
            >
              <option value="">All</option>
              {categories.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <button onClick={loadEntries} className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted">
            <Search className="size-4" /> Retrieve
          </button>
          <div className="ml-auto flex items-end gap-2">
            <div>
              <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Compress Scope</label>
              <select
                value={compressScope}
                onChange={(e) => setCompressScope(e.target.value as MemoryScope)}
                className="mt-1 rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
              >
                {scopes.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <button
              onClick={handleCompress}
              disabled={loading}
              className="inline-flex items-center gap-1 rounded-md border border-warning/50 px-3 py-1.5 text-sm text-warning hover:bg-warning/10 disabled:opacity-50"
            >
              <Archive className="size-4" /> Compress
            </button>
          </div>
        </Card>

        {/* Memory entries */}
        <div className="space-y-2">
          {entries.length === 0 && <p className="text-xs text-muted-foreground">No memories found for this scope/category.</p>}
          {entries.map((entry) => (
            <Card key={entry.id} className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{entry.key}</span>
                  <Badge tone="muted">{entry.scope}</Badge>
                  {entry.category && <Badge tone="primary">{entry.category}</Badge>}
                  <Badge tone="warning">Importance: {entry.importance}</Badge>
                </div>
                <pre className="mt-1 text-xs font-mono text-muted-foreground overflow-x-auto max-h-24 overflow-y-auto">
                  {typeof entry.value === 'string' ? entry.value : JSON.stringify(entry.value, null, 2)}
                </pre>
                <div className="mt-1 flex items-center gap-3 text-[10px] text-muted-foreground">
                  <span>Accessed: {entry.accessCount}x</span>
                  {entry.accessedAt && <span>Last: {new Date(entry.accessedAt).toLocaleString()}</span>}
                </div>
              </div>
              <button
                onClick={() => handleForget(entry.id)}
                className="inline-flex items-center gap-1 rounded-md border border-destructive/40 px-2 py-1 text-xs text-destructive hover:bg-destructive/10 shrink-0"
              >
                <Trash2 className="size-3" /> Forget
              </button>
            </Card>
          ))}
        </div>
      </div>
    </div>
  )
}
