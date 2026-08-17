# AIC IDE — Platform Matrix

Last updated: 2026-07-24 (Cycle 12)

| Capability | Windows | Linux | macOS |
|------------|---------|-------|-------|
| Desktop Build | CI VERIFIED | BUILD VERIFIED | CI VERIFIED |
| Unit Tests | CI VERIFIED | CI VERIFIED | CI VERIFIED |
| Integration Tests | UNTESTED | RUNTIME VERIFIED (21/21) | UNTESTED |
| Runtime Startup | UNVERIFIED | RUNTIME VERIFIED | UNVERIFIED |
| AIC Core Connection | UNVERIFIED | RUNTIME VERIFIED | UNVERIFIED |
| Chat | UNVERIFIED | E2E VERIFIED | UNVERIFIED |
| Projects | UNVERIFIED | E2E VERIFIED | UNVERIFIED |
| Files | UNVERIFIED | BUILD VERIFIED | UNVERIFIED |
| Editor | UNVERIFIED | BUILD VERIFIED | UNVERIFIED |
| User Terminal | UNVERIFIED | BUILD VERIFIED (PTY) | UNVERIFIED |
| Live Execution | UNVERIFIED | RUNTIME VERIFIED | UNVERIFIED |
| Workers | UNVERIFIED | RUNTIME VERIFIED | UNVERIFIED |
| Board | UNVERIFIED | BUILD VERIFIED | UNVERIFIED |
| Activity | UNVERIFIED | RUNTIME VERIFIED | UNVERIFIED |
| Approvals | UNVERIFIED | RUNTIME VERIFIED | UNVERIFIED |
| Verification | UNVERIFIED | BUILD VERIFIED | UNVERIFIED |
| Delivery | UNVERIFIED | RUNTIME VERIFIED (ZIP) | UNVERIFIED |
| Packaging | CI VERIFIED | BUILD VERIFIED (AppImage + .deb) | CI VERIFIED |
| Golden Path | UNTESTED | E2E VERIFIED | UNTESTED |

Notes:
- Linux: full verification chain (build + typecheck + tests + smoke + E2E + packaging)
- .deb now generated (was previously broken)
- Windows/macOS: CI pipeline exists but no runtime evidence (needs physical machines)
