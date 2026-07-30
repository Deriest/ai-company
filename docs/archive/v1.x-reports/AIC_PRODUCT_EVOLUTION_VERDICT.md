# AIC ADE — Product Evolution Verdict

**Date:** 2026-07-25  
**Heads:** platform `c155486` · ide `659bb97`

## Verdict

**BLOCKED BY EXTERNAL VERIFICATION**

Engineering work for a professional native ADE has advanced substantially. Remaining mandatory gate is physical Windows install/run on a clean machine (no Python/Node/Git). Setup.exe rebuild from latest win-unpacked may still be compressing at report time — Portable + Linux packages already rebuilt with latest UI.

## What changed this evolution session

### Native desktop experience
- Splash: starting → restoring → ready (error recovery)
- Session restore: lastView, projectRoot, openTabs, conversationId
- Silent local session (no login form, no Base URL form)
- Native menu + shortcuts: Cmd/Ctrl+K palette, L Hermes, S save, B dock

### Hermes conversation-first
- Propose `pending_task` when requirements enough
- Create task only on confirm (“yes/go ahead”) or force (“build now/create the task”)
- Hermes-branded system prompt for ADE partner behavior

### Workspace
- Project environment detection (Node/Python/Rust/Go/…)
- Files panel: env card + open project shell
- Empty states for workspace + Hermes

### Lifecycle / packaging
- Bundled python-win / python-linux still required path
- Linux AppImage + deb rebuilt
- Windows Portable rebuilt
- SkillsManager uses authenticated runtime client

## Quality evidence
- aic-platform: **114** pytest
- aic-ide: **75** vitest
- typecheck: clean
- production build: OK

## Not claimed complete
- Physical Windows runtime on clean PC
- Full VS Code–parity Git/search/debug
- Auto-executing project bootstrap (hints only)
- Multi-res visual screenshot campaign in headless env

## External verification required
1. Download Setup.exe or Portable from download.aicompany.biz.id
2. Install on clean Windows 10/11 without Python
3. Confirm Engine Ready without terminal
4. Add provider → model · provider label
5. Talk to Hermes → confirm-before-task behavior
6. Open project → env detected
7. No orphaned python after quit

See: `WINDOWS_ACCEPTANCE_TEST.md`
