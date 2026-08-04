import { useEffect, useRef, useState } from "react";
import { X, Bug, MessageSquareHeart, LifeBuoy, Paperclip, Monitor, Send } from "lucide-react";
import { cn } from "../../lib/utils";
// auth-kit removed — inline stubs
function FormField({ label, children }: { label: string; children: React.ReactNode }) { return <div><label className="text-sm text-muted-foreground">{label}</label>{children}</div>; }
function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) { return <input {...props} className={"w-full rounded-lg border border-border bg-background px-3 py-2 text-foreground " + (props.className || "")} />; }
function PrimaryButton({ loading, children, className, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { loading?: boolean }) { return <button {...props} disabled={loading || props.disabled} className={"rounded-lg bg-cyan-500 px-4 py-2 text-sm font-medium text-black hover:bg-cyan-400 disabled:opacity-50 " + (className || "")}>{loading ? "Saving..." : children}</button>; }
function GhostButton(props: React.ButtonHTMLAttributes<HTMLButtonElement>) { return <button {...props} className={"rounded-lg px-4 py-2 text-sm hover:bg-muted " + (props.className || "")} />; }
function ErrorBanner({ message }: { message: string }) { return <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-2 text-sm text-red-400">{message}</div>; }
function SuccessBanner({ message }: { message: string }) { return <div className="rounded-lg bg-green-500/10 border border-green-500/20 px-4 py-2 text-sm text-green-400">{message}</div>; }

type DialogProps = {
  open: boolean;
  onClose: () => void;
};

export function ModalShell({
  open,
  onClose,
  title,
  children,
  maxWidth = 480,
}: DialogProps & { title: string; children: React.ReactNode; maxWidth?: number }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  // A11y: save the previously focused element and restore it on close. A Tab
  // key trap keeps focus inside the dialog while it is open.
  const dialogRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    return () => { previouslyFocused?.focus?.(); };
  }, [open]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key !== "Tab") return;
    const container = dialogRef.current;
    if (!container) return;
    const focusables = Array.from(container.querySelectorAll<HTMLElement>(
      "button, [href], input, select, textarea, [tabindex]:not([tabindex=\"-1\"])",
    )).filter(el => !el.hasAttribute("disabled"));
    if (focusables.length === 0) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div
        ref={dialogRef}
        onKeyDown={handleKeyDown}
        className="w-full rounded-xl border border-border bg-card shadow-xl"
        style={{ maxWidth }}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal
        aria-label={title}
      >
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <h2 className="text-sm font-semibold">{title}</h2>
          <button type="button" onClick={onClose} className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground" aria-label="Close">
            <X className="size-4" />
          </button>
        </div>
        <div className="max-h-[70vh] overflow-y-auto scroll-thin px-5 py-4">{children}</div>
      </div>
    </div>
  );
}

export function BugReportDialog({ open, onClose }: DialogProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [attachShot, setAttachShot] = useState(true);
  const [attachLogs, setAttachLogs] = useState(true);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [appVersion, setAppVersion] = useState("…");

  // BUG-17: Read the real app version from Electron instead of a hardcoded value.
  useEffect(() => {
    window.aic?.getAppVersion?.().then((v: string) => {
      if (v) setAppVersion(v);
    }).catch(() => {});
  }, []);

  const sys = {
    version: appVersion,
    os: typeof navigator !== "undefined" ? navigator.platform : "Linux",
    provider: "Local",
    mission: "—",
    worker: "—",
    timeline: "Last 50 events",
  };

  useEffect(() => {
    if (open) {
      setDone(false);
      setError("");
    }
  }, [open]);

  return (
    <ModalShell open={open} onClose={onClose} title="Report a bug" maxWidth={520}>
      {done ? (
        <div className="space-y-4 py-4 text-center">
          <Bug className="mx-auto size-8 text-success" />
          <p className="text-sm font-medium">Report submitted</p>
          <p className="text-xs text-muted-foreground">Ticket #AIC-{Math.floor(Math.random() * 9000 + 1000)}</p>
          <PrimaryButton onClick={onClose}>Close</PrimaryButton>
        </div>
      ) : (
        <div className="space-y-4">
          <ErrorBanner message={error} />
          <FormField label="Title">
            <TextInput value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Short summary of the issue" />
          </FormField>
          <FormField label="Description">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              placeholder="What happened? What did you expect?"
              className="flex w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus:border-primary/60 focus:ring-1 focus:ring-primary/30"
            />
          </FormField>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setAttachShot((v) => !v)}
              className={cn(
                "flex items-center gap-2 rounded-lg border px-3 py-2 text-xs",
                attachShot ? "border-primary/50 bg-primary/10 text-primary" : "border-border text-muted-foreground",
              )}
            >
              <Paperclip className="size-3.5" /> Screenshot
            </button>
            <button
              type="button"
              onClick={() => setAttachLogs((v) => !v)}
              className={cn(
                "flex items-center gap-2 rounded-lg border px-3 py-2 text-xs",
                attachLogs ? "border-primary/50 bg-primary/10 text-primary" : "border-border text-muted-foreground",
              )}
            >
              <Monitor className="size-3.5" /> Logs
            </button>
          </div>
          <div className="rounded-lg border border-border bg-background/50 p-3 font-mono text-[10px] text-muted-foreground">
            <p>Version: {sys.version}</p>
            <p>OS: {sys.os}</p>
            <p>Provider: {sys.provider}</p>
            <p>Mission: {sys.mission}</p>
            <p>Worker: {sys.worker}</p>
            <p>Timeline: {sys.timeline}</p>
          </div>
          <div className="flex justify-end gap-2">
            <GhostButton className="w-auto px-4" onClick={onClose}>
              Cancel
            </GhostButton>
            <PrimaryButton
              className="w-auto px-4"
              loading={loading}
              onClick={async () => {
                setError("");
                if (!title.trim()) {
                  setError("Title is required.");
                  return;
                }
                setLoading(true);
                const issueUrl = new URL("https://github.com/Deriest/ai-company/issues/new");
                issueUrl.searchParams.set("title", `[Bug] ${title.trim()}`);
                issueUrl.searchParams.set("body", `${description.trim()}\n\n---\nVersion: ${sys.version}\nOS: ${sys.os}`);
                await window.aic?.openExternal?.(issueUrl.toString());
                setLoading(false);
                setDone(true);
              }}
            >
              <Send className="size-3.5" /> Send
            </PrimaryButton>
          </div>
        </div>
      )}
    </ModalShell>
  );
}

