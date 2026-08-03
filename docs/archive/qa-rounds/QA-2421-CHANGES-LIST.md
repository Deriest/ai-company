# AIC-ADE — LIST PERUBAHAN (10 item, urutan gambar sudah diverifikasi ulang)

Dibuat: 2026-08-02 | Status: LIST SAJA, belum di-fix
**Logo konfirmasi:** `/home/tvd/aic-ade-logo.png` — logo AIC ADE final, PAKAI INI untuk semua logo (tidak perlu diganti).

---

## 1. NAMA APP: "AI Company ADE" → "AICompany ADE" (hilangkan spasi)

Lokasi yang harus diubah:
| # | File | Baris | Isi sekarang | Menjadi |
|---|---|---|---|---|
| 1 | `app/package.json` | build.productName | `"AI Company ADE"` | `"AICompany ADE"` |
| 2 | `app/package.json` | build.executableName | `"AI Company ADE"` | `"AICompany ADE"` |
| 3 | `app/src/main/main.ts` | 354 | `title: "AI Company ADE"` | `title: "AICompany ADE"` |
| 4 | `app/src/renderer/src/components/AppShell.tsx` | 95 | span text `AI Company ADE` | `AICompany ADE` |
| 5 | `app/src/renderer/src/components/AppShell.tsx` | 94 | alt `AI Company ADE` | `AICompany ADE` |

Efek turunan: exe Windows, taskbar name, window title ikut berubah.
Catatan: `appId: id.aicompany.ade` TETAP (biar user data ga migrasi), nama file installer `AIC-ADE-Setup-*.exe` + AppImage TETAP.

## 2. GAMBAR 01 — Office Layout: floating panel terpotong di kanan (01-office-layout.jpg)

**Masalah:** ada floating window/panel di sisi kanan Office yang terpotong (clipped) oleh tepi kanan viewport — tidak bisa melihat isi panel secara penuh. Tidak ada overlap footer.

**Fix:** pastikan semua floating panel/modal di Office layout tidak terpotong — atur posisi/overflow viewport dengan benar.

**File:** `app/src/renderer/src/components/VirtualOfficeCanvas.tsx` atau `WorkspaceView.tsx`

## 3. GAMBAR 02 — Skill Registry: layout card baru + footer overlap (02-skills-registry-full.jpg)

**Masalah UI (garis putih):** kategori "Quality" dengan skill "Anti-AI-Slop Taste" ditandai — ini soal LAYOUT card skill, bukan hapus fitur. Semua card skill harus diubah formatnya.

**3a. Layout card skill baru:** header card = `[LOGO] AICompany ADE` di kiri, `- [ ] X` (action buttons) di ujung kanan. Berlaku untuk SEMUA card skill di Skill Registry.

**3b. Footer overlap:** skill card "Anti-AI-Slop Taste" di bagian bawah TERPOTONG oleh Windows taskbar — setengah card tidak terlihat. Perlu padding/margin bottom di app window agar konten tidak ketindih taskbar.

**File:** `app/src/renderer/src/components/SkillsView.tsx` (atau komponen skill card terkait)

## 4. GAMBAR 03 — IDE Workspace: title bar format baru (03-ide-empty-workspace.jpg bagian atas)

**Masalah UI (garis putih):** title bar "AIC IDE" + menu bar "File/Edit/View/Window/Help" + nav bar "▲ AI Company ADE" ditandai — ini soal LAYOUT header.

**Fix:** SAMA dengan gambar 02 — format baru `[LOGO] AICompany ADE` + `- [ ] X`:
- Title bar: `[LOGO] AICompany ADE` di kiri, `- [ ] X` (minimize/maximize/close) di ujung kanan
- Nav bar: rename "AI Company ADE" → "AICompany ADE"
- Menu bar: File, Edit, View, Window, Help — tetap (atau digabung)

**File:** `src/main/main.ts` (BrowserWindow title + frame), `src/renderer/src/components/AppShell.tsx` (sidebar header/nav bar)

