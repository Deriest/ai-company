# ADR-001: Desktop Technology for AIC IDE

Status: ACCEPTED  
Date: 2026-07-23

## Context

AIC IDE needs a first-class desktop app for Windows, Linux, and macOS with:

- Native filesystem, dialogs, window lifecycle
- Terminal/PTY (user shell + future worker streams)
- Process management
- Secure bridge to local/remote AIC core
- Fast iteration with React-capable UI
- Packaging path for all three OSes

Build host has **Node 22**, **no Rust/cargo**.

## Options Considered

### A. Tauri 2

| Pros | Cons |
|------|------|
| Small binary, low RAM | Requires Rust toolchain |
| Strong security defaults | PTY/native plugins more work |
| System webview | Webview variance Win/Linux/macOS |
| Good packaging story | Install rustup + longer first build on this host |

### B. Electron (Chromium + Node main)

| Pros | Cons |
|------|------|
| Mature PTY ecosystem (`node-pty`) | Larger RAM/disk footprint |
| Full control of Chromium for IDE chrome | Heavier updates |
| Same stack as aic-platform frontend (React) | Security discipline required for bridge |
| Works immediately on this host | Must not become dumb localhost wrapper |
| electron-builder multi-OS packaging | |

### C. Native (Swift/C#/Qt) + remote UI

| Pros | Cons |
|------|------|
| True native | Three codebases or huge cost |
| | No reuse of React velocity |

## Decision

**Primary architecture: Electron + React + TypeScript.**

Reasons:

1. Evidence: no Rust on build host; mission requires shipping real app, not waiting on toolchain.
2. Terminal: `node-pty` is the mature cross-platform path for user terminals.
3. Velocity: team already runs React 19 / Vite for AIC; IDE UI is greenfield but stack knowledge transfers.
4. Packaging: electron-builder supports win/linux/mac targets from CI matrix.
5. Product rule still holds: **not a WebView of localhost:5173**. Renderer is a separate app; main process owns native capabilities; backend is a Runtime Client target, not "the app".

## Consequences

- Accept larger binary vs Tauri.
- Enforce contextIsolation, no nodeIntegration in renderer, typed IPC allowlist.
- Document migration path to Tauri if later RAM/binary constraints force it — only after feature parity.
- Cross-platform claims: Linux VERIFIED on this host; Windows/macOS BUILD-VERIFIED via CI when available, else UNTESTED.

## Non-goals of this ADR

- Multiple competing desktop stacks
- Wrapping existing SPA without redesign
