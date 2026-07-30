# 31 — Architecture Decision Records (ADRs)

---

## ADR-001: Separation of Operating Core and Dispatcher Worker

- **Status:** Accepted  
- **Context:** Early designs confused Hermes with the entire runtime application.
- **Decision:** Explicitly separate `AIC Runtime` (the operating backend core) from `Hermes` (the Dispatcher Worker). Hermes coordinates engineering tasks but does not own database models or execute direct code changes.

---

## ADR-002: Elimination of Default Model in Favor of Smart Tier Fallback

- **Status:** Accepted  
- **Context:** Single "Default Model" assignments failed when rate limits or context windows were exceeded.
- **Decision:** Require explicit tier assignments (`Thinker`, `Crafter`, `Sprinter`) and implement automatic fallback routing (`Thinker` -> `Crafter` -> `Sprinter`).

---

## ADR-003: Local Update HTTP Distribution Server

- **Status:** Accepted  
- **Context:** Automated updates must function reliably across LAN environments without external cloud lock-in.
- **Decision:** Serve release binaries and `latest.json` over a local HTTP server (`http://192.168.2.10:8088`), verifying SHA256 checksums before initiating installation.

---

## ADR-004: Multi-Agent Parallel Execution & AST Code Intelligence Core

- **Status:** Accepted  
- **Context:** Roadmap milestones v1.2.x and v1.3.x require simultaneous subtask worker execution and static AST analysis for codebases.
- **Decision:** Implement `ParallelDispatcher` (`dispatcher/parallel.py`) to execute independent subtasks concurrently using `asyncio.gather`, and `ASTAnalyzer` (`backend/ast_analyzer.py`) for extracting classes, functions, args, and imports across Python and TypeScript/JavaScript source files.

---

## ADR-005: v1.6.x Stabilization & Recovery — Wire All Unreachable Modules

- **Status:** Accepted
- **Context:** By v1.5.x, multiple modules (`SelfHealingEngine`, `ParallelDispatcher`, `ASTAnalyzer`, `Execution DAG`) were implemented and unit-tested but never wired into the production FastAPI lifespan, REST routes, or desktop UI. Sleep-based parallel simulation masked the gap. The product claimed features it could not exercise end-to-end.
- **Decision:** In v1.6.x, perform a full integration recovery pass:
  1. Wire `run_startup_self_heal()` into the FastAPI lifespan (replacing inline SQL recovery blocks).
  2. Replace `asyncio.sleep(0.1)` parallel simulation with real `Dispatcher.issue_lease` calls and `plan_all_phases` on task dispatch.
  3. Expose `GET /api/console/execution-dag` for Live Company phase→worker graph rendering.
  4. Wire AST analysis into the desktop FileTree context menu via `GET /api/ast/analyze`.
  5. Document honest feature depth in the SoT roadmap (AST generate-tests = scaffold only; JS/TS parse = regex; policy engine = static scopes, not enterprise RBAC).
- **Consequence:** All modules previously verified only by unit tests are now exercised in production runtime paths. Sleep simulation is eliminated. Feature claims in SoT match verified source behavior.
