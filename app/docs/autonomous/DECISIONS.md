# AIC IDE — Architecture Decisions

Last updated: 2026-07-24

## DEC-001: Electron + React 19
- Context: Need cross-platform desktop app
- Alternatives: Tauri, native Qt, CEF
- Reason: Mature ecosystem, React for UI, electron-builder for packaging
- Tradeoffs: Larger binary than Tauri, but proven reliability

## DEC-002: Vite 6 + Vitest 3
- Context: Build + test tooling
- Alternatives: Webpack, Jest, Rollup
- Reason: Fast HMR, native ESM, integrated test runner
- Tradeoffs: Newer than Webpack, but sufficient

## DEC-003: No Monaco (Yet)
- Context: Code editor choice
- Alternatives: Monaco, CodeMirror 6, Ace
- Reason: Monaco bundle is large; current textarea sufficient for deliverable review
- Tradeoffs: No syntax highlighting yet
- Superseding: BL-002 proposes CodeMirror 6 for better DX without Monaco's weight

## DEC-004: Pipe Terminal (Not PTY)
- Context: User terminal implementation
- Alternatives: node-pty, ConPTY (Windows)
- Reason: node-pty requires native compilation; pipe is simpler for basic shell
- Tradeoffs: No colors, no interactive TTY programs (vim, top)
- Superseding: BL-010 evaluates proper PTY

## DEC-005: Path Allowlist Security
- Context: File access security
- Alternatives: Full filesystem access, chroot
- Reason: Prevent path traversal; allow project root + userData only
- Tradeoffs: Slightly restrictive; safe default

## DEC-006: Keep Web SPA Fallback
- Context: Web vs desktop strategy
- Decision: Web SPA at aic-platform/frontend remains as fallback
- Reason: Desktop not yet proven to fully supersede web capabilities
- Tradeoffs: Dual maintenance until retirement audit

## DEC-007: Git Init at Cycle 1
- Context: No git repo existed
- Decision: Initialize git with baseline commit of ALPHA state
- Reason: Mission continuity, recoverability, change tracking
