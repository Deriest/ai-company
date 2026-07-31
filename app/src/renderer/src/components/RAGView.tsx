import { useState, useEffect, useCallback } from 'react'
import { Upload, Search, Trash2, RefreshCw, FileText, BookOpen, X } from 'lucide-react'
import { Card, PageHeader, Badge } from './kit'
import { cn } from '../lib/utils'
import {
  ragApi,
  type RagDocumentRecord,
  type RagRetrieveResult,
  type RagContextResult,
  type DocumentContentType,
} from '../lib/api/rag'

const contentTypes: DocumentContentType[] = ['text', 'pdf', 'markdown', 'code']

const statusTone: Record<string, 'muted' | 'primary' | 'success' | 'destructive' | 'warning'> = {
  loaded: 'muted',
  chunking: 'warning',
  embedding: 'primary',
  ready: 'success',
  error: 'destructive',
}

export function RAGView() {
  const [documents, setDocuments] = useState<RagDocumentRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Load document form
  const [showLoad, setShowLoad] = useState(false)
  const [loadTitle, setLoadTitle] = useState('')
  const [loadContent, setLoadContent] = useState('')
  const [loadSource, setLoadSource] = useState('')
  const [loadType, setLoadType] = useState<DocumentContentType>('text')

  // Retrieve form
  const [retrieveQuery, setRetrieveQuery] = useState('')
  const [retrieveTopK, setRetrieveTopK] = useState(5)
  const [retrieveResults, setRetrieveResults] = useState<RagRetrieveResult[] | null>(null)

  // Context builder
  const [contextQuery, setContextQuery] = useState('')
  const [contextTopK, setContextTopK] = useState(5)
  const [contextMaxTokens, setContextMaxTokens] = useState(2000)
  const [contextResult, setContextResult] = useState<RagContextResult | null>(null)

  const loadDocuments = useCallback(async () => {
    try {
      const data = await ragApi.listDocuments()
      setDocuments(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  useEffect(() => { loadDocuments() }, [loadDocuments])

  const handleLoadDocument = async () => {
    if (!loadTitle.trim() || !loadContent.trim()) return
    setLoading(true)
    setError(null)
    try {
      await ragApi.loadDocument({
        title: loadTitle,
        content: loadContent,
        source: loadSource || undefined,
        content_type: loadType,
      })
      setShowLoad(false)
      setLoadTitle('')
      setLoadContent('')
      setLoadSource('')
      await loadDocuments()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const handleRetrieve = async () => {
    if (!retrieveQuery.trim()) return
    setError(null)
    try {
      const results = await ragApi.retrieve({ query: retrieveQuery, top_k: retrieveTopK })
      setRetrieveResults(results)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const handleBuildContext = async () => {
    if (!contextQuery.trim()) return
    setError(null)
    try {
      const result = await ragApi.buildContext({ query: contextQuery, top_k: contextTopK, max_tokens: contextMaxTokens })
      setContextResult(result)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await ragApi.deleteDocument(id)
      await loadDocuments()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div>
      <PageHeader
        title="RAG Documents"
        subtitle="Load, index, search, and build context from your document corpus."
        actions={
          <button
            onClick={() => setShowLoad(true)}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Upload className="size-4" /> Load Document
          </button>
        }
      />

      <div className="p-6 space-y-3">
        {error && (
          <Card className="border-destructive/40 bg-destructive/5 text-sm text-destructive flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)}><X className="size-4" /></button>
          </Card>
        )}

        {/* Load document form */}
        {showLoad && (
          <Card className="space-y-3">
            <h3 className="text-sm font-semibold">Load Document</h3>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Title</label>
                <input
                  value={loadTitle}
                  onChange={(e) => setLoadTitle(e.target.value)}
                  placeholder="Document title"
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                />
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Source (optional)</label>
                <input
                  value={loadSource}
                  onChange={(e) => setLoadSource(e.target.value)}
                  placeholder="URL or file path"
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                />
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Content Type</label>
                <select
                  value={loadType}
                  onChange={(e) => setLoadType(e.target.value as DocumentContentType)}
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                >
                  {contentTypes.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
            </div>
            <div>
              <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Content</label>
              <textarea
                value={loadContent}
                onChange={(e) => setLoadContent(e.target.value)}
                rows={8}
                placeholder="Paste document content here..."
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 font-mono text-xs outline-none focus:border-primary"
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleLoadDocument}
                disabled={loading}
                className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {loading ? 'Loading...' : 'Load'}
              </button>
              <button onClick={() => setShowLoad(false)} className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-muted">
                Cancel
              </button>
            </div>
          </Card>
        )}

        {/* Search / Retrieve */}
        <Card>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2"><Search className="size-4" /> Retrieve</h3>
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex-1 min-w-[200px]">
              <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Query</label>
              <input
                value={retrieveQuery}
                onChange={(e) => setRetrieveQuery(e.target.value)}
                placeholder="Search query..."
                onKeyDown={(e) => e.key === 'Enter' && handleRetrieve()}
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Top K</label>
              <input
                type="number"
                min={1}
                max={50}
                value={retrieveTopK}
                onChange={(e) => setRetrieveTopK(Number(e.target.value))}
                className="mt-1 w-20 rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
              />
            </div>
            <button
              onClick={handleRetrieve}
              className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              Search
            </button>
          </div>

          {retrieveResults && (
            <div className="mt-3 space-y-2">
              <p className="text-xs text-muted-foreground">{retrieveResults.length} results</p>
              {retrieveResults.map((r) => (
                <div key={r.chunkId} className="rounded-lg border border-border bg-background/50 p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">{r.documentTitle}</span>
                    <Badge tone="primary">Similarity: {(r.similarity * 100).toFixed(1)}%</Badge>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground line-clamp-3">{r.content}</p>
                  <div className="mt-1 flex items-center gap-3 text-[10px] text-muted-foreground">
                    <span>Chunk #{r.chunkIndex}</span>
                    {r.tokenCount && <span>{r.tokenCount} tokens</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Context Builder */}
        <Card>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2"><BookOpen className="size-4" /> Build Context</h3>
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex-1 min-w-[200px]">
              <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Query</label>
              <input
                value={contextQuery}
                onChange={(e) => setContextQuery(e.target.value)}
                placeholder="Context query..."
                onKeyDown={(e) => e.key === 'Enter' && handleBuildContext()}
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Top K</label>
              <input
                type="number"
                min={1}
                value={contextTopK}
                onChange={(e) => setContextTopK(Number(e.target.value))}
                className="mt-1 w-20 rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Max Tokens</label>
              <input
                type="number"
                min={100}
                value={contextMaxTokens}
                onChange={(e) => setContextMaxTokens(Number(e.target.value))}
                className="mt-1 w-24 rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
              />
            </div>
            <button
              onClick={handleBuildContext}
              className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              Build
            </button>
          </div>

          {contextResult && (
            <div className="mt-3 space-y-3">
              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                <span>{contextResult.chunksUsed} chunks used</span>
                <span>{contextResult.totalTokens} tokens</span>
              </div>
              <div className="rounded-lg border border-border bg-background/50 p-3">
                <h4 className="text-xs font-semibold mb-2">Context</h4>
                <pre className="text-xs font-mono text-muted-foreground whitespace-pre-wrap max-h-60 overflow-y-auto">{contextResult.context}</pre>
              </div>
              {contextResult.citations.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold mb-2">Citations</h4>
                  <div className="space-y-1">
                    {contextResult.citations.map((c) => (
                      <div key={c.index} className="flex items-center gap-2 text-xs">
                        <Badge tone="muted">[{c.index}]</Badge>
                        <span className="font-medium">{c.documentTitle}</span>
                        <span className="text-muted-foreground">Chunk #{c.chunkIndex}</span>
                        <Badge tone="primary">{(c.similarity * 100).toFixed(1)}%</Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </Card>

        {/* Document list */}
        <Card>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold flex items-center gap-2"><FileText className="size-4" /> Documents ({documents.length})</h3>
            <button onClick={loadDocuments} className="text-muted-foreground hover:text-foreground">
              <RefreshCw className="size-4" />
            </button>
          </div>
          {documents.length === 0 ? (
            <p className="text-xs text-muted-foreground">No documents loaded.</p>
          ) : (
            <div className="space-y-2">
              {documents.map((doc) => (
                <div key={doc.id} className="flex items-center justify-between rounded-lg border border-border bg-background/50 p-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{doc.title}</span>
                      <Badge tone="muted">{doc.contentType}</Badge>
                      <Badge tone={statusTone[doc.status] || 'muted'}>{doc.status}</Badge>
                    </div>
                    <div className="mt-1 flex items-center gap-3 text-[10px] text-muted-foreground">
                      <span>{doc.chunkCount} chunks</span>
                      {doc.source && <span className="truncate max-w-[200px]">{doc.source}</span>}
                      <span>{new Date(doc.createdAt).toLocaleString()}</span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(doc.id)}
                    className="inline-flex items-center gap-1 rounded-md border border-destructive/40 px-2 py-1 text-xs text-destructive hover:bg-destructive/10 shrink-0"
                  >
                    <Trash2 className="size-3" /> Delete
                  </button>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
