# 41 — Product Principles

**Release Scope:** v2.0.2 → v2.1.0
**Status:** Source of Truth (Implementation Contract)

---

## Design Principles

### P1: One Shell, One Layout
Every screen exists inside the same shell: Title Bar → Activity Bar → Context Sidebar → Primary Workspace → Optional Inspector → Collapsible Bottom Panel. No page invents its own layout.

### P2: Context Over Navigation
Changing the active rail destination changes only the sidebar content and workspace content. The shell structure never changes. Users always know where they are because the shell is constant.

### P3: Actions Over Views
Every screen should tell the user what to do next, not just show data. Empty states educate. Error states guide. Success states reward.

### P4: Calm Density
Professional software presents much information while remaining calm. Use progressive disclosure to manage complexity. Show primary content immediately; hide advanced details behind tabs, drawers, or expandable sections.

### P5: Keyboard-First
Every action accessible by mouse must also be accessible by keyboard. Command palette is the universal escape hatch. Shortcuts follow platform conventions (Cmd on macOS, Ctrl on Linux/Windows).

### P6: Honest UI
Never show placeholder data. Never fake loading states. Never display "No problems detected" unless problems can actually be detected. Empty states must explain WHY they're empty.

## Engineering Principles

### E1: Evidence-Driven Development
Every claim about system behavior must be backed by runtime output, test results, or verifiable artifacts. Historical "COMPLETE" claims without evidence are treated as unverified.

### E2: Single Source of Truth
Version strings, product state, architecture decisions, and release status must be consistent across all files. No conflicting version numbers between `package.json`, `config.py`, `latest.json`, and documentation.

### E3: No Vendor Hardcoding
Runtime decisions (model selection, policy, fallback) derive from capability metadata, not model names or provider strings. The adaptive runtime system uses `capabilities_from_metadata()` — never `if provider == "openai"`.

### E4: Backward-Compatible Updates
The auto-update system must support upgrading from any prior v2.x version. Manifest schema must remain stable. SHA256 verification is mandatory for all downloaded artifacts.

### E5: Test What You Ship
Every feature that appears in release notes must have corresponding test evidence. Backend: pytest. Frontend: vitest. TypeScript: tsc --noEmit. Builds: npm run build.