## 5. GAMBAR 04 — Engineering Workforce: layout card Platform (04-skills-registry.jpg → Live Company)

**Masalah UI (garis putih):** departemen "Platform" (Nova, Nexus, Flint, Sentinel) ditandai — ini soal LAYOUT card worker, sama seperti gambar 02/03.

**Fix:** format card worker sama: `[LOGO] AICompany ADE` di kiri, `- [ ] X` di ujung kanan. Berlaku untuk SEMUA card worker di Live Company (Leadership, Product, Engineering, Platform).

**File:** `app/src/renderer/src/components/LiveCompanyView.tsx`

## 6. EXECUTION ENGINE — hapus subtitle "Used by..."

Tiga baris di `app/src/renderer/src/components/SettingsView.tsx`:
| Baris | Sekarang | Jadinya |
|---|---|---|
| 246 | `<p>Used by Planner, Architect, Research</p>` | DIHAPUS |
| 264 | `<p>Used by Backend, Frontend, QA</p>` | DIHAPUS |
| 282 | `<p>Used by Docs, Governor</p>` | DIHAPUS |

## 7. OBSERVABILITY — restruktur tab

File: `app/src/renderer/src/components/ObservabilityView.tsx`

**Sekarang (4 tab):** overview, context, workers, usage
**Jadinya (2 tab):** overview (include usage), graph

| Item | Sekarang | Jadinya |
|---|---|---|
| Tab `context` | Ada | DIHAPUS — tab + fetch + card |
| Tab `workers` | Ada | DIHAPUS — tab + fetch + render |
| Tab `usage` | Pisah sendiri | DIMERGE ke tab `overview` |
| Tab `graph` | Tidak ada | DITAMBAH — tab baru |
| `activeTab` type | `'overview' \| 'context' \| 'workers' \| 'usage'` | `'overview' \| 'graph'` |

## 8. COMMAND CENTER — restruktur chat UI

File: `app/src/renderer/src/components/ChatView.tsx`

### 8a. Status bar → context progress bar
- HAPUS: status bar `connected/offline` + `build agent` + `inspector` toggle + `Hermes` label
- TAMBAH: bar konteks memanjang di atas: `total msg: 100.000 / 1.000.000` dengan progress bar

### 8b. Tombol build | plan — pindah ke dekat composer
- Sekarang: di header kanan atas
- Jadinya: di dekat box composer (agar gampang di-press)

### 8c. Composer — simplify
- HAPUS: `❯` prefix di textarea
- HAPUS: placeholder `describe what to build`
- LEBARKAN: stretch penuh (hapus `max-w-3xl mx-auto`)

### 8d. Message display — alignment kiri
- User message rata kiri, format `> hello` (tanpa dots, tanpa icon rumit)

### 8e. BUG: Chat ke Hermes tidak ada response — perlu investigasi

## 9. EXECUTION ENGINE — model dropdown menampilkan gabungan

Perlu verifikasi: apakah benar gabungan antar provider atau murni gateway aggregator (VansRouter). Fix setelah dikonfirmasi.

## 10. EMPTY WORKSPACE — meaningful empty state

Area kerja kosong putih polos → ganti dengan: penjelasan "No project open" + tombol action "Open Project" / "Create New Project".

## 11. CATATAN EKSEKUSI (buat opencode nanti)
- Urutan prioritas: Rename app (1) → Gambar 03 title bar (4) → Gambar 02 Skill Registry (3) → Gambar 04 Platform (5) → Command Center (8) → Observability (7) → Execution Engine subtitle (6) → Gambar 01 Office (2) → Empty workspace (10) → Model dropdown (9)
- Logo sudah final: `/home/tvd/aic-ade-logo.png` — PAKAI INI, jangan diganti
- Rebuild 2.4.22 + re-QA + deploy latest.json (copy ke app/release/)
- JANGAN dispatch subagent/parallel fixer — kerjakan langsung di session utama
