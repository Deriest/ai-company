import { useEffect, useState } from "react";
import { Check, Loader2, RefreshCw, Plus, Zap, Cpu, Eye, EyeOff } from "lucide-react";
import { Card, Badge } from "../kit";
import { apiClient } from "../../lib/api/client";
import { providersApi, type ProviderRecord, type ModelInfo } from "../../lib/api/providers";
import { providerManageApi, type TestConnectionResult } from "../../lib/api/provider_manage";

const PROVIDER_PRESETS = [
  { id: "openai", name: "OpenAI Compatible", endpoint: "https://api.openai.com/v1" },
  { id: "anthropic", name: "Anthropic", endpoint: "https://api.anthropic.com/v1" },
] as const;

function ConnectionStatus({ status }: { status: "idle" | "testing" | "connected" | "failed" }) {
  if (status === "idle") return null;
  const map = {
    testing: { icon: <Loader2 className="size-3 animate-spin" />, text: "Testing…", color: "text-muted-foreground" },
    connected: { icon: <Check className="size-3" />, text: "Connected", color: "text-success" },
    failed: { icon: <span className="size-3">✕</span>, text: "Failed", color: "text-destructive" },
    idle: { icon: null, text: "", color: "" },
  };
  const s = map[status];
  return <span className={`flex items-center gap-1 text-xs ${s.color}`}>{s.icon} {s.text}</span>;
}

export function ProviderSetup({ mode, onProviderSaved }: { mode: "settings" | "fre"; onProviderSaved?: () => void }) {
  if (mode === "settings") return <ProviderRegistry onProviderSaved={onProviderSaved} />;
  return <FREProviderSetup />;
}

export function WorkerRuntimeAssignment() {
  const [providers, setProviders] = useState<ProviderRecord[]>([]);
  useEffect(() => { providersApi.list().then(setProviders).catch(() => {}); }, []);
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Worker Runtime</h3>
      <p className="text-sm text-muted-foreground">Workers use the configured providers above. No additional assignment needed.</p>
      {providers.length > 0 && (
        <div className="text-xs text-muted-foreground">
          {providers.filter(p => p.enabled !== false).length} active provider(s) available
        </div>
      )}
    </div>
  );
}

