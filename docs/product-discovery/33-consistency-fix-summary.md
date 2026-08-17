# BACKEND WIRING SOT v2.1 — CONSISTENCY FIX SUMMARY

==================================================
DATE: 2026-07-29
VERSION: 2.1
==================================================

==================================================
CHANGES MADE
==================================================

3 fixes applied to 30-backend-wiring-sot.md

--------------------------------------------------
FIX 1: VerificationFailed Event Handling
--------------------------------------------------
Section: Event Model (Section 7)
Line: 344

Before:
| VerificationFailed | Verification Engine | Autonomy Engine | verification_id, failures |

After:
| VerificationFailed | Verification Engine | Runtime Executor | verification_id, failures |

Reason: Event Model now matches Failure Flow. Verification failure is handled by Runtime Executor (mark task as "verification_skipped"), not Autonomy Engine.

--------------------------------------------------
FIX 2: Terminology Inconsistency
--------------------------------------------------
Section: Sequence Diagrams (Section 11)
Line: 531

Before:
ChatService → MemoryStore: store(conversation, response) [async]

After:
ChatService → Memory Service: store(conversation, response) [async]

Reason: "MemoryStore" replaced with canonical name "Memory Service" to match all other sections.

--------------------------------------------------
FIX 3: Research Pipeline Inconsistency
--------------------------------------------------
Section: Decision Matrix (Section 6)
Line: 317

Before:
| Research | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |

After:
| Research | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |

Reason: Decision Matrix now shows Research uses Discovery → Planning (column 5 changed from ✗ to ✓). This matches Execution Pipeline where Discovery leads to Planning. Research does not use TaskGraph/Dispatcher (columns 6-7 remain ✗).

==================================================
SECTIONS MODIFIED
==================================================

1. Section 7 (Event Model) — Line 344: VerificationFailed subscriber changed
2. Section 11 (Sequence Diagrams) — Line 531: MemoryStore → Memory Service
3. Section 6 (Decision Matrix) — Line 317: Research Planning column changed

==================================================
SECTIONS NOT MODIFIED
==================================================

- Executive Summary
- Current State
- Architecture Principles
- Engine Responsibility Matrix
- Integration/Wiring Matrix
- Context Pipeline
- Execution Pipeline
- Dependency Rules
- Failure Flow
- State Machine
- Integration Contracts
- Testing Strategy
- Observability
- Open Questions
- Implementation Order
- Implementation Timeline
- Success Criteria

==================================================
CONFIRMATION
==================================================

✓ No architecture changed
✓ No implementation order changed
✓ No dependency graph changed
✓ No responsibilities changed
✓ No contracts changed
✓ No new engines added
✓ No new features added
✓ No scope expanded

Only 3 lines changed across 3 sections.

==================================================
END OF SUMMARY
==================================================
