import { useState, useEffect, useCallback } from 'react'
import {
  Hand, Bot, Zap, Cpu, Download, FolderOpen,
  Bug, Clock, HardDrive, Save, FileText, RefreshCw, Trash2,
} from 'lucide-react'
import { Card, PageHeader, Badge } from './kit'
import { cn } from '../lib/utils'
import { GeneralTab } from './auth/AccountSettings'
import { ProviderSetup } from './auth/ProviderSetup'
import { api } from '../lib/runtimeClient'
import { apiClient } from '../lib/api/client'
import { profileApi } from '../lib/api/profile'
import { providerManageApi, type EnvConfig } from '../lib/api/provider_manage'
import { providersApi, type ProviderRecord, type ModelInfo } from '../lib/api/providers'

const tabs = [
  'General', 'Workspace', 'Providers',
  'Updates', 'Developer', 'Auto Save',
] as const
export type SettingsTab = (typeof tabs)[number]
type Tab = SettingsTab

/* ─── Workspace Tab ─── */

function WorkspaceTab() {
  const [root, setRoot] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    profileApi.get().then(p => { if (p?.projectRoot) setRoot(p.projectRoot) }).catch(() => {})
  }, [])

  const handleSave = async () => {
    try { await profileApi.update({ projectRoot: root }); setSaved(true); setTimeout(() => setSaved(false), 2000) }
    catch { /* ignore */ }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <FolderOpen className="size-5" /> Workspace
        </h3>
        <div className="space-y-4">
          <div>
            <label className="text-sm text-muted-foreground">Default Project Root</label>
            <input
              type="text" value={root} onChange={(e) => setRoot(e.target.value)}
              placeholder="/home/user/projects"
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-foreground font-mono text-sm outline-none focus:border-primary"
            />
          </div>
          <button onClick={handleSave} className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
            {saved ? 'Saved' : 'Save'}
          </button>
        </div>
      </Card>
    </div>
  )
}

/* ─── Engine Config Section ─── */

