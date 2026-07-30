# AIC IDE — Architecture Invariants

Last updated: 2026-07-24

## INV-001: 15 Canonical Entities
Exactly 15 canonical AIC workers including Hermes. Defined in `src/renderer/src/lib/workforce.ts`. Matches aic-platform `backend/canonical_workforce.py`.

## INV-002: Greenfield Desktop Product
AIC IDE is NOT a web SPA wrapper. Built as Electron desktop app from scratch. Web SPA remains as separate fallback.

## INV-003: Core Independence
AIC Core/domain/runtime (aic-platform) is independent from desktop presentation. IDE calls platform via HTTP/WS API only.

## INV-004: Behavioral Parity
AIC behavioral semantics align with `/home/tvd/AI-Company/aic-skill`. FSM phases, worker roles, workflow semantics match. Implementation may differ architecturally.

## INV-005: Hermes as Dispatcher
Hermes is the System/Dispatcher coordinator. Discovery happens when user intent is insufficient. Tasks not created prematurely from vague requests.

## INV-006: Runtime Status Truth
Worker status derives from authoritative execution state (`/api/workers` + active leases). No decorative/static status.

## INV-007: Execution Traceability
Execution identity traceable: Project → Task → Worker Assignment → Execution Session → Terminal/Tools/Events → Files/Artifacts → Test/Verification → Result.

## INV-008: No Fabrication
Never fabricate: worker activity, terminal output, commands, tool execution, files, progress, tests, events, verification, handoffs, results.

## INV-009: FSM Authority
FSM/domain state is authoritative. UI must not invent independent workflow truth.

## INV-010: Cross-Platform First-Class
Windows, Linux, macOS are first-class targets. No hardcoded Linux-only assumptions in shared logic.

## INV-011: Terminal Separation
Worker Execution Terminal and User Interactive Terminal are separate concepts.

## INV-012: No Private Reasoning
Never expose private chain-of-thought or hidden model reasoning in UI.

## INV-013: Autonomous Company Environment
AIC IDE is an autonomous AI software company environment. Not a VS Code clone, Kanban, agent dashboard, or 15 independent chatbots.

## INV-014: Evidence Required
Visible success requires evidence. Build PASS alone ≠ completion. Tests PASS alone ≠ completion.
