import { useState, useEffect, useCallback } from 'react'
import {
  Hand,
  Bot,
  Zap,
} from 'lucide-react'
import { Card, PageHeader, Badge } from './kit'
import { cn } from '../lib/utils'
import {
  GeneralTab,
} from './auth/AccountSettings'
import { ProviderSetup } from './auth/ProviderSetup'
import { api } from '../lib/runtimeClient'

const tabs = [
  'General',
  'Providers',
  'Auto Approve',
] as const
export type SettingsTab = (typeof tabs)[number]
type Tab = SettingsTab

/* ---------------- Providers ---------------- */

function HealthCheckSection() {
  const [health, setHealth] = useState<Array<{ id: string; name: string; status: string; latency_ms?: number; error?: string }>>([])
  const [loading, setLoading] = useState(false)
  const [tested, setTested] = useState(false)

  const runHealthCheck = async () => {
    setLoading(true)
    try {
      const { providerManageApi } = await import('../lib/api/provider_manage')
      const result = await providerManageApi.healthCheck()
      setHealth(result)
      setTested(true)
    } catch {
      setHealth([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold">Provider Health</h3>
          <p className="text-xs text-muted-foreground">Check connectivity of all enabled providers</p>
        </div>
        <button
          onClick={runHealthCheck}
          disabled={loading}
          className="rounded-lg px-3 py-1.5 text-xs font-medium hover:bg-muted border border-border"
        >
          {loading ? 'Checking...' : 'Run Health Check'}
        </button>
      </div>
      {tested && (
        <div className="space-y-2">
          {health.length === 0 && <p className="text-xs text-muted-foreground">No enabled providers found.</p>}
          {health.map((h) => (
            <div key={h.id} className="flex items-center justify-between rounded-lg border border-border px-3 py-2">
              <span className="text-sm font-medium">{h.name}</span>
              {h.status === 'connected' ? (
                <span className="flex items-center gap-1.5 text-xs text-green-400">
                  <span className="size-1.5 rounded-full bg-green-400" />
                  Connected — {h.latency_ms}ms
                </span>
              ) : (
                <span className="flex items-center gap-1.5 text-xs text-red-400">
                  <span className="size-1.5 rounded-full bg-red-400" />
                  Error — {h.error}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ProvidersTab() {
  return (
    <div className="space-y-4">
      <HealthCheckSection />
      <ProviderSetup mode="settings" />
    </div>
  )
}

/* ---------------- Auto Approve ---------------- */
const modes = [
  { id: 'manual', label: 'Manual', icon: Hand, desc: 'All approvals require manual review.' },
  { id: 'semi', label: 'Semi Auto', icon: Bot, desc: 'Low-risk auto approve; high-risk requires review.', recommended: true },
  { id: 'full', label: 'Full Auto', icon: Zap, desc: 'All approvals are automatically approved.' },
] as const

const SCOPE_KEYS = [
  { key: 'verifications', label: 'Verifications' },
  { key: 'lint_type_checks', label: 'Lint & Type Checks' },
  { key: 'unit_tests', label: 'Unit Tests' },
  { key: 'build_success', label: 'Build Success' },
  { key: 'security_scan_low', label: 'Security Scan (Low)' },
  { key: 'deploy_staging', label: 'Deploy to Staging' },
  { key: 'deploy_production', label: 'Deploy to Production' },
] as const

function AutoApproveTab() {
  const [mode, setMode] = useState<string>('semi')
  const [scope, setScope] = useState<Record<string, boolean>>({})
  const [riskThreshold, setRiskThreshold] = useState<string>('low')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getApprovalConfig().then((cfg) => {
      setMode(cfg.mode)
      setScope(cfg.scope)
      setRiskThreshold(cfg.risk_threshold)
    }).catch(() => {
      const defaultScope: Record<string, boolean> = {}
      SCOPE_KEYS.forEach((s) => { defaultScope[s.key] = s.key !== 'deploy_staging' && s.key !== 'deploy_production' })
      setScope(defaultScope)
    }).finally(() => setLoading(false))
  }, [])

  const saveConfig = useCallback(async (updates: { mode?: string; scope?: Record<string, boolean>; risk_threshold?: string }) => {
    try {
      await api.updateApprovalConfig({
        mode: updates.mode ?? mode,
        scope: updates.scope ?? scope,
        risk_threshold: updates.risk_threshold ?? riskThreshold,
      })
    } catch {
      // silently fail — UI stays in sync locally
    }
  }, [mode, scope, riskThreshold])

  const handleModeChange = (newMode: string) => {
    setMode(newMode)
    saveConfig({ mode: newMode })
  }

  const handleScopeToggle = (key: string) => {
    const updated = { ...scope, [key]: !scope[key] }
    setScope(updated)
    saveConfig({ scope: updated })
  }

  const handleRiskChange = (level: string) => {
    setRiskThreshold(level)
    saveConfig({ risk_threshold: level })
  }

  if (loading) return <div className="text-sm text-muted-foreground">Loading...</div>

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-sm font-semibold">Auto Approve Mode</h2>
        <p className="text-xs text-muted-foreground">
          Control how much of the approval workflow runs without human input.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
        <div className="grid gap-3 sm:grid-cols-3">
          {modes.map((m) => {
            const Icon = m.icon
            const active = mode === m.id
            return (
              <button
                key={m.id}
                onClick={() => handleModeChange(m.id)}
                className={cn(
                  'flex flex-col items-center gap-2 rounded-xl border p-4 text-center transition-colors',
                  active ? 'border-primary bg-primary/10 ring-1 ring-primary/40' : 'border-border bg-card hover:border-primary/40',
                )}
              >
                <div className={cn('grid size-10 place-items-center rounded-lg', active ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground')}>
                  <Icon className="size-5" />
                </div>
                <span className="text-sm font-semibold">{m.label}</span>
                <span className="text-[11px] text-muted-foreground">{m.desc}</span>
                {'recommended' in m && m.recommended ? <Badge tone="primary">Recommended</Badge> : null}
              </button>
            )
          })}
        </div>

        <Card>
          <h3 className="mb-3 text-sm font-semibold">Auto Approve Scope</h3>
          <ul className="space-y-2.5">
            {SCOPE_KEYS.map((s) => (
              <li key={s.key} className="flex items-center justify-between text-sm">
                <span className={scope[s.key] ? '' : 'text-muted-foreground'}>{s.label}</span>
                <button
                  type="button"
                  onClick={() => handleScopeToggle(s.key)}
                  className={cn(
                    'relative h-4 w-8 rounded-full transition-colors',
                    scope[s.key] ? 'bg-primary' : 'bg-muted',
                  )}
                >
                  <span
                    className={cn(
                      'absolute top-0.5 size-3 rounded-full bg-background transition-all',
                      scope[s.key] ? 'left-4' : 'left-0.5',
                    )}
                  />
                </button>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">Risk Threshold (Semi Auto)</h3>
          <p className="text-xs text-muted-foreground">Only low-risk approvals will be auto approved.</p>
        </div>
        <div className="flex items-center gap-1 rounded-lg border border-border p-1">
          {['low', 'medium', 'high'].map((r) => (
            <button
              key={r}
              onClick={() => handleRiskChange(r)}
              className={cn(
                'rounded-md px-3 py-1 text-sm capitalize',
                r === riskThreshold ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {r}
            </button>
          ))}
        </div>
      </Card>
    </div>
  )
}

export function SettingsView({
  initialTab,
  updateDialogOpen,
  onUpdateDialogOpenChange,
}: {
  initialTab?: Tab
  updateDialogOpen?: boolean
  onUpdateDialogOpenChange?: (open: boolean) => void
} = {}) {
  const [tab, setTab] = useState<Tab>(initialTab || 'General')

  return (
    <div>
      <PageHeader title="Settings" subtitle="Profile, providers, and approval automation." />

      <div className="p-6">
        <div className="mb-6 flex flex-wrap gap-4 border-b border-border">
          {tabs.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={cn(
                'relative pb-3 text-sm transition-colors',
                tab === t ? 'text-foreground' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {t}
              {tab === t ? (
                <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-primary" />
              ) : null}
            </button>
          ))}
        </div>

        {tab === 'General' ? <GeneralTab updateDialogOpen={updateDialogOpen} onUpdateDialogOpenChange={onUpdateDialogOpenChange} /> : null}
        {tab === 'Providers' ? <ProvidersTab /> : null}
        {tab === 'Auto Approve' ? <AutoApproveTab /> : null}
      </div>
    </div>
  )
}
