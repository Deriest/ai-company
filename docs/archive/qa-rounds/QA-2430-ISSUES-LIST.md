# AIC-ADE v2.4.30 — ISSUE LIST (LENGKAP, belum di-fix)

## 1. UI berantakan kalau tidak fullscreen
- Layout pake fixed heights, ga responsive
- Waktu window di-resize, elemen overlap/ilang
- Harusnya pake flex layout + responsive units + overflow-y-auto

## 2. Context size masih hardcoded 1,000,000 sebelum pilih provider
- Sebelum provider dipilih, context bar nunjukin `1,000,000`
- Harusnya: `?` atau `N/A` sampai provider & model terkonfigurasi
- Atau ambil default dari model yang paling umum dipakai

## 3. Execution Engine: model ilang setelah save
- User pilih provider + model → save → model hilang
- Kemungkinan: state ga persist ke backend, atau config ga di-load balik

## 4. Model isolation belum fix (2 provider, pilih TVD masih show kedua)
- User punya 2 provider (TVD + lainnya)
- Fetch models → pilih TVD → dropdown masih nunjukin model dari kedua provider
- `fetchAllModels` fix mungkin belum cukup — perlu cek `handleTierProviderChange` + state management

## 5. Windows: chat muncul 1 detik terus hilang
- Di Windows, response chat keliatan sesaat trus ilang
- Mungkin: state di-reset setelah render, atau streaming response ga di-handle bener
- Di Linux: OK (tested)

## 6. Hapus footer "System operational"
- User minta footer di remove
- File: `app/src/renderer/src/components/AppShell.tsx` — hapus `<footer>` block

## 7. Command Center: tambah model selector (Thinker/Crafter/Sprinter) di composer
- Di area composer (di atas textarea), sebelah tombol "build" dan "plan", masih ada banyak area kosong
- Tambah 3 dropdown kecil untuk milih model: Thinker, Crafter, Sprinter
- **Saat user pilih model → auto-save ke engine** (TIDAK perlu tombol "Save" terpisah)
- **Model isolation: pilih Provider A → dropdown cuma show model Provider A** (jangan gabung)
- Tambah tombol "Fetch Models" kecil di ujung kanan (refresh model list dari provider)
- Hasil fetch model selalu tersimpan
- Jadi user bisa ganti model + fetch model langsung dari Command Center, tanpa harus ke Settings
- Ambil daftar model dari provider yang terkonfigurasi
- File: `app/src/renderer/src/components/ChatView.tsx` — area composer sekitar line ~740-810
- Layout: 1 baris, `BUILD | PLAN` di kiri, lalu `THINKER: [Provider▼] [Model▼]` `CRAFTER: [Provider▼] [Model▼]` `SPRINTER: [Provider▼] [Model▼]` lalu `[⟳ Fetch Models]` di ujung kanan
- Muat karena area lebar ~900px ✅

## 8. CATATAN EKSEKUSI
- Semua item DI-LIST dulu, tunggu user approve
- JANGAN fix sebelum user bilang OK
- Urutan prioritas: Footer (6) → Responsive (1) → Context size (2) → Model save (3) → Model isolation (4) → Windows chat (5)
- OpenCode model: TR/deepseek/deepseek-v4-flash (yang sudah diset user)