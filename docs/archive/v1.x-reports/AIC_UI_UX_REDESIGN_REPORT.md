# AIC ADE — UI/UX Redesign Report

**Date:** 2026-07-25  
**aic-ide HEAD:** `967016d`

## OLD → NEW (major surfaces)

| Surface | OLD | NEW | Status |
|---|---|---|---|
| Navigation rail | 18 admin icons | 6 destinations (Home, Hermes, Workspace, Live, Skills, Settings) | DONE |
| Permanent company column | Always-visible 15 workers | Only on Live view (`:has(.company)`) | DONE |
| Settings | Runtime Base URL / Username / Password | AI Providers BYOK + diagnostics | DONE |
| Model control | “Active Provider ▼” | `model-id · ProviderName` dropdown | DONE |
| Welcome | “AIC IDE” + Runtime Settings | “AIC ADE” + AI Providers, local-first copy | DONE |
| Home | Stats dashboard first | Hero CTAs → Hermes / Create / Open / Recent projects | DONE |
| Hermes Chat | Token gate “Sign in under Settings” | Direct chat surface | DONE |
| Native menu | Default/minimal | File/Edit/View/Window/Help with real actions | DONE |
| Provider form | Model free-text only | Model ID + Fetch Models + discovered list | DONE |

## Still iterative (not full visual system redesign of every panel)

- Project Workspace / CodeEditor visual polish
- Task detail unification of all lifecycle tabs
- Multi-resolution screenshot gallery automation
- Empty-state system across all secondary views

## Design principles applied

- Hermes-first workflow
- Progressive disclosure of workers
- PROVIDER ≠ MODEL
- Local engine invisible to users
- No fake activity

## Visual acceptance

Layout structural fixes applied. Headless multi-res screenshot campaign **partial / environment-limited**. Physical desktop visual pass recommended on Windows install.
