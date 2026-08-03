# AIC ADE v1.6.0 — Release Notes

**Product:** AIC-ADE  
**Version:** 1.6.0  
**Channel:** stable  
**Theme:** Stabilization & Recovery  

---

## Highlights

### Integration recovery
- **Self-healing** wired into FastAPI lifespan (`run_startup_self_heal`) and `POST /api/console/self-heal`.
- **Parallel worker planning** via `plan_all_phases` on task dispatch; real lease issuance via `POST /api/tasks/{id}/parallel-leases` (no sleep simulation).
- **Execution DAG** API `GET /api/console/execution-dag` + Live Company summary.
- **AST analyze** API with path validation; File Tree **Analyze AST** context action.

### Desktop quality
- **App.tsx** decomposed into hooks (`useBoot`, `useChat`, `useWorkspace`) and views (Chat, Sidebar, Layout, Files, Projects); shell ~296 LOC.
- TypeScript clean; Vitest 92; Platform pytest 123.

### Repository hygiene
- Legacy web `frontend/` removed from platform tree.
- Historical redesign reports archived under `docs/archive/`.
- SoT roadmap/product state/ADR-005 aligned to v1.6.x.

### Identity
- Platform `settings.VERSION` = **1.6.0**
- Desktop `package.json` / NSIS = **1.6.0**
- Update manifest `latest.json` = **1.6.0**

---

## Honest limits (not v1.6 product depth)

- JS/TS AST uses regex extraction (not full compiler AST); no Rust.
- Test generation is scaffold text, not auto-run on patch.
- Parallel leases are sequential per SQLite session; full concurrent multi-agent product is future work.
- Local policy engine is not enterprise remote RBAC/audit shipper.

---

## Validation gates (release closeout)

- pytest (platform): 123 passed  
- vitest (desktop): 92 passed  
- tsc: clean  
- health endpoint version: 1.6.0  

---

## Artifacts

See `SHA256SUMS.txt` and `latest.json` in the release distribution directory.
