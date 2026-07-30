# 42 — Desktop Architecture

**Release Scope:** v2.0.2 → v2.1.0
**Status:** Source of Truth (Implementation Contract)

---

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│            AIC-ADE Desktop (Electron)                │
│  ┌───────────────────────────────────────────────┐  │
│  │         React 19 Renderer (Vite 6)            │  │
│  │  [ActivityBar] [Sidebar] [Workspace] [Panel]  │  │
│  └──────────────────┬────────────────────────────┘  │
│                     │ IPC / Preload                   │
│  ┌──────────────────▼────────────────────────────┐  │
│  │            Electron Main Process               │  │
│  │    Sidecar Manager │ Auto Updater │ Store      │  │
│  └──────────────────┬────────────────────────────┘  │
└─────────────────────┼───────────────────────────────┘
                      │ HTTP (127.0.0.1:8000)
┌─────────────────────▼───────────────────────────────┐
│            aic-platform (Python 3.12)                 │
│  ┌───────────────────────────────────────────────┐  │
│  │              FastAPI Backend                    │  │
│  │  /api/auth  /api/tasks  /api/conversations    │  │
│  │  /api/dashboard  /api/llm  /api/runtime       │  │
│  └──────────────────┬────────────────────────────┘  │
│                     │                                 │
│  ┌──────────────────▼────────────────────────────┐  │
│  │     Conversation Engine → Dispatcher           │  │
│  │     Provider Manager → Adaptive Runtime        │  │
│  │     Self-Healing Engine → Recovery             │  │
│  └──────────────────┬────────────────────────────┘  │
│                     │ SQLite (async)                  │
│  ┌──────────────────▼────────────────────────────┐  │
│  │            aic.db (storage/models.py)          │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

## Shell Layout (Mandatory)

Every screen in AIC-ADE uses this exact layout structure:

```
┌─────────────────────────────────────────────────────┐
│ Title Bar (draggable, status, model, palette)       │
├────┬──────┬─────────────────────────────────────────┤
│ AB │ Side │          Primary Workspace               │
│ 48 │ bar  │   ┌──────────────────────────────────┐   │
│ px │ ctx  │   │         Editor / Content          │   │
│    │      │   │                                    │   │
│    │      │   └──────────────────────────────────┘   │
│    │      ├─────────────────────────────────────────┤
│    │      │  Bottom Panel (collapsible)             │
├────┴──────┴─────────────────────────────────────────┤
│ Status Bar (optional, compact)                       │
└─────────────────────────────────────────────────────┘
```

### Component Hierarchy

| Component | Path | Purpose |
|---|---|---|
| `LayoutShell` | `components/LayoutShell.tsx` | Root shell — renders all structural regions |
| `App` | `App.tsx` | View router — determines which content fills shell |
| Activity Bar | Inline in `LayoutShell` | 48px left rail with icon navigation |
| Context Sidebar | `.ide-sidebar` slot | View-specific sidebar content |
| Primary Workspace | `.ide-editor-area` slot | Main content area |
| Bottom Panel | `.ide-panel` | Activity, Output, Problems, Terminal |
| Command Palette | `CommandPalette.tsx` | Modal overlay for command execution |

### Data Flow

```
User Action → React Hook (useBoot/useChat/useWorkspace)
    → runtimeClient.ts → HTTP → FastAPI Route
    → SQLAlchemy → SQLite → Response
    → Hook State Update → React Re-render
```

### Sidecar Lifecycle

1. Electron `main.ts` starts
2. `SidecarManager` launches `aic-platform` subprocess (uvicorn on port 8000)
3. Renderer polls `/api/health` until `"status": "ok"`
4. Boot sequence completes → main UI renders
5. On app quit: sidecar process is terminated

### Security Model

- Electron: `sandbox: true`, `contextIsolation: true`, `nodeIntegration: false`
- Preload: Minimal API surface (`window.aic.*`)
- Backend: JWT auth, bcrypt passwords, SQLite-only storage
- API keys: Stored in `LLMProviderConfig.api_key` (plaintext in local SQLite — acceptable for local-first desktop)
