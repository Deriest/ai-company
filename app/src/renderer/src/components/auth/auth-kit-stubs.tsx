/** Stubs replacing removed auth-kit components */
import React from "react";

export function FormField({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <div>
      <label className="text-sm text-muted-foreground">{label}</label>
      {children}
      {hint && <p className="text-xs text-muted-foreground mt-1">{hint}</p>}
    </div>
  );
}

export function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={"w-full rounded-lg border border-border bg-background px-3 py-2 text-foreground " + (props.className || "")} />;
}

export function PasswordField({ label, ...props }: React.InputHTMLAttributes<HTMLInputElement> & { label?: string }) {
  return (
    <div>
      {label && <label className="text-sm text-muted-foreground">{label}</label>}
      <input type="password" {...props} className={"w-full rounded-lg border border-border bg-background px-3 py-2 text-foreground " + (props.className || "")} />
    </div>
  );
}

export function PrimaryButton({ loading, children, className, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { loading?: boolean }) {
  return (
    <button {...props} disabled={loading || props.disabled} className={"rounded-lg bg-cyan-500 px-4 py-2 text-sm font-medium text-black hover:bg-cyan-400 disabled:opacity-50 " + (className || "")}>
      {loading ? "Saving…" : children}
    </button>
  );
}

export function GhostButton(props: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button {...props} className={"rounded-lg px-4 py-2 text-sm hover:bg-muted " + (props.className || "")} />;
}

export function SelectField({ label, value, onChange, options }: { label: string; value: string; onChange: (e: React.ChangeEvent<HTMLSelectElement>) => void; options: { value: string; label: string }[] }) {
  return (
    <div>
      <label className="text-sm text-muted-foreground">{label}</label>
      <select value={value} onChange={onChange} className="w-full rounded-lg border border-border bg-background px-3 py-2 text-foreground">
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-2 text-sm text-red-400">{message}</div>;
}

export function SuccessBanner({ message }: { message: string }) {
  return <div className="rounded-lg bg-green-500/10 border border-green-500/20 px-4 py-2 text-sm text-green-400">{message}</div>;
}

export function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div>
      <h3 className="text-lg font-semibold">{title}</h3>
      {subtitle && <p className="text-sm text-muted-foreground">{subtitle}</p>}
    </div>
  );
}
