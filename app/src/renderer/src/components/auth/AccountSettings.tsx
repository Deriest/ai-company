import { useEffect, useState } from "react";
import { Card } from "../kit";
import { profileApi, type LocalProfile } from "../../lib/api/profile";
import type { UpdateStateDto } from "../../types";
import { BugReportDialog, UpdatesDialog } from "./Dialogs";

export function GeneralTab({
  updateDialogOpen,
  onUpdateDialogOpenChange,
  onProfileUpdated,
}: {
  updateDialogOpen?: boolean
  onUpdateDialogOpenChange?: (open: boolean) => void
  onProfileUpdated?: (profile: LocalProfile) => void
} = {}) {
  const [profile, setProfile] = useState<LocalProfile | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [msg, setMsg] = useState("");
  const [saving, setSaving] = useState(false);
  const [bugOpen, setBugOpen] = useState(false);
  const updatesOpen = updateDialogOpen ?? false;
  const setUpdatesOpen = onUpdateDialogOpenChange ?? (() => {});

  // Real update state from Electron
  const [appVersion, setAppVersion] = useState("…");
  const [updateState, setUpdateState] = useState<UpdateStateDto | null>(null);

  useEffect(() => {
    profileApi.get().then((p) => {
      if (p) {
        setProfile(p);
        setDisplayName(p.displayName);
      }
    }).catch(() => {});

    // Read real app version from Electron
    window.aic?.getAppVersion?.().then((v: string) => {
      if (v) setAppVersion(v);
    }).catch(() => {});

    // Read current update state
    window.aic?.updateGetState?.().then((s) => {
      if (s) setUpdateState(s);
    }).catch(() => {});

    // Listen for update state changes
    const off = window.aic?.onUpdateStateChanged?.((s) => {
      setUpdateState(s);
    });
    return () => { off?.(); };
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setMsg("");
    try {
      const updated = await profileApi.update({ displayName });
      // FE-H2: PATCH returns a partial profile — merge over the full one so
      // deviceId/createdAt keep rendering instead of being wiped.
      setProfile(prev => (prev ? { ...prev, ...updated } : updated));
      onProfileUpdated?.(updated);
      setMsg("Saved");
    } catch {
      setMsg("Failed to save");
    }
    setSaving(false);
  };

  const handleCheckUpdates = () => {
    setUpdatesOpen(true);
    window.aic?.updateCheck?.();
  };

  const handleDownload = () => { window.aic?.updateDownload?.(); };
  const handleInstall = () => { window.aic?.updateQuitAndInstall?.(); };
  const handleDismiss = () => {
    setUpdatesOpen(false);
    window.aic?.updateDismiss?.();
  };

  // Update status label
  const updateStatus = updateState?.status || "unknown";
  const updateLabel: Record<string, string> = {
    idle: "Up to date",
    checking: "Checking…",
    available: "Update available",
    downloading: "Downloading…",
    ready_to_install: "Ready to install",
    error: "Update error",
    unknown: "—",
  };

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Profile */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Profile</h3>
        <div className="space-y-4">
          <div>
            <label className="text-sm text-muted-foreground">Display Name</label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-foreground outline-none focus:border-primary"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-muted-foreground">Device ID</label>
              <div className="mt-1 text-sm font-mono text-muted-foreground">
                {profile?.deviceId || "—"}
              </div>
            </div>
            <div>
              <label className="text-sm text-muted-foreground">Created</label>
              <div className="mt-1 text-sm text-muted-foreground">
                {profile?.createdAt ? new Date(profile.createdAt).toLocaleDateString() : "—"}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={saving}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save"}
            </button>
            {msg && <span className="text-sm text-muted-foreground">{msg}</span>}
          </div>
        </div>
      </Card>

      {/* App Info + Update */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">About</h3>
          <span className="font-mono text-sm text-muted-foreground">v{appVersion}</span>
        </div>
        <div className="space-y-3 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Platform</span>
            <span>Desktop (Electron + React + FastAPI)</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Database</span>
            <span>SQLite (local)</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Update Status</span>
            <span className={
              updateStatus === "idle" ? "text-success" :
              updateStatus === "available" || updateStatus === "ready_to_install" ? "text-primary" :
              updateStatus === "error" ? "text-destructive" :
              "text-muted-foreground"
            }>
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
            <button
              onClick={handleCheckUpdates}
              className="rounded-lg bg-primary/15 px-4 py-2 text-sm font-medium text-primary hover:bg-primary/25"
            >
              Check for Updates
            </button>
            <button
              onClick={() => setBugOpen(true)}
              className="rounded-lg border border-border px-4 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-muted"
            >
              Report a Bug
            </button>
          </div>
        </div>
      </Card>

      <BugReportDialog open={bugOpen} onClose={() => setBugOpen(false)} />
      <UpdatesDialog
        open={updatesOpen}
        onClose={() => setUpdatesOpen(false)}
        updateState={updateState}
        onCheck={() => window.aic?.updateCheck?.()}
        onDownload={handleDownload}
        onInstall={handleInstall}
        onDismiss={handleDismiss}
      />
    </div>
  );
}
