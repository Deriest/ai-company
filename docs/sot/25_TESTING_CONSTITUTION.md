# 25 — Testing Constitution

**Mandatory Rule:** NO RELEASE MAY BE CREATED UNLESS ALL TESTS PASS.  

---

## 1. Test Suite Standards

- **Backend Test Suite (Pytest):** Must pass 100% of unit & integration tests (`cd aic-platform && .venv/bin/python -m pytest tests/`).
- **Desktop UI Test Suite (Vitest):** Must pass 100% of component & store tests (`cd aic-ide && npx vitest run`).
- **TypeScript Typecheck:** Zero errors allowed (`npx tsc -p tsconfig.json --noEmit` and `npx tsc -p tsconfig.electron.json --noEmit`).

---

## 2. Quality Gates

```
[ Code Change ] ──► [ Typecheck ] ──► [ Vitest ] ──► [ Pytest ] ──► [ Build Binary ] ──► [ SHA256 Checksum ]
```