function EngineConfigSection() {
  const [cfg, setCfg] = useState<EnvConfig | null>(null)
  const [providers, setProviders] = useState<ProviderRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  // Per-tier provider+model state
  const [thinkerProvider, setThinkerProvider] = useState<string>('')
  const [crafterProvider, setCrafterProvider] = useState<string>('')
  const [sprinterProvider, setSprinterProvider] = useState<string>('')
  const [thinkerModels, setThinkerModels] = useState<ModelInfo[]>([])
  const [crafterModels, setCrafterModels] = useState<ModelInfo[]>([])
  const [sprinterModels, setSprinterModels] = useState<ModelInfo[]>([])
  const [thinkerModel, setThinkerModel] = useState<string>('')
  const [crafterModel, setCrafterModel] = useState<string>('')
  const [sprinterModel, setSprinterModel] = useState<string>('')

  useEffect(() => {
    Promise.all([
      providerManageApi.getEnvConfig(),
      providersApi.list()
    ]).then(([envCfg, pList]) => {
      setCfg(envCfg)
      setProviders(pList)

      // Find provider for each tier from env config
      const activeP = pList.find(p => p.name === envCfg.provider_name)
      if (activeP) {
        setThinkerProvider(activeP.name)
        setCrafterProvider(activeP.name)
        setSprinterProvider(activeP.name)
        setThinkerModels(activeP.models || [])
        setCrafterModels(activeP.models || [])
        setSprinterModels(activeP.models || [])
      }
      setThinkerModel(envCfg.thinker || '')
      setCrafterModel(envCfg.crafter || '')
      setSprinterModel(envCfg.sprinter || '')
    }).finally(() => setLoading(false))
  }, [])

  const handleTierProviderChange = (tier: 'thinker' | 'crafter' | 'sprinter', pName: string) => {
    const p = providers.find(x => x.name === pName)
    if (!p) return
    const pModels = p.models || []
    if (tier === 'thinker') { setThinkerProvider(pName); setThinkerModels(pModels); setThinkerModel('') }
    if (tier === 'crafter') { setCrafterProvider(pName); setCrafterModels(pModels); setCrafterModel('') }
    if (tier === 'sprinter') { setSprinterProvider(pName); setSprinterModels(pModels); setSprinterModel('') }
  }

  const fetchAllModels = async () => {
    setLoading(true)
    try {
      const pList: ProviderRecord[] = []
      for (const p of providers) {
        try { await providersApi.fetchModelsAndUpdate(p.id, p.endpoint) } catch {}
        const refreshed = await providersApi.list()
        const updated = refreshed.find(r => r.id === p.id)
        if (updated) pList.push(updated)
      }
      if (pList.length === 0) {
        const all = await providersApi.list()
        setProviders(all)
      } else {
        setProviders(pList)
      }
      // Refresh current selections
      const tp = pList.find(p => p.name === thinkerProvider)
      const cp = pList.find(p => p.name === crafterProvider)
      const sp = pList.find(p => p.name === sprinterProvider)
      if (tp) setThinkerModels(tp.models || [])
      if (cp) setCrafterModels(cp.models || [])
      if (sp) setSprinterModels(sp.models || [])
    } catch {}
    setLoading(false)
  }

  const handleSave = async () => {
    setSaving(true)
    setMsg('')
    try {
      // Use the first available provider's credentials
      const p = providers.find(x => x.name === thinkerProvider) || providers[0]
      await providerManageApi.updateEnvConfig({
        provider_name: p?.name || '',
        base_url: p?.endpoint || '',
        api_key: p?.apiKey || '',
        thinker: thinkerModel,
        crafter: crafterModel,
        sprinter: sprinterModel,
      })
      setMsg('Engine updated successfully!')
      setTimeout(() => setMsg(''), 3000)
    } catch {
      setMsg('Failed to update engine')
    }
    setSaving(false)
  }

  if (loading) return <div className="text-sm text-muted-foreground animate-pulse">Loading engine config...</div>
  if (!cfg) return null

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h3 className="text-lg font-semibold flex items-center gap-2"><Cpu className="size-5" /> Execution Engine</h3>
          <p className="text-xs text-muted-foreground mt-1">Select provider and model for each tier.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={fetchAllModels} disabled={loading} className="rounded-lg border border-border px-3 py-2 text-xs font-medium hover:bg-muted">
            {loading ? 'Scanning...' : 'Fetch Models'}
          </button>
          <button onClick={handleSave} disabled={saving} className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
            {saving ? 'Applying...' : 'Apply to Engine'}
          </button>
        </div>
      </div>

      {msg && <div className="mb-4 rounded-lg bg-success/10 border border-success/20 px-4 py-2 text-sm text-success">{msg}</div>}

      <div className="space-y-4">
        {/* THINKER */}
        <div className="rounded-lg border border-border/60 p-4">
          <div className="flex items-center gap-3 mb-3">
            <span className="text-sm font-semibold text-primary w-24">Thinker</span>
            <select value={thinkerProvider} onChange={e => handleTierProviderChange('thinker', e.target.value)}
              className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm">
              <option value="">Select Provider...</option>
              {providers.map(p => <option key={p.id} value={p.name}>{p.name}</option>)}
            </select>
            <select value={thinkerModel} onChange={e => setThinkerModel(e.target.value)}
              className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono">
              <option value="">Select Model...</option>
              {thinkerModels.map(m => <option key={m.id} value={m.id}>{m.name || m.id}</option>)}
            </select>
          </div>
          <p className="text-[10px] text-muted-foreground ml-[96px]">Used by Planner, Architect, Research</p>
        </div>

        {/* CRAFTER */}
        <div className="rounded-lg border border-border/60 p-4">
          <div className="flex items-center gap-3 mb-3">
            <span className="text-sm font-semibold text-success w-24">Crafter</span>
            <select value={crafterProvider} onChange={e => handleTierProviderChange('crafter', e.target.value)}
              className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm">
              <option value="">Select Provider...</option>
              {providers.map(p => <option key={p.id} value={p.name}>{p.name}</option>)}
            </select>
            <select value={crafterModel} onChange={e => setCrafterModel(e.target.value)}
              className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono">
              <option value="">Select Model...</option>
              {crafterModels.map(m => <option key={m.id} value={m.id}>{m.name || m.id}</option>)}
            </select>
          </div>
          <p className="text-[10px] text-muted-foreground ml-[96px]">Used by Backend, Frontend, QA</p>
        </div>

        {/* SPRINTER */}
        <div className="rounded-lg border border-border/60 p-4">
          <div className="flex items-center gap-3 mb-3">
            <span className="text-sm font-semibold text-warning w-24">Sprinter</span>
            <select value={sprinterProvider} onChange={e => handleTierProviderChange('sprinter', e.target.value)}
              className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm">
              <option value="">Select Provider...</option>
              {providers.map(p => <option key={p.id} value={p.name}>{p.name}</option>)}
            </select>
            <select value={sprinterModel} onChange={e => setSprinterModel(e.target.value)}
              className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono">
              <option value="">Select Model...</option>
              {sprinterModels.map(m => <option key={m.id} value={m.id}>{m.name || m.id}</option>)}
            </select>
          </div>
          <p className="text-[10px] text-muted-foreground ml-[96px]">Used by Docs, Governor</p>
        </div>
      </div>
    </Card>
  )
}

