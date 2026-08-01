# OpenCode Task: AIC-ADE v2.4.20 — Commit + Tag + Release

> Role: Senior Engineer. Work in `/home/tvd/AI-Company`. 
> Konteks: 9 round fix (v2.4.9 → v2.4.20) sudah selesai & terverifikasi (636 pytest pass, build AppImage+deb ada di `app/release/`, latest.json sudah v2.4.20). Sekarang tinggal COMMIT + TAG + PUSH + release notes.

## Langkah

### 1. Review diff (JANGAN commit dulu sebelum lihat)
- `git status --short` (saat ini ~86 file modified, semua uncommitted)
- `git diff --stat` — pastikan tidak ada file aneh/artifact build yang masuk (AppImage/deb TIDAK boleh di-commit; pastikan .gitignore menutup `app/release/`)
- Cek `git diff app/package.json backend/backend/config.py` — version harus 2.4.20

### 2. Commit
- Buat SATU commit rapi (conventional): message utama + body yang merangkum semua perubahan:
  - `release: v2.4.20 — QA loop 9 rounds, 20 bugs fixed, MCP Memory + Taste system`
  - Body: list perubahan per area (backend engine/pipeline, chat/SSE tool_calls, MCP memory, taste anti-slop, launcher/port, migrations/tests)
- JANGAN split banyak commit — satu commit release cukup (repo ini polanya gitu: "release: v2.4.x")

### 3. Tag
- `git tag v2.4.20` (annotated: `git tag -a v2.4.20 -m "release v2.4.20 ..."`)
- Cek `git tag` tidak bentrok (v2.4.20 harus belum ada)

### 4. Push
- `git push origin main && git push origin v2.4.20`
- KALAU auth gagal (push 403/not authorized): JANGAN stuck — laporkan + tinggalkan perintah siap pakai. Remote pakai HTTPS; kalau butuh token, pola yang dipakai di repo ini: inject token ke URL remote (`git remote set-url origin https://<user>:<token>@github.com/Deriest/ai-company.git`) — tapi JANGAN tulis token ke file/dotfile; kalau tidak ada token tersedia di env, cukup laporkan blocker.

### 5. Release notes
- Update `CHANGELOG.md` (kalau ada) / buat section v2.4.20: ringkasan fitur + fix + bukti (636 test pass, 2 fitur baru)
- Pastikan `latest.json` sudah v2.4.20 (jangan ubah kalau sudah benar)

## Acceptance
1. `git log --oneline -1` → commit release v2.4.20
2. `git tag` → v2.4.20 ada
3. `git push origin main` sukses (atau laporan blocker auth yang jelas)
4. `git push origin v2.4.20` sukses (atau blocker)
5. `git status --short` bersih (kecuali untracked yang memang harus diabaikan)
6. Laporkan: commit hash, tag, push status, CHANGELOG
