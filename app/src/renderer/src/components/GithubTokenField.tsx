import { useState } from "react";
import { Eye, EyeOff, KeyRound, Trash2 } from "lucide-react";

/**
 * Optional GitHub token ("GHP") input — password field with an eye toggle.
 *
 * Semantics (owned by the parent):
 *  - type into the field         → parent sends `githubToken` on save
 *  - leave blank                 → field is NOT included in the PATCH (keeps stored)
 *  - "Remove stored"             → parent sends `` (empty string clears it)
 *
 * When a token is already stored and the field is empty it shows a masked
 * placeholder so the stored value is never overwritten by mistake.
 */
export function GithubTokenField({
  value,
  onChange,
  onClear,
  hasStored = false,
  disabled = false,
  id,
}: {
  value: string;
  onChange: (v: string) => void;
  onClear?: () => void;
  hasStored?: boolean;
  disabled?: boolean;
  id?: string;
}) {
  const [visible, setVisible] = useState(false);
  const showStoredPlaceholder = hasStored && !value;

  return (
    <div>
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={id} className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <KeyRound className="size-3.5" />
          GitHub token
          <span className="rounded bg-muted px-1 py-0.5 text-[9px] font-medium uppercase tracking-wide text-muted-foreground/70">optional</span>
        </label>
        {hasStored && onClear && (
          <button
            type="button"
            onClick={onClear}
            className="flex items-center gap-1 text-[11px] text-muted-foreground/60 transition-colors hover:text-destructive"
            title="Remove the stored GitHub token"
          >
            <Trash2 className="size-3" /> Remove stored
          </button>
        )}
      </div>
      <div className="relative mt-1">
        <input
          id={id}
          type={visible ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={showStoredPlaceholder ? "•••••••• stored token — type to replace" : "ghp_…"}
          autoComplete="off"
          spellCheck={false}
          disabled={disabled}
          className="w-full rounded-lg border border-border bg-background px-3 py-2 pr-9 font-mono text-sm text-foreground placeholder:text-muted-foreground/40 outline-none transition-colors focus:border-primary disabled:opacity-50"
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          tabIndex={-1}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground"
          aria-label={visible ? "Hide GitHub token" : "Show GitHub token"}
        >
          {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </button>
      </div>
      <p className="mt-1 text-[11px] text-muted-foreground/60">
        Used to install skills from private GitHub repositories. Stored encrypted on this device.
      </p>
    </div>
  );
}