/* ─── Providers Tab ─── */

function ProvidersTab() {
  return (
    <div className="space-y-6 max-w-4xl">
      <ProviderSetup mode="settings" />
      <EngineConfigSection />
    </div>
  )
}

/* ─── Updates Tab ─── */

function UpdatesTab() {
  const [appVersion, setAppVersion] = useState('…')
  const [updateState, setUpdateState] = useState<any>(null)

  useEffect(() => {
    window.aic?.getAppVersion?.().then((v: string) => { if (v) setAppVersion(v) }).catch(() => {})
    window.aic?.updateGetState?.().then((s: any) => { if (s) setUpdateState(s) }).catch(() => {})
    const off = window.aic?.onUpdateStateChanged?.((s: any) => { setUpdateState(s) })
    return () => { off?.() }
  }, [])

  const updateStatus = updateState?.status || 'unknown'
  const updateLabel: Record<string, string> = {
    idle: 'Up to date', checking: 'Checking…', available: 'Update available',
    downloading: 'Downloading…', ready_to_install: 'Ready to install', error: 'Update error', unknown: '—',
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Download className="size-5" /> Updates
        </h3>
        <div className="space-y-3 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Current Version</span>
            <span className="font-mono">{appVersion}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Status</span>
            <span className={updateStatus === 'idle' ? 'text-success' : updateStatus === 'available' || updateStatus === 'ready_to_install' ? 'text-primary' : updateStatus === 'error' ? 'text-destructive' : 'text-muted-foreground'}>
              {updateLabel[updateStatus] || updateStatus}
            </span>
          </div>
          {updateState?.availableVersion && updateState.availableVersion !== appVersion && (
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">New Version</span>
              <span className="font-mono text-primary">{updateState.availableVersion}</span>
            </div>
          )}
          <div className="flex items-center gap-3 pt-2 border-t border-border">
            <button onClick={() => window.aic?.updateCheck?.()}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
              Check for Updates
            </button>
            {updateState?.status === 'available' && (
              <button onClick={() => window.aic?.updateDownload?.()}
                className="rounded-lg border border-primary px-4 py-2 text-sm font-medium text-primary">
                Download Update
              </button>
            )}
            {updateState?.status === 'ready_to_install' && (
              <button onClick={() => window.aic?.updateQuitAndInstall?.()}
                className="rounded-lg bg-success px-4 py-2 text-sm font-medium text-white">
                Install & Restart
              </button>
            )}
          </div>
        </div>
      </Card>
    </div>
  )
}

/* ─── Developer Tab ─── */

