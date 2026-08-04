import { useState, useEffect, useCallback } from 'react'
import {
  Cpu, Download, FolderOpen,
  Bug, Save, Trash2,
} from 'lucide-react'
import { Card, PageHeader } from './kit'
import { cn } from '../lib/utils'
import { GeneralTab } from './auth/AccountSettings'
import { ProviderSetup } from './auth/ProviderSetup'
import { profileApi, type LocalProfile } from '../lib/api/profile'
import { providerManageApi, type EnvConfig } from '../lib/api/provider_manage'
import { providersApi, type ProviderRecord, type ModelInfo } from '../lib/api/providers'

const tabs = [
  'General', 'Workspace', 'Providers',
  'Updates', 'Developer', 'Auto Save',
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
      // so the workspace/file tree pick it up immediately (mirrors ProjectPicker).
      await window.aic?.storeSet?.('projectRoot', root)
      onProjectRootChange?.(root)
      setSaved(true); setTimeout(() => setSaved(false), 2000) 
    }
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
  const [msg, setMsg] = useState('')

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
          const updated = await providersApi.fetchModelsAndUpdate(p.id, p.endpoint)
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
    setMsg('')
    try {
      // Persist per-tier provider selections to localStorage
      localStorage.setItem('aic-ade-engine-tiers', JSON.stringify({
        thinkerProvider,
        crafterProvider,
        sprinterProvider,
        visionProvider,
      }))

      const p = providers.find(x => x.name === thinkerProvider) || providers[0]
      const res = await providerManageApi.updateEnvConfig({
        provider_name: p?.name || '',
        base_url: p?.endpoint || '',
        api_key: p?.apiKey || '',
        thinker: thinkerModel,
        crafter: crafterModel,
        sprinter: sprinterModel,
        vision: visionModel,
      })
      setMsg('Engine updated successfully!')
      setTimeout(() => setMsg(''), 3000)

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
      setMsg('Failed: ' + (e?.message || String(e)))
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

function ProvidersTab() {
  const [providersVersion, setProvidersVersion] = useState(0)
  return (
    <div className="space-y-6 max-w-4xl">
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
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    const s = localStorage.getItem('aic-ade-autosave')
    if (s) {
      const cfg = JSON.parse(s)
      if (cfg.enabled !== undefined) setEnabled(cfg.enabled)
      if (cfg.interval) setInterval(cfg.interval)
    }
  }, [])

  const save = () => {
    localStorage.setItem('aic-ade-autosave', JSON.stringify({ enabled, interval }))
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
              <p className="text-xs text-muted-foreground">Automatically save conversations and project state to SQLite</p>
            </div>
            <button onClick={() => setEnabled(!enabled)}
              className={cn('relative h-5 w-9 rounded-full transition-colors', enabled ? 'bg-primary' : 'bg-muted')}>
              <span className={cn('absolute top-0.5 size-4 rounded-full bg-background transition-all', enabled ? 'left-4' : 'left-0.5')} />
            </button>
          </div>
          <div>
            <label className="text-sm text-muted-foreground">Save Interval (seconds)</label>
            <input type="number" value={interval} onChange={(e) => setInterval(Number(e.target.value))} disabled={!enabled}
              placeholder="30"
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-foreground outline-none focus:border-primary disabled:opacity-50" />
          </div>
          <button onClick={save} className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
            {saved ? 'Saved' : 'Save'}
          </button>
        </div>
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
        {tab === 'Developer' && <DeveloperTab />}
        {tab === 'Auto Save' && <AutoSaveTab />}
      </div>
    </div>
  )
}
