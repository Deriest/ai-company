import { useState, useEffect, useCallback } from 'react'
import {
  Cpu, Download, FolderOpen, Database, RotateCcw, KeyRound,
} from 'lucide-react'
import { Card, PageHeader } from './kit'
import { cn } from '../lib/utils'
import { GeneralTab } from './auth/AccountSettings'
import { ProviderSetup } from './auth/ProviderSetup'
import { GithubTokenField } from './GithubTokenField'
import { profileApi, type LocalProfile } from '../lib/api/profile'
import { providerManageApi, type EnvConfig } from '../lib/api/provider_manage'
import { providersApi, type ProviderRecord, type ModelInfo } from '../lib/api/providers'
import { backupApi, type BackupRecord, type BackupValidateResult } from '../lib/api/backup'

const tabs = [
  'General', 'Workspace', 'Providers',
  'Updates', 'Data',
] as const
export type SettingsTab = (typeof tabs)[number]
type Tab = SettingsTab

/* ─── Workspace Tab ─── */

function WorkspaceTab({ onProjectRootChange }: { onProjectRootChange?: (root: string | null) => void }) {
  const [root, setRoot] = useState('')
  const [saved, setSaved] = useState(false)
  const [autoOpen, setAutoOpen] = useState(true)
  const [rememberSession, setRememberSession] = useState(true)
  const [sessionName, setSessionName] = useState('')

  useEffect(() => {
    profileApi.get().then(p => { if (p?.projectRoot) setRoot(p.projectRoot) }).catch(() => {})
    try {
      const s = localStorage.getItem('aic-ade-workspace')
      if (s) {
        const cfg = JSON.parse(s)
        if (cfg.autoOpen !== undefined) setAutoOpen(cfg.autoOpen)
        if (cfg.rememberSession !== undefined) setRememberSession(cfg.rememberSession)
        if (cfg.sessionName) setSessionName(cfg.sessionName)
      }
    } catch {}
  }, [])

const handleSave = async () => {
    try { 
      await profileApi.update({ projectRoot: root })
      localStorage.setItem('aic-ade-workspace', JSON.stringify({ autoOpen, rememberSession, sessionName }))
      // BUG-6: Propagate the project root to the IPC store and App-level state
      // so the workspace/file tree pick up it immediately (mirrors ProjectPicker).
      await window.aic?.storeSet?.('projectRoot', root)
      onProjectRootChange?.(root)
      setSaved(true); setTimeout(() => setSaved(false), 2000) 
    }
    catch { /* ignore */ }
  }

  const handleBrowse = async () => {
    const dir = await window.aic?.selectDirectory?.()
    if (dir) setRoot(dir)
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
            <div className="mt-1 flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 transition-colors focus-within:border-primary">
              <FolderOpen className="size-4 shrink-0 text-muted-foreground/60" />
              <span className={cn("min-w-0 flex-1 truncate font-mono text-sm", root ? "text-foreground" : "text-muted-foreground/50")}>
                {root || 'No folder selected'}
              </span>
              <button
                type="button"
                onClick={handleBrowse}
                className="shrink-0 rounded-md bg-muted px-3 py-1 text-xs font-medium text-foreground transition-colors hover:bg-muted/70"
              >
                Browse…
              </button>
              {root && (
                <button
                  type="button"
                  onClick={() => setRoot('')}
                  className="shrink-0 text-[11px] text-muted-foreground/60 transition-colors hover:text-destructive"
                  title="Clear the default project root"
                >
                  Clear
                </button>
              )}
            </div>
            <p className="mt-1 text-[11px] text-muted-foreground/60">
              Pick the folder where dispatcher agents create projects — instead of the app data directory.
            </p>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium">Auto-open last project</label>
              <p className="text-xs text-muted-foreground">Open the last used project on startup</p>
            </div>
            <button onClick={() => setAutoOpen(!autoOpen)}
              className={cn('relative h-5 w-9 rounded-full transition-colors', autoOpen ? 'bg-primary' : 'bg-muted')}>
              <span className={cn('absolute top-0.5 size-4 rounded-full bg-background transition-all', autoOpen ? 'left-4' : 'left-0.5')} />
            </button>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium">Remember session</label>
              <p className="text-xs text-muted-foreground">Restore the last conversation on startup</p>
            </div>
            <button onClick={() => setRememberSession(!rememberSession)}
              className={cn('relative h-5 w-9 rounded-full transition-colors', rememberSession ? 'bg-primary' : 'bg-muted')}>
              <span className={cn('absolute top-0.5 size-4 rounded-full bg-background transition-all', rememberSession ? 'left-4' : 'left-0.5')} />
            </button>
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

function EngineConfigSection({ refreshKey = 0 }: { refreshKey?: number }) {
  const [cfg, setCfg] = useState<EnvConfig | null>(null)
  const [providers, setProviders] = useState<ProviderRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)

  // Per-tier provider+model state
  const [thinkerProvider, setThinkerProvider] = useState<string>('')
  const [crafterProvider, setCrafterProvider] = useState<string>('')
  const [sprinterProvider, setSprinterProvider] = useState<string>('')
  const [visionProvider, setVisionProvider] = useState<string>('')
  const [thinkerModels, setThinkerModels] = useState<ModelInfo[]>([])
  const [crafterModels, setCrafterModels] = useState<ModelInfo[]>([])
  const [sprinterModels, setSprinterModels] = useState<ModelInfo[]>([])
  const [visionModels, setVisionModels] = useState<ModelInfo[]>([])
  const [thinkerModel, setThinkerModel] = useState<string>('')
  const [crafterModel, setCrafterModel] = useState<string>('')
  const [sprinterModel, setSprinterModel] = useState<string>('')
  const [visionModel, setVisionModel] = useState<string>('')

  // BUG-16 FIX: Filter out known-bad models from dropdowns — only clearly
  // internal prefixes (combo/, iamhc/, big-pickle). DeepSeek/r1 models are
  // legitimate and must NOT be dropped (DeepSeek users got an empty dropdown).
  const filterValidModels = (models: ModelInfo[]) => models.filter(m => {
    const id = m.id.toLowerCase();
    if (id.startsWith("combo/") || id.startsWith("iamhc/")) return false;
    if (id.includes("big-pickle")) return false;
    return true;
  })

  const loadEngineConfig = useCallback(async () => {
    setLoading(true)
    try {
      const [envCfg, pList] = await Promise.all([
        providerManageApi.getEnvConfig(),
        providersApi.list()
      ])
      setCfg(envCfg)
      setProviders(pList)

      // Restore per-tier provider selections from localStorage first
      let tp: string, cp: string, sp: string, vp: string;
      try {
        const saved = JSON.parse(localStorage.getItem('aic-ade-engine-tiers') || '{}')
        tp = saved.thinkerProvider || envCfg.provider_name
        cp = saved.crafterProvider || envCfg.provider_name
        sp = saved.sprinterProvider || envCfg.provider_name
        vp = saved.visionProvider || envCfg.provider_name
      } catch {
        tp = cp = sp = vp = envCfg.provider_name
      }

      setThinkerProvider(tp)
      setCrafterProvider(cp)
      setSprinterProvider(sp)
      setVisionProvider(vp)

      // Load models per restored provider — ensures isolation
      const tP = pList.find(p => p.name === tp)
      const cP = pList.find(p => p.name === cp)
      const sP = pList.find(p => p.name === sp)
      const vP = pList.find(p => p.name === vp)
      setThinkerModels(tP?.models || [])
      setCrafterModels(cP?.models || [])
      setSprinterModels(sP?.models || [])
      setVisionModels((vP?.models || []).filter(m => m.capabilities.vision))

      setThinkerModel(envCfg.thinker || '')
      setCrafterModel(envCfg.crafter || '')
      setSprinterModel(envCfg.sprinter || '')
      setVisionModel(envCfg.vision || '')

      // Override with IPC-persisted config (disk, survives app restart)
      try {
        if (window.aic) {
          const ipcCfg = await window.aic.storeGet('engineConfig') as Record<string, string> | null
          if (ipcCfg) {
            if (ipcCfg.thinkerProvider) setThinkerProvider(ipcCfg.thinkerProvider)
            if (ipcCfg.crafterProvider) setCrafterProvider(ipcCfg.crafterProvider)
            if (ipcCfg.sprinterProvider) setSprinterProvider(ipcCfg.sprinterProvider)
            if (ipcCfg.visionProvider) setVisionProvider(ipcCfg.visionProvider)
            if (ipcCfg.thinkerModel) setThinkerModel(ipcCfg.thinkerModel)
            if (ipcCfg.crafterModel) setCrafterModel(ipcCfg.crafterModel)
            if (ipcCfg.sprinterModel) setSprinterModel(ipcCfg.sprinterModel)
            if (ipcCfg.visionModel) setVisionModel(ipcCfg.visionModel)
            // Re-resolve models from the IPC provider names
            const tP2 = pList.find(p => p.name === ipcCfg.thinkerProvider)
            const cP2 = pList.find(p => p.name === ipcCfg.crafterProvider)
            const sP2 = pList.find(p => p.name === ipcCfg.sprinterProvider)
            const vP2 = pList.find(p => p.name === ipcCfg.visionProvider)
            if (tP2) setThinkerModels(tP2.models || [])
            if (cP2) setCrafterModels(cP2.models || [])
            if (sP2) setSprinterModels(sP2.models || [])
            if (vP2) setVisionModels((vP2.models || []).filter(m => m.capabilities.vision))
          }
        }
      } catch (e) {
        console.error('Failed to load engine config from IPC store', e)
      }
    } catch (e) {
      console.error('Failed to load engine config', e)
    }
    setLoading(false)
  }, [])

  // Reload when a provider is saved upstream (ProviderRegistry) so the
  // provider dropdown includes newly added providers (BUG-4).
  useEffect(() => { void loadEngineConfig() }, [loadEngineConfig, refreshKey])

  const handleTierProviderChange = useCallback((tier: 'thinker' | 'crafter' | 'sprinter' | 'vision', pName: string) => {
    const p = providers.find(x => x.name === pName)
    if (!p) return
    const pModels = p.models || []
    // BUG-2: The backend EnvConfig is single-provider — per-tier provider
    // selection would send one tier's model to another tier's endpoint.
    // Restrict every tier to the same provider when any tier changes.
    const keep = (m: string) => pModels.some(mm => mm.id === m) ? m : ''
    setThinkerProvider(pName); setThinkerModels(pModels); setThinkerModel(keep(thinkerModel))
    setCrafterProvider(pName); setCrafterModels(pModels); setCrafterModel(keep(crafterModel))
    setSprinterProvider(pName); setSprinterModels(pModels); setSprinterModel(keep(sprinterModel))
    setVisionProvider(pName); setVisionModels(pModels.filter(m => m.capabilities.vision)); setVisionModel(keep(visionModel))
  }, [providers, thinkerModel, crafterModel, sprinterModel, visionModel])

  const fetchAllModels = useCallback(async () => {
    setLoading(true)
    try {
      // Get fresh provider list from API to avoid stale closure
      const currentProviders = await providersApi.list()
      const pList: ProviderRecord[] = []
      for (const p of currentProviders) {
        try {
          // fetchModelsAndUpdate returns the updated provider record directly
          const updated = await providersApi.fetchModelsAndUpdate(p.id)
          pList.push(updated)
        } catch (e) {
          console.error('Fetch models failed for', p.name, e)
          pList.push(p) // keep existing data on failure
        }
      }
      setProviders(pList)
      // Refresh current selections — models are isolated per provider
      const tp = pList.find(p => p.name === thinkerProvider)
      const cp = pList.find(p => p.name === crafterProvider)
      const sp = pList.find(p => p.name === sprinterProvider)
      const vp = pList.find(p => p.name === visionProvider)
      if (tp) setThinkerModels(tp.models || [])
      if (cp) setCrafterModels(cp.models || [])
      if (sp) setSprinterModels(sp.models || [])
      if (vp) setVisionModels((vp.models || []).filter(m => m.capabilities.vision))

      // Persist fresh provider selections
      localStorage.setItem('aic-ade-engine-tiers', JSON.stringify({
        thinkerProvider,
        crafterProvider,
        sprinterProvider,
        visionProvider,
      }))
    } catch (e) { console.error('Fetch models failed', e) }
    setLoading(false)
  }, [thinkerProvider, crafterProvider, sprinterProvider, visionProvider])

  const handleSave = async () => {
    setSaving(true)
    setMsg(null)
    try {
      // Persist per-tier provider selections to localStorage
      localStorage.setItem('aic-ade-engine-tiers', JSON.stringify({
        thinkerProvider,
        crafterProvider,
        sprinterProvider,
        visionProvider,
      }))

      const p = providers.find(x => x.name === thinkerProvider) || providers[0]
      await providerManageApi.updateEnvConfig({
        provider_name: p?.name || '',
        base_url: p?.endpoint || '',
        api_key: p?.apiKey || '',
        thinker: thinkerModel,
        crafter: crafterModel,
        sprinter: sprinterModel,
        vision: visionModel,
      })
      setMsg({ kind: 'success', text: 'Engine updated successfully!' })
      setTimeout(() => setMsg(null), 3000)

      // Persist to IPC store (disk, survives app restart)
      if (window.aic) {
        await window.aic.storeSet('engineConfig', {
          thinkerProvider,
          crafterProvider,
          sprinterProvider,
          visionProvider,
          thinkerModel,
          crafterModel,
          sprinterModel,
          visionModel,
        })
      }
    } catch (e: any) {
      setMsg({ kind: 'error', text: 'Failed: ' + (e?.message || String(e)) })
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

      {msg && (
        <div className={cn(
          'mb-4 rounded-lg border px-4 py-2 text-sm',
          msg.kind === 'error'
            ? 'bg-destructive/10 border-destructive/20 text-destructive'
            : 'bg-success/10 border-success/20 text-success',
        )}>
          {msg.text}
        </div>
      )}

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
              {filterValidModels(thinkerModels).map(m => <option key={m.id} value={m.id}>{m.name || m.id}</option>)}
            </select>
          </div>
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
              {filterValidModels(crafterModels).map(m => <option key={m.id} value={m.id}>{m.name || m.id}</option>)}
            </select>
          </div>
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
              {filterValidModels(sprinterModels).map(m => <option key={m.id} value={m.id}>{m.name || m.id}</option>)}
            </select>
          </div>
        </div>
        {/* VISION */}
        <div className="rounded-lg border border-info/40 bg-info/5 p-4">
          <div className="flex items-center gap-3 mb-3">
            <span className="text-sm font-semibold text-info w-24">Vision</span>
            <select value={visionProvider} onChange={e => handleTierProviderChange('vision', e.target.value)} className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm">
              <option value="">Select Provider...</option>
              {providers.map(p => <option key={p.id} value={p.name}>{p.name}</option>)}
            </select>
            <select value={visionModel} onChange={e => setVisionModel(e.target.value)} className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono">
              <option value="">Select Vision Model...</option>
              {filterValidModels(visionModels).map(m => <option key={m.id} value={m.id}>{m.name || m.id}</option>)}
            </select>
          </div>
          <p className="text-[11px] text-muted-foreground">Only models marked as vision-capable are shown. Image attachments use this tier exclusively.</p>
        </div>
      </div>
    </Card>
  )
}

/* ─── Providers Tab ─── */

function GithubTokenCard() {
  const [value, setValue] = useState("")
  const [hasStored, setHasStored] = useState(false)
  const [cleared, setCleared] = useState(false)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    profileApi.get().then(p => {
      if (p?.github_token) setHasStored(true)
    }).catch(() => {})
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setMsg(null)
    try {
      const payload: { github_token?: string | null } = {}
      if (value.trim()) {
        payload.github_token = value.trim()
      } else if (cleared) {
        payload.github_token = null
      }
      if (Object.keys(payload).length > 0) {
        await profileApi.update(payload as { github_token: string | null })
        setHasStored(Boolean(payload.github_token) && payload.github_token !== null)
        setValue("")
        setCleared(false)
        setMsg({ kind: 'success', text: payload.github_token ? 'GitHub token saved' : 'GitHub token removed' })
      } else {
        setMsg({ kind: 'success', text: 'No changes — token kept as stored' })
      }
    } catch (e) {
      setMsg({ kind: 'error', text: 'Failed: ' + (e instanceof Error ? e.message : String(e)) })
    }
    setSaving(false)
  }

  return (
    <Card className="p-6">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold">
        <KeyRound className="size-4 text-muted-foreground" /> GitHub Integration
      </h3>
      <GithubTokenField
        id="ghp-settings"
        value={value}
        onChange={(v) => { setValue(v); setCleared(false) }}
        onClear={() => { setValue(""); setCleared(true) }}
        hasStored={hasStored}
        disabled={saving}
      />
      {msg && (
        <p className={cn('mt-2 text-xs', msg.kind === 'error' ? 'text-destructive' : 'text-success')}>{msg.text}</p>
      )}
      <div className="mt-4 flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Save Token'}
        </button>
        <span className="text-[11px] text-muted-foreground/60">
          {hasStored && !value ? 'A token is already stored.' : value ? 'Will overwrite the stored token.' : 'Optional — leave blank to keep.'}
        </span>
      </div>
    </Card>
  )
}

function ProvidersTab() {
  const [providersVersion, setProvidersVersion] = useState(0)
  return (
    <div className="space-y-6 max-w-4xl">
      <GithubTokenCard />
      <ProviderSetup mode="settings" onProviderSaved={() => setProvidersVersion(v => v + 1)} />
      <EngineConfigSection refreshKey={providersVersion} />
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
    downloading: 'Downloading…', ready_to_install: 'Ready to install',
    ready_to_restart: 'Restart to apply', error: 'Update error', unknown: '—',
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
            {updateState?.status === 'ready_to_restart' && (
              <button onClick={() => window.aic?.updateQuitAndInstall?.()}
                className="rounded-lg bg-success px-4 py-2 text-sm font-medium text-white">
                Restart & Apply
              </button>
            )}
            {updateState?.notifyBeforeInstall && (
              <p className="text-xs text-muted-foreground">
                A new version is available and will download after you confirm here.
              </p>
            )}
          </div>
        </div>
      </Card>
    </div>
  )
}

/* ─── Data Tab (Backup / Restore) ─── */

function formatSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '—'
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${bytes} B`
}

function DataTab() {
  const [backups, setBackups] = useState<BackupRecord[]>([])
  const [busy, setBusy] = useState(false)
  const [restoring, setRestoring] = useState(false)
  const [validated, setValidated] = useState<Record<string, BackupValidateResult>>({})
  const [msg, setMsg] = useState<{ kind: 'success' | 'error' | 'info'; text: string } | null>(null)

  const refresh = useCallback(async () => {
    try {
      setBackups(await backupApi.listBackups())
    } catch {
      // keep the last known list — backend may be down
    }
  }, [])

  useEffect(() => { void refresh() }, [refresh])

  const handleCreate = async () => {
    if (busy || restoring) return
    setBusy(true)
    setMsg(null)
    try {
      // Create the archive in the backend data dir, then offer it through the
      // native save dialog.
      const created = await backupApi.createBackup()
      const res = await window.aic?.backupCreateTo?.(created.filename)
      if (res?.cancelled) {
        setMsg({ kind: 'info', text: 'Backup created but save cancelled.' })
      } else if (res?.saved) {
        setMsg({ kind: 'success', text: `Backup created: ${created.filename}` })
      } else {
        setMsg({ kind: 'error', text: `Backup failed: ${res?.error || 'unknown error'}` })
      }
      void refresh()
    } catch (e: any) {
      setMsg({ kind: 'error', text: 'Backup failed: ' + (e?.message || String(e)) })
    }
    setBusy(false)
  }

  const handleRestore = async () => {
    if (busy || restoring) return
    const ok = window.confirm('This will replace all current data. A safety copy will be kept. Continue?')
    if (!ok) return
    setRestoring(true)
    setMsg(null)
    try {
      const res = await window.aic?.backupRestore?.()
      if (res?.restored) {
        setMsg({ kind: 'success', text: 'Restore complete. Reloading the app…' })
        setTimeout(() => window.location.reload(), 1500)
      } else if (res?.error === 'cancelled') {
        setMsg(null)
      } else {
        setMsg({ kind: 'error', text: `Restore failed: ${res?.error || 'unknown error'}${res?.rollbackDone ? ' — previous data restored.' : ''}` })
      }
    } catch (e: any) {
      setMsg({ kind: 'error', text: 'Restore failed: ' + (e?.message || String(e)) })
    }
    setRestoring(false)
  }

  const handleValidate = async (filename: string) => {
    try {
      const result = await backupApi.validateBackup(filename)
      setValidated(prev => ({ ...prev, [filename]: result }))
    } catch (e: any) {
      setValidated(prev => ({ ...prev, [filename]: { valid: false, error: e?.message || String(e) } }))
    }
  }

  const msgStyle =
    msg?.kind === 'error' ? 'bg-destructive/10 border-destructive/20 text-destructive'
    : msg?.kind === 'success' ? 'bg-success/10 border-success/20 text-success'
    : 'bg-info/10 border-info/20 text-info'

  return (
    <div className="space-y-6 max-w-2xl">
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-1 flex items-center gap-2">
          <Database className="size-5" /> Backups
        </h3>
        <p className="text-xs text-muted-foreground">
          Back up all conversations, settings and files, or restore an earlier backup.
          A restore replaces the current data — a safety copy is kept for rollback.
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button onClick={() => void handleCreate()} disabled={busy || restoring}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
            {busy ? 'Creating…' : 'Create Backup'}
          </button>
          <button onClick={() => void handleRestore()} disabled={busy || restoring}
            className="inline-flex items-center gap-1.5 rounded-lg border border-destructive/40 px-4 py-2 text-sm font-medium text-destructive hover:bg-destructive/10 disabled:opacity-50">
            <RotateCcw className="size-3.5" />
            {restoring ? 'Restoring…' : 'Restore from Backup'}
          </button>
        </div>

        {msg && <div className={cn('mt-4 rounded-lg border px-4 py-2 text-sm', msgStyle)}>{msg.text}</div>}
      </Card>

      <Card className="p-6">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-semibold">Saved Backups</h4>
          <button onClick={() => void refresh()} className="text-xs text-muted-foreground hover:text-foreground" disabled={busy || restoring}>
            Refresh
          </button>
        </div>
        {backups.length === 0 ? (
          <p className="text-sm text-muted-foreground">No backups yet. Create one to get started.</p>
        ) : (
          <ul className="divide-y divide-border">
            {backups.map(b => {
              const v = validated[b.filename]
              return (
                <li key={b.filename} className="py-2.5">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate font-mono text-sm">{b.filename}</div>
                      <div className="text-xs text-muted-foreground">
                        {formatSize(b.size)} · {new Date(b.created_at).toLocaleString()}
                      </div>
                    </div>
                    <button onClick={() => void handleValidate(b.filename)} disabled={busy || restoring}
                      className="shrink-0 rounded border border-border px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50">
                      Validate
                    </button>
                  </div>
                  {v && (
                    <p className={cn('mt-1 text-xs', v.valid ? 'text-success' : 'text-destructive')}>
                      {v.valid ? `Valid backup · ${v.entries ?? '?'} entries${v.version ? ` · v${v.version}` : ''}` : `Invalid backup: ${v.error || 'unknown error'}`}
                    </p>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </Card>
    </div>
  )
}

/* ─── Main Settings View ─── */

export function SettingsView({
  initialTab, updateDialogOpen, onUpdateDialogOpenChange, onProfileUpdated, onProjectRootChange,
}: {
  initialTab?: Tab
  updateDialogOpen?: boolean
  onUpdateDialogOpenChange?: (open: boolean) => void
  onProfileUpdated?: (profile: LocalProfile) => void
  onProjectRootChange?: (root: string | null) => void
} = {}) {
  const [tab, setTab] = useState<Tab>(() => {
    // BUG-23: Prefer initialTab when it differs from the stored tab.
    if (initialTab && tabs.includes(initialTab as Tab)) return initialTab as Tab
    const saved = localStorage.getItem('aic-ade-settings-tab')
    if (saved && tabs.includes(saved as Tab)) return saved as Tab
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

        {tab === 'General' && <GeneralTab updateDialogOpen={updateDialogOpen} onUpdateDialogOpenChange={onUpdateDialogOpenChange} onProfileUpdated={onProfileUpdated} />}
        {tab === 'Workspace' && <WorkspaceTab onProjectRootChange={onProjectRootChange} />}
        {tab === 'Providers' && <ProvidersTab />}
        {tab === 'Updates' && <UpdatesTab />}
        {tab === 'Data' && <DataTab />}
      </div>
    </div>
  )
}
