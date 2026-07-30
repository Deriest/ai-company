/** Native-feeling splash with meaningful engine lifecycle. */

export type EnginePhase =
  | "launching"
  | "loading_workspace"
  | "restoring_session"
  | "loading_skills"
  | "ready"
  | "error";

type Props = {
  phase: EnginePhase | "starting" | "restoring";
  detail?: string;
};

const LABELS: Record<string, string> = {
  launching: "Launching engine",
  starting: "Launching engine",
  loading_workspace: "Loading workspace",
  restoring_session: "Restoring session",
  restoring: "Restoring session",
  loading_skills: "Loading skills",
  ready: "Ready",
  error: "Engine error",
};

const ORDER = ["launching", "loading_workspace", "restoring_session", "loading_skills", "ready"] as const;

export function Splash({ phase, detail }: Props) {
  const normalized =
    phase === "starting" ? "launching" : phase === "restoring" ? "restoring_session" : phase;
  const label = LABELS[normalized] || "Working…";
  const stepIdx = Math.max(
    0,
    ORDER.indexOf(normalized as (typeof ORDER)[number])
  );

  return (
    <div
      className="splash"
      role="status"
      aria-live="polite"
      aria-busy={normalized !== "ready" && normalized !== "error"}
    >
      <div className="splash-card">
        <div className="splash-mark" aria-hidden>
          ◈
        </div>
        <h1 className="splash-title">AIC ADE</h1>
        <p className="splash-sub">Agentic Development Environment</p>

        {normalized !== "error" && (
          <ol className="splash-steps" aria-label="Startup progress">
            {ORDER.slice(0, -1).map((key, i) => {
              const done = i < stepIdx;
              const active = i === stepIdx;
              return (
                <li key={key} className={done ? "done" : active ? "active" : ""}>
                  <span className="splash-step-dot" />
                  <span>{LABELS[key]}</span>
                </li>
              );
            })}
          </ol>
        )}

        <div className="splash-bar" aria-hidden>
          <div className={`splash-bar-fill ${normalized}`} />
        </div>
        <p className="splash-phase">{label}</p>
        {detail ? <p className="splash-detail">{detail}</p> : null}
      </div>
    </div>
  );
}
