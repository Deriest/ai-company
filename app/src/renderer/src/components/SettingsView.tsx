import { useState, useEffect, useCallback } from 'react'
import {
  Hand, Bot, Zap, Monitor, Palette, Globe, Cpu, Download, FolderOpen,
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
  'General', 'Workspace', 'Appearance', 'Providers',
  'Updates', 'Memory', 'Developer', 'Auto Save',
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

/* ─── Appearance Tab ─── */

function AppearanceTab() {
  const [theme, setTheme] = useState('dark')
  const [fontSize, setFontSize] = useState('medium')
  const [density, setDensity] = useState('comfortable')

  useEffect(() => {
    const saved = localStorage.getItem('aic-ade-settings')
    if (saved) {
      const s = JSON.parse(saved)
      if (s.theme) setTheme(s.theme)
      if (s.fontSize) setFontSize(s.fontSize)
      if (s.density) setDensity(s.density)
    }
  }, [])

  const save = (key: string, val: string) => {
    const saved = localStorage.getItem('aic-ade-settings')
    const cfg = saved ? JSON.parse(saved) : {}
    cfg[key] = val
    localStorage.setItem('aic-ade-settings', JSON.stringify(cfg))
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Palette className="size-5" /> Theme
        </h3>
        <div className="flex gap-3">
          {['dark', 'light', 'system'].map(t => (
            <button key={t} onClick={() => { setTheme(t); save('theme', t) }}
              className={cn('rounded-lg border px-4 py-3 text-sm font-medium capitalize transition-colors',
                theme === t ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:border-primary/40')}>
              {t}
            </button>
          ))}
        </div>
      </Card>

      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Monitor className="size-5" /> Font Size
        </h3>
        <div className="flex gap-3">
          {['small', 'medium', 'large'].map(s => (
            <button key={s} onClick={() => { setFontSize(s); save('fontSize', s) }}
              className={cn('rounded-lg border px-4 py-3 text-sm font-medium capitalize transition-colors',
                fontSize === s ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:border-primary/40')}>
              {s}
            </button>
          ))}
        </div>
      </Card>

      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Monitor className="size-5" /> UI Density
        </h3>
        <div className="flex gap-3">
          {['compact', 'comfortable', 'spacious'].map(d => (
            <button key={d} onClick={() => { setDensity(d); save('density', d) }}
              className={cn('rounded-lg border px-4 py-3 text-sm font-medium capitalize transition-colors',
                density === d ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:border-primary/40')}>
              {d}
            </button>
          ))}
        </div>
      </Card>
    </div>
  )
}

/* ─── Engine Config Section ─── */

function EngineConfigSection() {
  const [cfg, setCfg] = useState<EnvConfig | null>(null)
  const [providers, setProviders] = useState<ProviderRecord[]>([])
  const [models, setModels] = useState<ModelInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    Promise.all([
      providerManageApi.getEnvConfig(),
      providersApi.list()
    ]).then(([envCfg, pList]) => {
      setCfg(envCfg)
      setProviders(pList)
      
      const activeP = pList.find(p => p.name === envCfg.provider_name)
      if (activeP) {
        setModels(activeP.models || [])
      }
    }).finally(() => setLoading(false))
  }, [])

  const handleProviderChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const pName = e.target.value
    const p = providers.find(x => x.name === pName)
    if (p) {
      setModels(p.models || [])
      setCfg(prev => prev ? { 
        ...prev, 
        provider_name: p.name, 
        base_url: p.endpoint, 
        api_key: p.apiKey 
      } : null)
    }
  }

  const handleSave = async () => {
    if (!cfg) return
    setSaving(true)
    setMsg('')
    try {
      await providerManageApi.updateEnvConfig(cfg)
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
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold flex items-center gap-2"><Cpu className="size-5" /> Execution Engine</h3>
          <p className="text-xs text-muted-foreground mt-1">Select the active provider and models used by the AI workers.</p>
        </div>
        <button onClick={handleSave} disabled={saving} className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
          {saving ? 'Applying...' : 'Apply to Engine'}
        </button>
      </div>

      {msg && <div className="mb-4 rounded-lg bg-success/10 border border-success/20 px-4 py-2 text-sm text-success">{msg}</div>}

      <div className="grid gap-4 sm:grid-cols-2 mb-4 pb-4 border-b border-border">
        <div>
          <label className="text-sm text-muted-foreground">Active Provider</label>
          <select value={cfg.provider_name} onChange={handleProviderChange} className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm">
            <option value="default" disabled>Select a configured provider...</option>
            {providers.map(p => <option key={p.id} value={p.name}>{p.name}</option>)}
          </select>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div>
          <label className="text-sm font-medium text-primary">Thinker Model</label>
          <p className="text-[10px] text-muted-foreground mb-2">Used by Planner, Architect</p>
          <select value={cfg.thinker} onChange={e => setCfg({ ...cfg, thinker: e.target.value })} className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono mb-2">
            <option value="">-- Select Model --</option>
            {models.map(m => <option key={m.id} value={m.id}>{m.name || m.id}</option>)}
          </select>
          <input type="text" value={cfg.thinker} onChange={e => setCfg({ ...cfg, thinker: e.target.value })} className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-mono" placeholder="Or type model ID..." />
        </div>
        <div>
          <label className="text-sm font-medium text-success">Crafter Model</label>
          <p className="text-[10px] text-muted-foreground mb-2">Used by Backend, Frontend, QA</p>
          <select value={cfg.crafter} onChange={e => setCfg({ ...cfg, crafter: e.target.value })} className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono mb-2">
            <option value="">-- Select Model --</option>
            {models.map(m => <option key={m.id} value={m.id}>{m.name || m.id}</option>)}
          </select>
          <input type="text" value={cfg.crafter} onChange={e => setCfg({ ...cfg, crafter: e.target.value })} className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-mono" placeholder="Or type model ID..." />
        </div>
        <div>
          <label className="text-sm font-medium text-warning">Sprinter Model</label>
          <p className="text-[10px] text-muted-foreground mb-2">Used by Docs, Governor</p>
          <select value={cfg.sprinter} onChange={e => setCfg({ ...cfg, sprinter: e.target.value })} className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono mb-2">
            <option value="">-- Select Model --</option>
            {models.map(m => <option key={m.id} value={m.id}>{m.name || m.id}</option>)}
          </select>
          <input type="text" value={cfg.sprinter} onChange={e => setCfg({ ...cfg, sprinter: e.target.value })} className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-mono" placeholder="Or type model ID..." />
        </div>
      </div>
    </Card>
  )
}

/* ─── Providers Tab ─── */

function ProvidersTab() {
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
    } catch { setHealth([]) }
    finally { setLoading(false) }
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <EngineConfigSection />
      
      <Card className="p-6">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-lg font-semibold">Provider Health</h3>
            <p className="text-xs text-muted-foreground mt-1">Check connectivity of all enabled providers</p>
          </div>
          <button onClick={runHealthCheck} disabled={loading}
            className="rounded-lg px-3 py-1.5 text-xs font-medium hover:bg-muted border border-border">
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
                    <span className="size-1.5 rounded-full bg-green-400" /> Connected — {h.latency_ms}ms
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5 text-xs text-red-400">
                    <span className="size-1.5 rounded-full bg-red-400" /> {h.error || 'Error'}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
      <ProviderSetup mode="settings" />
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
              <button onClick={() => window.aic?.updateInstall?.()}
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

/* ─── Memory Tab ─── */

function MemoryTab() {
  const [contextWindow, setContextWindow] = useState(150000)
  const [maxMessages, setMaxMessages] = useState(50)
  const [autoSummarize, setAutoSummarize] = useState(true)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    const saved = localStorage.getItem('aic-ade-memory')
    if (saved) {
      const s = JSON.parse(saved)
      if (s.contextWindow) setContextWindow(s.contextWindow)
      if (s.maxMessages) setMaxMessages(s.maxMessages)
      if (s.autoSummarize !== undefined) setAutoSummarize(s.autoSummarize)
    }
  }, [])

  const save = () => {
    localStorage.setItem('aic-ade-memory', JSON.stringify({ contextWindow, maxMessages, autoSummarize }))
    setSaved(true); setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <HardDrive className="size-5" /> Memory
        </h3>
        <div className="space-y-4">
          <div>
            <label className="text-sm text-muted-foreground">Context Window (tokens)</label>
            <input type="number" value={contextWindow} onChange={(e) => setContextWindow(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-foreground outline-none focus:border-primary" />
          </div>
          <div>
            <label className="text-sm text-muted-foreground">Max Messages to Keep</label>
            <input type="number" value={maxMessages} onChange={(e) => setMaxMessages(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-foreground outline-none focus:border-primary" />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium">Auto-Summarize Old Messages</label>
              <p className="text-xs text-muted-foreground">Automatically compress old messages when context is full</p>
            </div>
            <button onClick={() => setAutoSummarize(!autoSummarize)}
              className={cn('relative h-5 w-9 rounded-full transition-colors', autoSummarize ? 'bg-primary' : 'bg-muted')}>
              <span className={cn('absolute top-0.5 size-4 rounded-full bg-background transition-all', autoSummarize ? 'left-4' : 'left-0.5')} />
            </button>
          </div>
          <button onClick={save} className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
            {saved ? 'Saved' : 'Save'}
          </button>
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
    <div>
      <PageHeader title="Settings" subtitle="Configure your AIC ADE workspace." />
      <div className="p-6">
        <div className="mb-6 flex flex-wrap gap-1 border-b border-border">
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

        {tab === 'General' && <GeneralTab updateDialogOpen={updateDialogOpen} onUpdateDialogOpenChange={onUpdateDialogOpenChange} />}
        {tab === 'Workspace' && <WorkspaceTab />}
        {tab === 'Appearance' && <AppearanceTab />}
        {tab === 'Providers' && <ProvidersTab />}
        {tab === 'Updates' && <UpdatesTab />}
        {tab === 'Memory' && <MemoryTab />}
        {tab === 'Developer' && <DeveloperTab />}
        {tab === 'Auto Save' && <AutoSaveTab />}
      </div>
    </div>
  )
}