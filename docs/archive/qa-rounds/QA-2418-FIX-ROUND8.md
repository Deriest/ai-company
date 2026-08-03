# OpenCode Task: AIC-ADE 2.4.18 → 2.4.19 — Fix Taste Gap (chat masih "How can I help you today?")

> Role: Senior Backend Engineer. Work in `/home/tvd/AI-Company`.
> MANDATORY: jangan klaim fix tanpa bukti. Setiap perbaikan WAJIB: (1) diff source, (2) test/repro runtime, (3) verifikasi di app. JANGAN commit sampai terbukti.
> SETELAH SEMUA TERBUKTI: bump ke 2.4.19 (package.json + `backend/backend/config.py` fallback) + BUILD (`cd app && npm run build && npx electron-builder --linux AppImage deb`), update latest.json lengkap. `/health` HARUS report 2.4.19.

## Konteks
- Stack: Electron+React + FastAPI+SQLite. Gateway VansRouter `http://127.0.0.1:20129/v1`. Model stabil: kr/qwen3-coder-next, kr/claude-sonnet-4.5, qd/qmodel_latest, WF/wf/*.
- Round 1-7 SUDAH FIX & VERIFIED: BUG-01..19, MCP Memory e2e (create/search/persist JALAN), tool calling builtin+mcp JALAN (BUG-19 SSE fix), taste checker + skill + rewrite pass ada. JANGAN regresi.
- SATU gap tersisa dari QA 2.4.18: chat app MASIH menjawab "Hi! How can I help you today?" — AI-ism khas yang TIDAK ter-detect taste_checker.

# BUG-20 (MEDIUM): Taste checker wordlist TIDAK menangkap greeting AI-ism umum → chat tetap slop
- Gejala (verified di 2.4.18): chat "halo" → response `Hi! How can I help you today?` — taste checker TIDAK trigger rewrite (has_ai_slop false). Engine rewrite pass (backend/conversation/engine.py ~735-760) SUDAH ada: kalau high>0 → LLM rewrite. Masalahnya wordlist tidak lengkap.
- Root cause: `backend/backend/services/taste_checker.py` wordlist cuma punya sebagian pola ("great question", "let me know if", dll) — MISSING pola greeting/polite umum: "how can i help", "i'd be happy to", "happy to help", "is there anything else", "feel free to", "don't hesitate", "let me know if you", "absolutely!", "of course!", "certainly!", "good question", "hope this helps", "what else can i do".
- Fix:
  1. Perluas `BANNED_PHRASES` di taste_checker.py — tambahkan (case-insensitive, substring):
     - "how can i help" (menangkap "How can I help you today?")
     - "i'd be happy to", "happy to help"
     - "is there anything else", "anything else i can"
     - "feel free to", "don't hesitate", "do not hesitate"
     - "absolutely!", "of course!", "certainly!"
     - "good question", "great question" (sudah ada? pastikan)
     - "hope this helps", "i hope this helps"
     - "let me know if you need"
     - "what else can i do"
     - "as an ai", "as an ai assistant", "as a language model"
     - "i'm here to help", "here to help you"
  2. JANGAN false-positive bahasa Indonesia: "saya bisa membantu", "ada yang bisa saya bantu" TIDAK boleh ke-flag. Verifikasi dengan test.
  3. Pastikan greeting "Hi! How can I help you today?" → has_ai_slop TRUE → rewrite pass trigger → response bersih.
  4. Perkuat Lapis 2 guardrail system prompt chat (`backend/conversation/engine.py` SYSTEM_PROMPT + agent registry) dengan instruksi eksplisit: "Jangan buka percakapan dengan greeting generik seperti 'How can I help you today?' / 'Hi! How can I' — jawab langsung dan spesifik."
- Acceptance:
  1. `scan_text("Hi! How can I help you today?")` → findings > 0 (high).
  2. `scan_text("Halo! Ada yang bisa saya bantu hari ini.")` → 0 findings (NO false positive).
  3. Chat "halo" di app → response TIDAK mengandung "How can I help you today?" / "Hi! How can I" / "Great question!" / "I'd be happy to" / "Let me know if".
  4. Unit test baru di `backend/tests/test_taste_checker.py` untuk pola-pola ini.

# VERIFIKASI E2E (setelah fix — runtime)
1. Chat "halo" → response manusiawi, tanpa greeting generik (screenshot/curl bukti).
2. Chat "buatkan saya aplikasi catatan" → task pipeline jalan (regresi), response proposal tidak slop.
3. Memory masih jalan (create/search) — regresi check cepat.
4. Builtin tool masih jalan (list_directory) — regresi check cepat.

# Acceptance Criteria GLOBAL (sebelum build 2.4.19)
1. BUG-20: greeting AI-ism ter-detect + rewrite/guardrail → chat bersih (bukti curl).
2. Tidak ada regresi BUG-01..19 (tool calling, memory, pipeline, dsb).
3. pytest hijau ATAU laporkan (23 pre-existing failure — jangan tambah baru).
4. Build 2.4.19 + /health 2.4.19 + latest.json lengkap.
5. JANGAN commit sampai semua terbukti; laporkan diff + test + curl bukti.

## Repro Cepat
```bash
cd /home/tvd/AI-Company/backend && export AIC_DATA_DIR=/tmp/aicade-fix-r8
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
# (provider aktif, lalu:)
curl -s -N -X POST http://127.0.0.1:8000/chat/stream -H "Content-Type: application/json" \
  -d '{"conversation_id":"c1","messages":[{"role":"user","content":"halo"}]}' --max-time 30
# response TIDAK boleh mengandung "How can I help you today?"
.venv/bin/python -c "from backend.services.taste_checker import scan_text; print(len(scan_text('Hi! How can I help you today?')))"  # > 0
.venv/bin/python -c "from backend.services.taste_checker import scan_text; print(len(scan_text('Halo! Ada yang bisa saya bantu hari ini.')))"  # == 0
```

## Catatan
- Jangan ubah VansRouter. Jangan regresi fix sebelumnya (terutama BUG-19 SSE tool_calls).
- Backend port bisa 8000/8001/8002 — pakai port sesuai startup log.