function DeveloperTab() {
  const [debugMode, setDebugMode] = useState(false)
  const [logLevel, setLogLevel] = useState('info')
  const [showDevTools, setShowDevTools] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    const saved = localStorage.getItem('aic-ade-developer')
    if (saved) {
      const s = JSON.parse(saved)
      if (s.debugMode !== undefined) setDebugMode(s.debugMode)
      if (s.logLevel) setLogLevel(s.logLevel)
      if (s.showDevTools !== undefined) setShowDevTools(s.showDevTools)
    }
  }, [])

  const save = () => {
    localStorage.setItem('aic-ade-developer', JSON.stringify({ debugMode, logLevel, showDevTools }))
    setSaved(true); setTimeout(() => setSaved(false), 2000)
  }

  const clearCache = () => {
    localStorage.removeItem('aic-ade-settings')
    localStorage.removeItem('aic-ade-memory')
    localStorage.removeItem('aic-ade-developer')
    localStorage.removeItem('aic-ade-settings-tab')
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Bug className="size-5" /> Developer
        </h3>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium">Debug Mode</label>
              <p className="text-xs text-muted-foreground">Enable verbose logging and diagnostics</p>
            </div>
            <button onClick={() => setDebugMode(!debugMode)}
              className={cn('relative h-5 w-9 rounded-full transition-colors', debugMode ? 'bg-primary' : 'bg-muted')}>
              <span className={cn('absolute top-0.5 size-4 rounded-full bg-background transition-all', debugMode ? 'left-4' : 'left-0.5')} />
            </button>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium">Show Developer Tools</label>
              <p className="text-xs text-muted-foreground">Open Electron DevTools on startup</p>
            </div>
            <button onClick={() => setShowDevTools(!showDevTools)}
              className={cn('relative h-5 w-9 rounded-full transition-colors', showDevTools ? 'bg-primary' : 'bg-muted')}>
              <span className={cn('absolute top-0.5 size-4 rounded-full bg-background transition-all', showDevTools ? 'left-4' : 'left-0.5')} />
            </button>
          </div>
          <div>
            <label className="text-sm text-muted-foreground">Log Level</label>
            <div className="flex gap-2 mt-1">
              {['error', 'warn', 'info', 'debug', 'trace'].map(l => (
                <button key={l} onClick={() => setLogLevel(l)}
                  className={cn('rounded-md border px-3 py-1 text-xs font-mono uppercase transition-colors',
                    logLevel === l ? 'border-primary bg-primary/10 text-primary' : 'border-border')}>
                  {l}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-3 pt-2 border-t border-border">
            <button onClick={save} className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
              {saved ? 'Saved' : 'Save'}
            </button>
            <button onClick={clearCache}
              className="rounded-lg border border-border px-4 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-muted flex items-center gap-2">
              <Trash2 className="size-3.5" /> Clear Cache
            </button>
          </div>
        </div>
      </Card>
    </div>
  )
}

/* ─── Auto Save Tab ─── */

function AutoSaveTab() {
  const [enabled, setEnabled] = useState(true)
  const [interval, setInterval] = useState(30)
  const [saveFormat, setSaveFormat] = useState('json')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    const saved = localStorage.getItem('aic-ade-autosave')
    if (saved) {
      const s = JSON.parse(saved)
      if (s.enabled !== undefined) setEnabled(s.enabled)
      if (s.interval) setInterval(s.interval)
      if (s.saveFormat) setSaveFormat(s.saveFormat)
    }
  }, [])

  const save = () => {
    localStorage.setItem('aic-ade-autosave', JSON.stringify({ enabled, interval, saveFormat }))
    setSaved(true); setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Save className="size-5" /> Auto Save
        </h3>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium">Enable Auto Save</label>
              <p className="text-xs text-muted-foreground">Automatically save conversations and project state</p>
            </div>
            <button onClick={() => setEnabled(!enabled)}
              className={cn('relative h-5 w-9 rounded-full transition-colors', enabled ? 'bg-primary' : 'bg-muted')}>
              <span className={cn('absolute top-0.5 size-4 rounded-full bg-background transition-all', enabled ? 'left-4' : 'left-0.5')} />
            </button>
          </div>
          <div>
            <label className="text-sm text-muted-foreground">Save Interval (seconds)</label>
            <input type="number" value={interval} onChange={(e) => setInterval(Number(e.target.value))} disabled={!enabled}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-foreground outline-none focus:border-primary disabled:opacity-50" />
          </div>
          <div>
            <label className="text-sm text-muted-foreground">Save Format</label>
            <div className="flex gap-2 mt-1">
              {['json', 'sqlite', 'markdown'].map(f => (
                <button key={f} onClick={() => setSaveFormat(f)} disabled={!enabled}
                  className={cn('rounded-md border px-3 py-1 text-xs font-mono uppercase transition-colors disabled:opacity-50',
                    saveFormat === f ? 'border-primary bg-primary/10 text-primary' : 'border-border')}>
                  {f}
                </button>
              ))}
            </div>
          </div>
          <button onClick={save} className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
            {saved ? 'Saved' : 'Save'}
          </button>
        </div>
      </Card>
    </div>
  )
}

