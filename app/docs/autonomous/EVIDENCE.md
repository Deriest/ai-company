# AIC IDE — Evidence Log

Last updated: 2026-07-24 (Cycle 22)

## Build: PASS (70+ modules, tsc+vite, 2.8s)
## Typecheck: PASS (zero errors)
## Tests: 47/47 PASS
## Smoke: SMOKE_OK

## Packaging (1.0.0) — ALL 3 PLATFORMS

| Platform | Artifact | Size | Format | Status |
|----------|----------|------|--------|--------|
| Linux | AIC IDE-1.0.0.AppImage | 114MB | AppImage | DISTRIBUTABLE |
| Linux | aic-ide_1.0.0_amd64.deb | 78MB | .deb | DISTRIBUTABLE (installs cleanly) |
| Windows | AIC IDE 1.0.0.exe | 76MB | Portable .exe | DISTRIBUTABLE (unsigned) |
| macOS | AIC IDE-1.0.0-mac.zip | 106MB | zip | DISTRIBUTABLE (unsigned) |

## Cross-Platform Build Verification
| Platform | Build | Runtime | Distributable |
|----------|-------|---------|---------------|
| Linux | PASS | VERIFIED (Xvfb :99, E2E, smoke) | YES (AppImage + .deb) |
| Windows | PASS | UNVERIFIED (needs Windows machine) | YES (.exe portable) |
| macOS | PASS | UNVERIFIED (needs macOS machine) | YES (.zip) |

## Notes
- DMG format requires macOS (dmg-license module is darwin-only) — zip used as macOS distributable
- NSIS installer requires wine on Linux — portable .exe built instead
- All builds unsigned (no code signing certificates)
- Linux .deb verified: installs via dpkg -i, launches, uninstalls cleanly
