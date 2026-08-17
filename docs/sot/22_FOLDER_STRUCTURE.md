# 22 — Folder Structure Guidelines

**Policy:** Folder Single Responsibility Principle  

---

## 1. Strict Isolation Rules

- **`aic-platform/`:** Strictly Python backend code. No frontend assets or Electron scripts.
- **`aic-ide/`:** Strictly Desktop application source. Uses `runtimeClient.ts` to talk to backend.
- **`aic-skill/`:** Strictly SKILL.md files and supporting assets/templates. No binary code.
- **`releases/`:** Strictly public distribution binaries (`.AppImage`, `.deb`, `.exe`, `latest.json`).
