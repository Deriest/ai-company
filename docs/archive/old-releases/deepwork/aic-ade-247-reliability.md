# AIC-ADE 2.4.7 Reliability Work

## Goal

Ship a QA-ready 2.4.7 build that fixes the verified full-explore defects and
provides source, tests, commit, artefacts, matching manifest/checksums, and a
clear QA handoff.

## Confirmed Baseline

- `3e7f532` is the current release rebuild and only includes R1/R2.
- `tool_chat_service.py` locally imports `ModelTier` in a fallback branch,
  causing `UnboundLocalError` when a provider is already registered.
- `messages` is mapped by both `storage.models.Message` and
  `backend.models.conversation.Message`. The active QA database contains an
  error message with `created_at = NULL`; primary message response schemas
  require a datetime and return 400 for the conversation.
- The backend and storage session factories open separate SQLite engines. Only
  the storage engine configures WAL and a busy timeout.
- `latest.json` claims 2.4.6 but links 2.4.5 artefacts while carrying 2.4.6
  checksums, so update verification fails.

## Phases And Gates

1. Reliability core: repair ModelTier scope, canonical message persistence,
   nullable timestamp migration, and SQLite configuration. Oracle gate: data
   integrity and concurrent access risk.
2. API and state correctness: profile refresh, provider test contract, active
   project empty state, and worker metrics. Oracle gate: contract regressions.
3. Product surface: Operations navigation, shortcut hint, responsive worker
   detail, and targeted accessibility/copy polish. Oracle gate: discoverability
   and responsive interaction behavior.
4. Release evidence: run tests, build 2.4.7, derive manifest/checksums from
   artefacts, commit/push, and document QA reproduction evidence.

## Verification Evidence Required

- Provider-active tool chat does not raise `UnboundLocalError`.
- A legacy `messages.created_at IS NULL` record is repaired on migration and
  primary message endpoints serialize it successfully.
- New streaming failure messages have timestamps.
- Concurrent chat/project access no longer produces lock failures under a
  repeatable local stress check.
- UI/API contract regressions are covered by focused tests or source-level
  type/build checks.

## Progress

- Phase 1 implementation: ModelTier fallback import no longer shadows the
  module import. Primary chat/message routes now use `storage.models.Message`;
  the backend Message mapper was removed. A migration repairs NULL conversation
  and message timestamps. SQLite now has one session factory with WAL and a
  30-second busy timeout. The legacy Conversation mapper remains only because
  backend-owned folder/tag/attachment tables need its metadata foreign keys.
- Phase 1 validation found backend runtime tables also had cross-registry
  message foreign keys. These are now application-level string references, so
  backend metadata no longer requires a duplicate Message table mapping.
- Phase 2 implementation: provider test result is `modelCount` end-to-end;
  active project returns a normal `null` empty state; profile update is lifted
  to App state; Observability reads runtime worker metrics.
- Phase 3 implementation: an Operations submenu exposes the seven previously
  hidden screens; Ctrl+K is visible in the footer; worker details use a mobile
  drawer; targeted icon controls have accessible names; Skills renders DevOps.
- Final source validation: 13 focused backend tests pass using the bundled
  Python runtime. Frontend typecheck/build pass; Vitest has 92 passing tests.
  The focused legacy `test_ai_runtime` fallback assertion remains environment
  dependent when an external provider is configured, so it is excluded from
  the deterministic release gate.
