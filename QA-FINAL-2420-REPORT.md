# AIC-ADE 2.4.20 — FINAL QA REPORT (READY TO USE)

Tanggal: 2026-08-01 | Build: AIC-ADE-2.4.20-linux-x86_64.AppImage (182.6MB)
Metode: QA loop 9 round (2.4.11 → 2.4.20), fresh profile tiap build, CDP + curl + DB + pytest
**Score: 97/100 — READY TO USE** (target 95 ✅)

---

## PERJALANAN LOOP (9 round fix, semua lewat opencode — QA murni di sisi sini)

| Round | Build | Fix |
|---|---|---|
| R1 | 2.4.12 | BUG-01 updates display, BUG-02 delivery/stats, BUG-05 unpack crash, BUG-06 qa python, BUG-08 default project, Kelompok 3 worker selection |
| R2 | 2.4.13 | BUG-07 pipeline launch dari chat (CRITICAL), BUG-11 chat persist, BUG-03, BUG-09/10, BUG-04, BUG-12 security spawn |
| R3 | 2.4.14 | BUG-03 mount workers_router, BUG-13 workers:15, BUG-14 model fallback, BUG-04 palette |
| R4 | 2.4.15 | BUG-15 provider live-register + FITUR 1 MCP Memory + FITUR 2 Taste (3 lapis) |
| R5 | 2.4.16 | BUG-16 fallback combo filter (CRITICAL — 404 semua worker) |
| R6 | 2.4.17 | BUG-17 MCP tools di AgentRunner |
| R7 | 2.4.18 | BUG-19 SSE tool_calls DROPPED (CRITICAL — semua tool mati, regression provider.py), BUG-18 version drift |
| R8 | 2.4.19 | BUG-20 taste wordlist greeting AI-ism + rewrite event + frontend onRewrite |
| R9 | 2.4.20 | Test suite 23 failed → 636 ALL PASS (schema drift + memory/automation/rag) + port manager |

## VERIFIED FINAL (2.4.20 — fresh profile, runtime)
- ✅ Version 2.4.20 di /health + latest.json lengkap (sha256 match)
- ✅ Provider save via UI → llm_configured TRUE tanpa restart (BUG-15)
- ✅ Fallback model valid (combo/* ter-filter, BUG-16)
- ✅ Chat "halo" → stream slop → REWRITE EVENT → "What do you need?" (anti-slop EFEKTIF)
- ✅ Tool calling HIDUP: builtin list_directory eksekusi + hasil asli (BUG-19 fixed)
- ✅ MCP Memory e2e: register (9 tools) → create_entities dipanggil (10x) → memory.json terisi → search_nodes jalan
- ✅ Pipeline dari chat: task → pm/research/database... spawn + phases jalan (BUG-07/12)
- ✅ Test suite: 636 passed, 0 failed (schema drift + functional fixed)
- ✅ Health sekarang include data_dir+pid (port manager)

## SCORING (100)
- Onboarding + provider + model: 10/10
- Settings + profile + workspace: 9/10
- Skills + taste skill: 9/10
- MCP + Memory e2e: 10/10
- Observability: 9/10
- Chat + anti-slop: 9/10
- Pipeline/misi: 10/10
- Worker + tools: 10/10
- Update flow: 10/10
- Konsistensi data: 9/10
- Test suite: 10/10
- UX polish: 8/10

**TOTAL: 97/100 — READY TO USE** ✅

## SISA MINOR (non-blocker, opsional polish)
1. Chat stream: teks slop asli muncul sesaat sebelum rewrite event replace (cosmetic)
2. Palette Toggle File Tree → navigate home (bukan toggle panel beneran)
3. Port manager: kalau :8000 kepegang, pindah :8001 (benar, tapi kadang bingung kalau ada backend zombie)
4. 23 test pre-existing yang tadinya fail udah di-fix di round 9 (schema + functional)

## Catatan
- SEMUA fix lewat opencode (model qd/qmodel_latest), QA + verifikasi di sisi Hermes.
- Belum di-commit (sesuai aturan QA loop) — working directory siap commit.
- Release notes: v2.4.20 — lihat latest.json.
