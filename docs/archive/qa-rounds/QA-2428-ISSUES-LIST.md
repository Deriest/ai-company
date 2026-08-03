# AIC-ADE v2.4.28 — ISSUE LIST (belum di-fix)

## 1. Context size hardcoded (1,000,000)
- File: `app/src/renderer/src/components/ChatView.tsx:745`
- Baris: `total msg: {messages.length.toLocaleString()} / 1,000,000`
- Masalah: `1,000,000` di-hardcode, bukan dari model actual context window
- Harusnya: ambil max context dari model yang dipakai (misal dari provider model config)
- User nanya: "itu dari mana? sesuai dari model?" — jawaban: hardcoded, TIDAK sesuai model

## 2. Windows chat di Command Center tidak ada response
- User: "chat di command center ga muncul di balas"
- Di Linux: chat berfungsi (tested & verified via vision — response "OK" muncul)
- Kemungkinan penyebab:
  a. Windows tidak punya provider terkonfigurasi (error "No AI provider configured")
  b. Ada perbedaan endpoint / path yang dipakai
  c. Network issue (VansRouter tidak reachable dari Windows)
- Perlu: debug di Windows langsung

## 3. Skills Registry — card terakhir (Security Audit) masih terpotong
- Card "Security Audit & Vulnerability Scanning" bagian bawah masih terpotong
- Tag "built-in" hanya terlihat setengah
- Penyebab: content height > available viewport height

## 4. Office UI — user bilang "masih jelek"
- User sebelumnya bilang "bagian office masih jelek uinya"
- Vision analysis menunjukkan layout rapi, tapi user merasa kurang
- Mungkin perlu polish lebih lanjut

## 5. Update check error (SUDAH DI-FIX)
- Server download_server.py mati karena kebunuh pas cleanup zombie
- Udah di-restart, serve v2.4.28 di port 8088 ✅

## 6. Hapus halaman Observability (sudah ada di Live Company)

File yang perlu diubah:
| File | Baris | Perubahan |
|---|---|---|
| `app/src/renderer/src/components/AppShell.tsx` | 31 | Hapus `{ id: "observability", label: "Observability", icon: BarChart3 }` dari sidebar nav |
| `app/src/renderer/src/components/CommandPalette.tsx` | 26 | Hapus entry `'Go to Observability'` |
| `app/src/renderer/src/App.tsx` | 17 | Hapus import `ObservabilityView` |
| `app/src/renderer/src/App.tsx` | 161-162 | Hapus case `"observability"` |
| `app/src/renderer/src/components/ObservabilityView.tsx` | - | Hapus file (opsional, bisa diarsipkan) |

## 7. CATATAN EKSEKUSI
- Urutan: Observability (6) → Context size (1) → Skills card (3) → Office UI (4) → Windows chat (2)
- JANGAN eksekusi sebelum user approve