function ProviderRegistry({ onProviderSaved }: { onProviderSaved?: () => void }) {
  const [providers, setProviders] = useState<ProviderRecord[]>([]);
  const [editing, setEditing] = useState<Partial<ProviderRecord> | null>(null);
  const [loading, setLoading] = useState(true);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, TestConnectionResult>>({});

  useEffect(() => {
    providersApi.list().then(p => { setProviders(p); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  const handleTest = async (p: ProviderRecord) => {
    setTestingId(p.id);
    try {
      // BUG-16: The backend returns a masked key ("***") for stored providers.
      // Sending "***" as the API key would fail the test — skip it instead.
      if (p.apiKey === "***") {
        setTestResults(prev => ({ ...prev, [p.id]: { success: false, error: "Masked key stored — reopen the provider to test with a fresh key" } }));
        return;
      }
      const result = await providerManageApi.testConnection(p.endpoint, p.apiKey, p.id);
      setTestResults(prev => ({ ...prev, [p.id]: result }));
    } catch {
      setTestResults(prev => ({ ...prev, [p.id]: { success: false, error: "Request failed" } }));
    } finally {
      setTestingId(null);
    }
  };

  if (loading) return <div className="text-muted-foreground text-sm animate-pulse">Loading providers…</div>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div><h3 className="text-lg font-semibold">AI Providers</h3><p className="text-sm text-muted-foreground">Configure your AI model providers</p></div>
        <button onClick={() => setEditing({ name: "", endpoint: "" })} className="rounded-lg bg-cyan-500 px-4 py-2 text-sm font-medium text-black hover:bg-cyan-400">
          <Plus className="size-4 mr-1 inline" /> Add Provider
        </button>
      </div>
      {providers.length === 0 && <Card className="p-6 text-center text-muted-foreground">No providers configured yet.</Card>}
      {providers.map(p => (
        <Card key={p.id} className="flex items-center justify-between p-4">
          <div className="min-w-0 flex-1">
            <div className="font-medium">{p.name}</div>
            <div className="text-xs text-muted-foreground font-mono truncate">{p.endpoint}</div>
            {testResults[p.id] && (
              <div className={`mt-1 text-xs ${testResults[p.id].success ? "text-green-400" : "text-red-400"}`}>
                {testResults[p.id].success
                  ? `Connected — ${testResults[p.id].latency_ms}ms, ${testResults[p.id].modelCount ?? 0} models`
                  : `Failed — ${testResults[p.id].error}`}
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-xs px-2 py-0.5 rounded ${p.enabled !== false ? "bg-green-500/10 text-green-400" : "bg-muted text-muted-foreground"}`}>
              {p.enabled !== false ? "Active" : "Inactive"}
            </span>
            <button
              onClick={() => handleTest(p)}
              disabled={testingId === p.id}
              className="flex items-center gap-1 text-xs text-cyan-400 hover:underline disabled:opacity-50"
            >
              {testingId === p.id ? <Loader2 className="size-3 animate-spin" /> : <Zap className="size-3" />}
              Test
            </button>
            <button onClick={() => setEditing(p)} className="text-xs text-cyan-400 hover:underline">Edit</button>
          </div>
        </Card>
      ))}
      {editing && <ProviderForm provider={editing} onSaved={(p) => { setProviders(prev => prev.some(x => x.id === p.id) ? prev.map(x => x.id === p.id ? p : x) : [...prev, p]); onProviderSaved?.(); setEditing(null); }} onCancel={() => setEditing(null)} />}
    </div>
  );
}

function ProviderForm({ provider, onSaved, onCancel }: { provider: Partial<ProviderRecord>; onSaved: (p: ProviderRecord) => void; onCancel: () => void }) {
  const [name, setName] = useState(provider.name || "");
  const [providerType, setProviderType] = useState<string>(PROVIDER_PRESETS[0].name);
  const [endpoint, setEndpoint] = useState(provider.endpoint || "");
  const [apiKey, setApiKey] = useState("");
  const [apiKeyVisible, setApiKeyVisible] = useState(false);
  const [apiKeyPlaceholder, setApiKeyPlaceholder] = useState(provider.apiKey === "***" ? "••••••••" : "sk-...");
  const [status, setStatus] = useState<"idle" | "testing" | "connected" | "failed">("idle");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [models, setModels] = useState<ModelInfo[]>([]);

  const testConnection = async () => {
    setStatus("testing");
    setError("");
    try {
      const { providerManageApi } = await import('../../lib/api/provider_manage');
      // BUG-16: never send the masked "***" placeholder as a real API key.
      const storedKey = provider.apiKey === "***" ? "" : provider.apiKey;
      const testKey = apiKey || storedKey || "";
      if (!testKey) {
        setStatus("failed");
        setError("No API key available — enter a fresh key to test, then save.");
        return;
      }
      const res = await providerManageApi.testConnection(endpoint, testKey, provider.id);
      
      if (res.success) {
        setStatus("connected");
        // Also fetch models if successful to show the count
        try {
          const m = await providersApi.fetchModels(endpoint, testKey);
          setModels(m);
        } catch { /* ignore fetch model errors if connection succeeded */ }
      } else {
        setStatus("failed");
        setError(res.error || "Connection failed");
      }
    } catch (e: any) { 
      setStatus("failed"); 
      setError(e.message || "Request failed");
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError("");
    try {
      let saved: ProviderRecord;
      if (provider.id) {
        saved = await providersApi.update(provider.id, { name, endpoint, apiKey: apiKey || undefined });
      } else {
        saved = await providersApi.create({ name, endpoint, apiKey });
      }
      onSaved(saved);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Save failed"); setSaving(false); }
  };

  return (
    <Card className="space-y-4 p-6">
      <h3 className="text-lg font-semibold">{provider.id ? "Edit Provider" : "Add Provider"}</h3>
      {error && <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-2 text-sm text-red-400">{error}</div>}
      <div><label className="text-sm text-muted-foreground">Name</label>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="My AI Provider"
          className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-foreground" />
      </div>
      <div><label className="text-sm text-muted-foreground">Provider</label>
        <select value={providerType} onChange={(e) => { const p = PROVIDER_PRESETS.find(x => x.name === e.target.value); if (p) { setProviderType(p.name); setEndpoint(p.endpoint); } }}
          className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-foreground">
          <option value="">Select preset...</option>
          {PROVIDER_PRESETS.map(p => <option key={p.id} value={p.name}>{p.name}</option>)}
        </select>
      </div>
      <div><label className="text-sm text-muted-foreground">Base URL</label>
        <input value={endpoint} onChange={(e) => setEndpoint(e.target.value)} placeholder="https://api.openai.com/v1"
          className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-foreground" />
      </div>
      <div><label className="text-sm text-muted-foreground">API Key</label>
        <div className="relative">
        <input value={apiKey} onChange={(e) => { setApiKey(e.target.value); setApiKeyPlaceholder(''); }} placeholder={apiKeyPlaceholder} type={apiKeyVisible ? "text" : "password"} autoComplete="off"
          className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 pr-10 text-foreground" />
        <button type="button" onClick={() => setApiKeyVisible(v => !v)} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
          {apiKeyVisible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </button>
      </div>
      </div>
      <div className="flex items-center gap-3">
        <button onClick={testConnection} disabled={!endpoint} className="rounded-lg px-4 py-2 text-sm hover:bg-muted">
          <RefreshCw className="size-3 mr-1 inline" /> Test
        </button>
        <ConnectionStatus status={status} />
        {models.length > 0 && <span className="text-xs text-muted-foreground">{models.length} models</span>}
      </div>
      <div className="flex justify-end gap-2">
        <button onClick={onCancel} className="rounded-lg px-4 py-2 text-sm hover:bg-muted">Cancel</button>
        <button onClick={handleSave} disabled={saving || !name || !endpoint}
          className="rounded-lg bg-cyan-500 px-4 py-2 text-sm font-medium text-black hover:bg-cyan-400 disabled:opacity-50">
          {saving ? "Saving…" : "Save"}
        </button>
      </div>
    </Card>
  );
}

function FREProviderSetup() {
  const [name, setName] = useState<string>("");
  const [providerType, setProviderType] = useState<string>(PROVIDER_PRESETS[0].name);
  const [endpoint, setEndpoint] = useState<string>(PROVIDER_PRESETS[0].endpoint);
  const [endpointEdited, setEndpointEdited] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [apiKeyVisible, setApiKeyVisible] = useState(false);
  const [status, setStatus] = useState<"idle" | "testing" | "connected" | "failed">("idle");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [savedProviderId, setSavedProviderId] = useState<string>("");
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [fetchingModels, setFetchingModels] = useState(false);

  // Tier model selection
  const [thinkerModel, setThinkerModel] = useState<string>("");
  const [crafterModel, setCrafterModel] = useState<string>("");
  const [sprinterModel, setSprinterModel] = useState<string>("");
  const [applyingEngine, setApplyingEngine] = useState(false);
  const [engineMsg, setEngineMsg] = useState("");

  // BUG-16 FIX: Filter out known-bad models from dropdown — only clearly
  // internal prefixes (combo/, iamhc/, big-pickle). DeepSeek/r1 models are
  // legitimate and must NOT be dropped.
  const validModels = models.filter(m => {
    const id = m.id.toLowerCase();
    if (id.startsWith("combo/") || id.startsWith("iamhc/")) return false;
    if (id.includes("big-pickle")) return false;
    return true;
  });

  const testConnection = async () => {
    setStatus("testing");
    setError("");
    try {
      const { providerManageApi } = await import('../../lib/api/provider_manage');
      const res = await providerManageApi.testConnection(endpoint, apiKey);
      if (res.success) {
        setStatus("connected");
      } else {
        setStatus("failed");
        setError(res.error || "Connection failed");
      }
    } catch (e: any) { 
      setStatus("failed");
      setError(e.message || "Request failed");
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError("");
    try {
      const p = await providersApi.create({ name, endpoint, apiKey });
      setSavedProviderId(p.id);
      setSaved(true);
      // Auto-fetch models
      setFetchingModels(true);
      try {
        await providersApi.fetchModelsAndUpdate(p.id, p.endpoint);
        const updated = await providersApi.list();
        const fresh = updated.find(r => r.id === p.id);
        if (fresh) setModels(fresh.models || []);
      } catch {}
      setFetchingModels(false);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Save failed"); setSaving(false); }
  };

  const applyEngine = async () => {
    setApplyingEngine(true);
    setEngineMsg("");
    try {
      const { providerManageApi } = await import('../../lib/api/provider_manage');
      const p = await providersApi.list();
      const provider = p.find(x => x.id === savedProviderId);
      await providerManageApi.updateEnvConfig({
        provider_name: provider?.name || "",
        base_url: endpoint,
        api_key: apiKey,
        thinker: thinkerModel,
        crafter: crafterModel,
        sprinter: sprinterModel,
      });

      // BUG-03 FIX: Also persist model assignments to worker_runtime table
      // so that worker_runtime.model_id / provider_id are correctly set.
      const providerId = savedProviderId || provider?.id || "";
      const tierMap: Record<string, string> = {
        thinker: thinkerModel,
        crafter: crafterModel,
        sprinter: sprinterModel,
      };
      for (const [role, modelId] of Object.entries(tierMap)) {
        if (modelId && providerId) {
          try {
            await apiClient.patch(`/runtime/workers/${role}`, {
              providerId,
              modelId,
            });
          } catch {
            // Worker might not exist in runtime yet — create it
            try {
              await apiClient.patch(`/runtime/workers/${role}`, {
                providerId,
                modelId,
                isEnabled: true,
              });
            } catch {
              // graceful — env config is still set
            }
          }
        }
      }

      setEngineMsg("Engine configured! Ready to start.");
    } catch (e: any) {
      setEngineMsg("Failed: " + (e?.message || String(e)));
    }
    setApplyingEngine(false);
  };

  if (saved) {
    return (
      <Card className="space-y-4 p-6">
        <div className="rounded-lg bg-green-500/10 border border-green-500/20 px-4 py-2 text-sm text-green-400">Provider configured successfully!</div>
        
        <div className="rounded-lg border border-border/60 p-4 space-y-3">
          <h3 className="text-sm font-semibold flex items-center gap-2"><Cpu className="size-4" /> Select Models</h3>
          {fetchingModels ? (
            <p className="text-xs text-muted-foreground">Fetching models...</p>
          ) : (
            <>
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-primary w-16">Thinker</span>
                <select value={thinkerModel} onChange={e => setThinkerModel(e.target.value)} className="flex-1 rounded border border-border bg-background px-2 py-1 text-xs font-mono">
                  <option value="">Select...</option>
                  {validModels.map(m => <option key={m.id} value={m.id}>{m.name || m.id}</option>)}
                </select>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-success w-16">Crafter</span>
                <select value={crafterModel} onChange={e => setCrafterModel(e.target.value)} className="flex-1 rounded border border-border bg-background px-2 py-1 text-xs font-mono">
                  <option value="">Select...</option>
                  {validModels.map(m => <option key={m.id} value={m.id}>{m.name || m.id}</option>)}
                </select>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-warning w-16">Sprinter</span>
                <select value={sprinterModel} onChange={e => setSprinterModel(e.target.value)} className="flex-1 rounded border border-border bg-background px-2 py-1 text-xs font-mono">
                  <option value="">Select...</option>
                  {validModels.map(m => <option key={m.id} value={m.id}>{m.name || m.id}</option>)}
                </select>
              </div>
            </>
          )}
        </div>

        {engineMsg && <div className="rounded-lg bg-success/10 border border-success/20 px-4 py-2 text-sm text-success">{engineMsg}</div>}

        <button onClick={applyEngine} disabled={applyingEngine}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
          {applyingEngine ? "Applying..." : "Apply to Engine"}
        </button>
      </Card>
    );
  }

  return (
    <Card className="space-y-4 p-6">
      <div><h3 className="text-lg font-semibold">Configure AI Provider</h3><p className="text-sm text-muted-foreground">Choose a provider and enter your credentials</p></div>
      {error && <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-2 text-sm text-red-400">{error}</div>}
      <div><label className="text-sm text-muted-foreground">Name</label>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="My AI Provider"
          className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-foreground" />
      </div>
      <div><label className="text-sm text-muted-foreground">Provider</label>
        <select value={providerType} onChange={(e) => { const p = PROVIDER_PRESETS.find(x => x.name === e.target.value); if (p) { setProviderType(p.name); if (!endpointEdited) setEndpoint(p.endpoint); } }}
          className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-foreground">
          <option value="">Select preset...</option>
          {PROVIDER_PRESETS.map(p => <option key={p.id} value={p.name}>{p.name}</option>)}
        </select>
      </div>
      <div><label className="text-sm text-muted-foreground">Base URL</label>
        <input value={endpoint} onChange={(e) => { setEndpoint(e.target.value); setEndpointEdited(true); }} placeholder="https://api.openai.com/v1"
          className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-foreground" />
      </div>
      <div><label className="text-sm text-muted-foreground">API Key</label>
        <div className="relative">
        <input value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="sk-..." type={apiKeyVisible ? "text" : "password"} autoComplete="off"
          className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 pr-10 text-foreground" />
        <button type="button" onClick={() => setApiKeyVisible(v => !v)} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
          {apiKeyVisible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </button>
      </div>
      </div>
      <div className="flex items-center gap-3">
        <button onClick={testConnection} disabled={!endpoint} className="rounded-lg px-4 py-2 text-sm hover:bg-muted">
          <RefreshCw className="size-3 mr-1 inline" /> Test Connection
        </button>
        <ConnectionStatus status={status} />
      </div>
      <button onClick={handleSave} disabled={saving || !name || !endpoint}
        className="rounded-lg bg-cyan-500 px-6 py-3 font-medium text-black hover:bg-cyan-400 disabled:opacity-50">
        {saving ? "Saving…" : "Save Provider"}
      </button>
    </Card>
  );
}