/* ─── Auto Approve Tab ─── */

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
    } catch { /* ignore */ }
  }, [mode, scope, riskThreshold])

  if (loading) return <div className="text-sm text-muted-foreground">Loading...</div>

  return (
    <div className="space-y-5 max-w-2xl">
      <div>
        <h2 className="text-sm font-semibold">Auto Approve Mode</h2>
        <p className="text-xs text-muted-foreground">Control how much of the approval workflow runs without human input.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {modes.map((m) => {
          const Icon = m.icon
          const active = mode === m.id
          return (
            <button key={m.id} onClick={() => { setMode(m.id); saveConfig({ mode: m.id }) }}
              className={cn('flex flex-col items-center gap-2 rounded-xl border p-4 text-center transition-colors',
                active ? 'border-primary bg-primary/10 ring-1 ring-primary/40' : 'border-border bg-card hover:border-primary/40')}>
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
    </div>
  )
}

/* ─── Main Settings View ─── */

export function SettingsView({
  initialTab, updateDialogOpen, onUpdateDialogOpenChange,
}: {
  initialTab?: Tab
  updateDialogOpen?: boolean
  onUpdateDialogOpenChange?: (open: boolean) => void
} = {}) {
  const [tab, setTab] = useState<Tab>(() => {
    const saved = localStorage.getItem('aic-ade-settings-tab')
    if (saved && tabs.includes(saved as Tab)) return saved as Tab
    if (initialTab && tabs.includes(initialTab as Tab)) return initialTab as Tab
    return 'General'
  })

  const handleTabChange = (t: Tab) => {
    setTab(t)
    localStorage.setItem('aic-ade-settings-tab', t)
  }

  return (
    <div className="max-w-3xl mx-auto">
      <PageHeader title="Settings" subtitle="Configure your AIC ADE workspace." />
      <div className="p-6">
        <div className="mb-6 flex flex-wrap justify-center gap-1 border-b border-border">
          {tabs.map((t) => (
            <button
              key={t} type="button" onClick={() => handleTabChange(t)}
              className={cn('relative px-4 pb-3 text-sm transition-colors',
                tab === t ? 'text-foreground font-medium' : 'text-muted-foreground hover:text-foreground')}>
              {t}
              {tab === t && <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-primary" />}
            </button>
          ))}
        </div>

        <div className="flex justify-center">
          {tab === 'General' && <GeneralTab updateDialogOpen={updateDialogOpen} onUpdateDialogOpenChange={onUpdateDialogOpenChange} />}
          {tab === 'Workspace' && <WorkspaceTab />}
          {tab === 'Providers' && <ProvidersTab />}
          {tab === 'Updates' && <UpdatesTab />}
          {tab === 'Developer' && <DeveloperTab />}
          {tab === 'Auto Save' && <AutoSaveTab />}
        </div>
      </div>
    </div>
  )
}