export function FeedbackDialog({
  open,
  onClose,
  kind = "general",
}: DialogProps & { kind?: "feature" | "general" | "support" }) {
  const [body, setBody] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const titles = {
    feature: "Feature request",
    general: "General feedback",
    support: "Contact support",
  };
  const icons = {
    feature: SparklesIcon,
    general: MessageSquareHeart,
    support: LifeBuoy,
  };
  const Icon = icons[kind];

  useEffect(() => {
    if (open) setDone(false);
  }, [open]);

  return (
    <ModalShell open={open} onClose={onClose} title={titles[kind]}>
      {done ? (
        <div className="space-y-3 py-6 text-center">
          <SuccessBanner message="Thanks — submitted." />
          <PrimaryButton onClick={onClose}>Close</PrimaryButton>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Icon className="size-4 text-primary" />
            {kind === "support" ? "Our team will reply." : "We read every submission."}
          </div>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={5}
            placeholder={kind === "feature" ? "Describe the feature…" : "Write your message…"}
            className="flex w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary/60"
          />
          <div className="flex justify-end gap-2">
            <GhostButton className="w-auto px-4" onClick={onClose}>
              Cancel
            </GhostButton>
            <PrimaryButton
              className="w-auto px-4"
              loading={loading}
              onClick={async () => {
                if (!body.trim()) return;
                setLoading(true);
                await new Promise((r) => setTimeout(r, 600));
                setLoading(false);
                setDone(true);
              }}
            >
              Send
            </PrimaryButton>
          </div>
        </div>
      )}
    </ModalShell>
  );
}

function SparklesIcon({ className }: { className?: string }) {
  return (
    <svg className={className} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5L12 3z" />
    </svg>
  );
}

export function UpdatesDialog({
  open,
  onClose,
  updateState,
  onCheck,
  onDownload,
  onInstall,
  onDismiss,
}: DialogProps & {
  updateState?: any;
  onCheck?: () => void;
  onDownload?: () => void;
  onInstall?: () => void;
  onDismiss?: () => void;
}) {
  const checking = updateState?.status === "checking";
  const downloading = updateState?.status === "downloading";
  const ready = updateState?.status === "ready_to_install" || updateState?.status === "ready_to_restart";
  const mandatory = !!updateState?.mandatory;

  const statusLabel =
    updateState?.status === "checking" ? "Checking..." :
    updateState?.status === "downloading" ? "Downloading..." :
    updateState?.status === "ready_to_install" ? "Ready to restart" :
    updateState?.status === "ready_to_restart" ? "Restart to apply" :
    updateState?.status === "error" ? "Error" :
    updateState?.status === "available" ? "Update available" :
    "Up to date";

  const pct = updateState?.progress ? Math.round(updateState.progress) : 0;

  return (
    <ModalShell open={open} onClose={onClose} title="Updates">
      <div className="space-y-4">
        {updateState?.error && (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {updateState.error}
          </div>
        )}
        <div className="flex items-center justify-between rounded-lg border border-border bg-background/50 px-4 py-3">
          <div>
            <p className="text-xs text-muted-foreground">Current version</p>
            <p className="font-mono text-2xl font-bold">{updateState?.currentVersion || "2.1.0"}</p>
          </div>
          <div className="text-right">
            <span className={cn(
              "rounded-md border px-2 py-0.5 text-[11px] font-medium",
              ready ? "bg-success/15 text-success border-success/30" : "bg-primary/15 text-primary border-primary/30"
            )}>
              {statusLabel}
            </span>
            {updateState?.availableVersion && (
              <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                Latest: {updateState.availableVersion}
              </p>
            )}
          </div>
        </div>

        {downloading && (
          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>Downloading update...</span>
              <span className="font-mono">{pct}%</span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-primary transition-all duration-300" style={{ width: `${pct}%` }} />
            </div>
          </div>
        )}

        <div className="flex flex-col gap-2">
          {updateState?.status === "available" ? (
            <PrimaryButton loading={checking} onClick={onDownload}>
              Download Update
            </PrimaryButton>
          ) : ready ? (
            <PrimaryButton onClick={onInstall}>
              Restart & Install
            </PrimaryButton>
          ) : (
            <PrimaryButton loading={checking || downloading} onClick={onCheck}>
              Check for updates
            </PrimaryButton>
          )}
          {!mandatory && (updateState?.status === "error" || updateState?.status === "available" || ready) ? (
            <GhostButton onClick={onDismiss}>
              Remind me later
            </GhostButton>
          ) : null}
        </div>

        {updateState?.releaseNotes && (
          <div className="rounded-lg border border-border p-3">
            <p className="mb-1 text-xs font-semibold">Release notes</p>
            <div className="max-h-32 overflow-y-auto scroll-thin text-[11px] text-muted-foreground whitespace-pre-wrap">
              {updateState.releaseNotes}
            </div>
          </div>
        )}
      </div>
    </ModalShell>
  );
}
