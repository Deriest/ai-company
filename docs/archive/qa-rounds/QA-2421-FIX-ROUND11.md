# OpenCode Task: AIC-ADE 2.4.21 → 2.4.22 — UI Fix Round 11 (ALL UI issues from QA)

> Role: Senior Frontend/Backend Engineer. Work in `/home/tvd/AI-Company`.
> MANDATORY: jangan klaim fix tanpa bukti. Setiap perubahan WAJIB: (1) diff source, (2) verifikasi runtime (screenshot + curl). JANGAN commit sampai terbukti.
> SETELAH SEMUA: bump ke 2.4.22 (package.json + config.py) + BUILD Linux + Windows (`cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`), update latest.json (linux + win32), copy ke app/release/. JANGAN subagent/parallel fixer — kerjakan langsung.

## Konteks
- Semua bug BUG-01..20 sudah fixed di round 1-10 (tool calling, memory, taste, pipeline, test suite, dll).
- Round 11 = UI polish (rename app, layout card, observability, command center, empty states, footer overlap).
- Logo final: `/home/tvd/aic-ade-logo.png` — PAKAI INI, jangan diganti. Copy ke build/icon.png + src/renderer/public/aic-ade-logo.png.
- JANGAN regresi fitur yang sudah jalan (tool calling, memory, pipeline, chat, update).

# ITEM PERUBAHAN (kerjakan urut prioritas)

## 1. NAMA APP: "AI Company ADE" → "AICompany ADE" (hilangkan spasi)
Ubah di:
- `app/package.json` → build.productName + build.executableName (jadi "AICompany ADE")
- `app/src/main/main.ts:354` → title: "AICompany ADE"
- `app/src/renderer/src/components/AppShell.tsx:94-95` → alt + span text "AICompany ADE"
- `app/src/renderer/public/aic-ade-logo.png` → SUDAH ADA, jangan diubah (file benar)
- AppId `id.aicompany.ade` TETAP, nama file installer `AIC-ADE-Setup-*.exe` + AppImage TETAP

## 2. GAMBAR 03 — Title bar + Nav bar format `[LOGO] AICompany ADE` + `- [ ] X`
- Title bar: `[LOGO] AICompany ADE` di kiri, `- [ ] X` (minimize/maximize/close) di kanan
- Nav bar: "▲ AICompany ADE" (rename)
- File: `src/main/main.ts` (BrowserWindow title), komponen header/title bar

## 3. GAMBAR 02 — Skill Registry: layout card baru + footer overlap
- **Semua card skill**: header = `[LOGO] AICompany ADE` di kiri, `- [ ] X` (action buttons) di ujung kanan
- **Footer overlap**: card bawah (Quality/Anti-AI-Slop Taste) terpotong taskbar — tambah padding/margin bottom di app window, pastikan scroll konten tidak ketindih taskbar
- JANGAN hapus fitur Anti-AI-Slop Taste — ini soal UI LAYOUT, bukan fitur
- File: `app/src/renderer/src/components/SkillsView.tsx` atau komponen skill card

## 4. GAMBAR 04 — Live Company: layout card worker format baru
- **Semua card worker** (Leadership, Product, Engineering, Platform): header = `[LOGO] AICompany ADE` di kiri, `- [ ] X` di ujung kanan
- JANGAN hapus departemen Platform — ini soal UI LAYOUT, bukan hapus
- File: `app/src/renderer/src/components/LiveCompanyView.tsx`

## 5. GAMBAR 01 — Office Layout: floating panel terpotong di kanan
- Floating panel di kanan Office terpotong (clipped) oleh viewport edge — fix overflow/positioning
- File: `app/src/renderer/src/components/VirtualOfficeCanvas.tsx` atau `WorkspaceView.tsx`

## 6. EXECUTION ENGINE — hapus 3 subtitle "Used by..."
- `app/src/renderer/src/components/SettingsView.tsx` baris 246, 264, 282: hapus 3 `<p>` subtitle

## 7. OBSERVABILITY — restruktur tab
- `app/src/renderer/src/components/ObservabilityView.tsx`
- Hapus tab `context` + `workers` (termasuk fetch + render)
- Merge `usage` ke tab `overview`
- Tambah tab `graph` (baru, placeholder)
- activeTab type: `'overview' | 'graph'`

## 8. COMMAND CENTER — restruktur chat UI
- File: `app/src/renderer/src/components/ChatView.tsx`
- **8a. Status bar** → ganti dengan context progress bar memanjang di atas: `total msg: 100.000 / 1.000.000` (progress bar)
- **8b. Build | plan toggle** → pindah dari header kanan atas ke dekat composer
- **8c. Composer**: hapus `❯` prefix, hapus placeholder "describe what to build", stretch penuh (hapus max-w-3xl mx-auto)
- **8d. Message**: user message rata kiri, format `> hello` (tanpa dots, tanpa icon rumit)
- **8e. Chat Hermes** → cek: chat ke Hermes tidak ada response — perlu investigasi endpoint

## 9. LOGO — copy file final
- `cp /home/tvd/aic-ade-logo.png app/build/icon.png` (ikon app)
- `cp /home/tvd/aic-ade-logo.png app/src/renderer/public/aic-ade-logo.png` (sidebar logo)
- Pastikan ukuran responsif (16x16 di sidebar, 512x512 untuk icon)

## 10. EMPTY WORKSPACE — meaningful empty state
- Area kerja kosong putih polos → ganti dengan: penjelasan + tombol action "Open Project" / "Create New Project"
- File: cari komponen workspace/editor view

# Acceptance Criteria
1. Semua rename "AI Company ADE" → "AICompany ADE" konsisten (cek grep)
2. Semua card/header format `[LOGO] + AICompany ADE + - [ ] X` (screenshot bukti)
3. Footer overlap: scroll content tidak ketindih taskbar
4. Observability: 2 tab (overview+usage, graph)
5. Command Center: context bar, build/plan dekat composer, message rata kiri
6. Office: floating panel tidak terpotong
7. Build Linux AppImage + Windows exe keduanya sukses
8. latest.json update lengkap (linux + win32)
9. Copy latest.json ke app/release/ + SHA256SUMS

# Catatan
- Logo final: `/home/tvd/aic-ade-logo.png` — PAKAI INI, jangan diganti
- Jangan regresi fitur yang sudah jalan (tool calling, memory, pipeline, taste)
- Build Windows: `npx electron-builder --win nsis --x64` (wine tersedia)