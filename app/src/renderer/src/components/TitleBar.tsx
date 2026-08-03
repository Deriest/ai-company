import { useEffect, useState } from "react"

export default function TitleBar() {
  const [maximized, setMaximized] = useState(false)

  useEffect(() => {
    const check = () => {
      // Poll for maximize state — Electron doesn't fire events for this in renderer without IPC
      setMaximized(document.body.classList.contains("window-maximized"))
    }
    // Try to get initial state via IPC
    ;(window as any).aic?.storeGet("window-maximized").then((v: any) => {
      if (v !== null) setMaximized(v)
    }).catch(() => {})

    // Listen for maximize/unmaximize events
    const handler = () => {
      setMaximized(prev => !prev)
    }
    window.addEventListener("resize", handler)
    return () => window.removeEventListener("resize", handler)
  }, [])

  const handleMinimize = () => (window as any).aic?.minimize()
  const handleMaximize = () => (window as any).aic?.maximize()
  const handleClose = () => (window as any).aic?.close()

  return (
    <div
      className="flex h-9 shrink-0 items-center justify-between bg-background px-3 select-none"
      style={{ WebkitAppRegion: "drag" } as any}
    >
      {/* Left: Logo + App Name */}
      <div className="flex items-center gap-2 text-[11px] font-semibold tracking-wide text-foreground/80">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="text-primary">
          <path d="M12 2L2 7L12 12L22 7L12 2Z" fill="currentColor" opacity="0.6"/>
          <path d="M2 17L12 22L22 17" stroke="currentColor" strokeWidth="1.5" fill="none" opacity="0.4"/>
          <path d="M2 12L12 17L22 12" stroke="currentColor" strokeWidth="1.5" fill="none" opacity="0.5"/>
          <circle cx="12" cy="12" r="3" fill="currentColor"/>
        </svg>
        <span>AICompany ADE</span>
      </div>

      {/* Right: Window Controls */}
      <div className="flex items-center" style={{ WebkitAppRegion: "no-drag" } as any}>
        <button
          onClick={handleMinimize}
          className="flex h-9 w-11 items-center justify-center text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          title="Minimize"
        >
          <svg width="10" height="1" viewBox="0 0 10 1" fill="currentColor">
            <rect width="10" height="1" />
          </svg>
        </button>
        <button
          onClick={handleMaximize}
          className="flex h-9 w-11 items-center justify-center text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          title={maximized ? "Restore" : "Maximize"}
        >
          {maximized ? (
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.2">
              <rect x="2.5" y="0.5" width="7" height="7" />
              <rect x="0.5" y="2.5" width="7" height="7" fill="var(--background)" />
            </svg>
          ) : (
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.2">
              <rect x="0.5" y="0.5" width="9" height="9" />
            </svg>
          )}
        </button>
        <button
          onClick={handleClose}
          className="flex h-9 w-11 items-center justify-center text-muted-foreground hover:bg-destructive hover:text-destructive-foreground transition-colors"
          title="Close"
        >
          <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor">
            <path d="M1 1L9 9M9 1L1 9" stroke="currentColor" strokeWidth="1.2" />
          </svg>
        </button>
      </div>
    </div>
  )
}