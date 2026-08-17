# AIC IDE — Known Issues

Last updated: 2026-07-24 (Cycle 22)

## External Blockers (non-engineering, documented with resolution paths)

| ID | Issue | Impact | Resolution Path |
|----|-------|--------|-----------------|
| KI-EXT-01 | Windows runtime UNVERIFIED | Cannot confirm Windows desktop works at runtime | Obtain Windows machine (physical or VM), run `AIC IDE 1.0.0.exe`, verify all views. Binary is distributable. |
| KI-EXT-02 | macOS runtime UNVERIFIED | Cannot confirm macOS desktop works at runtime | Obtain macOS machine, unzip `AIC IDE-1.0.0-mac.zip`, launch .app, verify all views. |
| KI-EXT-03 | GitHub remote not pushed | CI cannot execute | Obtain GitHub PAT for Deriest/aic-ide repo, push, verify CI. |
| KI-EXT-04 | DMG format unavailable | DMG requires macOS to build | Use .zip as macOS distributable. DMG can be built on macOS machine if desired. |
| KI-EXT-05 | Unsigned binaries | Windows/macOS may warn users | Obtain code signing certificates for production distribution. |

## P3 — Polish
| ID | Issue | Status |
|----|-------|--------|
| KI-P3-02 | No auto-update mechanism | Post-1.0.0 |
