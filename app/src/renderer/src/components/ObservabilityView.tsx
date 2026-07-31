import { useState, useEffect } from 'react'
import { apiClient } from '../lib/api/client'

interface UsageStats {
  period_days: number
  total_requests: number
  total_prompt_tokens: number
  total_completion_tokens: number
  total_tokens: number
  total_cost: number
  by_provider: Array<{
    provider: string
    requests: number
    tokens: number
    cost: number
  }>
  by_model: Array<{
    model: string
    requests: number
    tokens: number
    cost: number
  }>
}

interface ContextStats {
  total_entries: number
  total_decisions: number
  domains: Record<string, number>
}

interface WorkerMetrics {
  role: string
  totalExecutions: number
  completed: number
  errors: number
  avgLatencyMs: number
  lastExecutedAt: string | null
  currentlyRunning: boolean
}

export default function ObservabilityView() {
  const [usageStats, setUsageStats] = useState<UsageStats | null>(null)
  const [contextStats, setContextStats] = useState<ContextStats | null>(null)
  const [workerMetrics, setWorkerMetrics] = useState<Record<string, WorkerMetrics>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'context' | 'workers' | 'usage'>('overview')

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    setError(null)

    try {
      // Load usage stats
      const usage = await apiClient.get<UsageStats>('/api/usage/stats?days=30')
      setUsageStats(usage)

      // Load context stats
      const context = await apiClient.get<ContextStats>('/api/context/stats')
      setContextStats(context)

      const workers = await apiClient.get<Array<{ role: string; metrics: WorkerMetrics }>>('/runtime/workers')
      setWorkerMetrics(Object.fromEntries(workers.map((worker) => [worker.role, worker.metrics])))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  const formatNumber = (num: number) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
    return num.toString()
  }

  const formatCost = (cost: number) => {
    return `$${cost.toFixed(4)}`
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-400">Loading observability data...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-red-400">{error}</div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-700">
        <h1 className="text-xl font-semibold text-white">Observability</h1>
        <p className="text-sm text-gray-400 mt-1">
          Monitor context, workers, and token usage
        </p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-700">
        {(['overview', 'context', 'workers', 'usage'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium ${
              activeTab === tab
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {activeTab === 'overview' && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Usage Card */}
            <div className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-sm font-medium text-gray-400">Total Requests</h3>
              <p className="text-2xl font-bold text-white mt-1">
                {formatNumber(usageStats?.total_requests || 0)}
              </p>
              <p className="text-xs text-gray-500 mt-1">Last 30 days</p>
            </div>

            {/* Tokens Card */}
            <div className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-sm font-medium text-gray-400">Total Tokens</h3>
              <p className="text-2xl font-bold text-white mt-1">
                {formatNumber(usageStats?.total_tokens || 0)}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                {formatNumber(usageStats?.total_prompt_tokens || 0)} prompt + {formatNumber(usageStats?.total_completion_tokens || 0)} completion
              </p>
            </div>

            {/* Cost Card */}
            <div className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-sm font-medium text-gray-400">Total Cost</h3>
              <p className="text-2xl font-bold text-white mt-1">
                {formatCost(usageStats?.total_cost || 0)}
              </p>
              <p className="text-xs text-gray-500 mt-1">Last 30 days</p>
            </div>

            {/* Context Card */}
            <div className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-sm font-medium text-gray-400">Knowledge Entries</h3>
              <p className="text-2xl font-bold text-white mt-1">
                {contextStats?.total_entries || 0}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                {contextStats?.total_decisions || 0} decisions
              </p>
            </div>
          </div>
        )}

        {activeTab === 'context' && (
          <div className="space-y-4">
            <div className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-lg font-medium text-white mb-4">Context Sources</h3>
              <div className="space-y-2">
                {contextStats?.domains && Object.entries(contextStats.domains).map(([domain, count]) => (
                  <div key={domain} className="flex justify-between items-center">
                    <span className="text-gray-300">{domain}</span>
                    <span className="text-gray-400">{count} entries</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'workers' && (
          <div className="space-y-4">
            <div className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-lg font-medium text-white mb-4">Worker Metrics</h3>
              {Object.keys(workerMetrics).length === 0 ? (
                <p className="text-gray-400">No worker metrics available</p>
              ) : (
                <div className="space-y-4">
                  {Object.entries(workerMetrics).map(([role, metrics]) => (
                    <div key={role} className="border-b border-gray-700 pb-4">
                      <div className="flex justify-between items-center mb-2">
                        <h4 className="font-medium text-white">{role}</h4>
                        <span className={`px-2 py-1 text-xs rounded ${
                          metrics.currentlyRunning ? 'bg-green-900 text-green-300' : 'bg-gray-700 text-gray-400'
                        }`}>
                          {metrics.currentlyRunning ? 'Running' : 'Idle'}
                        </span>
                      </div>
                      <div className="grid grid-cols-3 gap-4 text-sm">
                        <div>
                          <p className="text-gray-400">Total</p>
                          <p className="text-white">{metrics.totalExecutions}</p>
                        </div>
                        <div>
                          <p className="text-gray-400">Completed</p>
                          <p className="text-green-400">{metrics.completed}</p>
                        </div>
                        <div>
                          <p className="text-gray-400">Errors</p>
                          <p className="text-red-400">{metrics.errors}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'usage' && (
          <div className="space-y-4">
            {/* By Provider */}
            <div className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-lg font-medium text-white mb-4">Usage by Provider</h3>
              {usageStats?.by_provider && usageStats.by_provider.length > 0 ? (
                <div className="space-y-2">
                  {usageStats.by_provider.map(item => (
                    <div key={item.provider} className="flex justify-between items-center">
                      <span className="text-gray-300">{item.provider}</span>
                      <div className="flex gap-4 text-sm">
                        <span className="text-gray-400">{formatNumber(item.requests)} req</span>
                        <span className="text-gray-400">{formatNumber(item.tokens)} tokens</span>
                        <span className="text-white">{formatCost(item.cost)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-400">No usage data available</p>
              )}
            </div>

            {/* By Model */}
            <div className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-lg font-medium text-white mb-4">Usage by Model</h3>
              {usageStats?.by_model && usageStats.by_model.length > 0 ? (
                <div className="space-y-2">
                  {usageStats.by_model.map(item => (
                    <div key={item.model} className="flex justify-between items-center">
                      <span className="text-gray-300">{item.model}</span>
                      <div className="flex gap-4 text-sm">
                        <span className="text-gray-400">{formatNumber(item.requests)} req</span>
                        <span className="text-gray-400">{formatNumber(item.tokens)} tokens</span>
                        <span className="text-white">{formatCost(item.cost)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-400">No usage data available</p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-gray-700">
        <button
          onClick={loadData}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
        >
          Refresh
        </button>
      </div>
    </div>
  )
}
