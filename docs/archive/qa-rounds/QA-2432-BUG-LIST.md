# AIC-ADE v2.4.32 — FULL BUG LIST (updated)

## 1. Window controls (- [ ] X) hilang
- Tombol minimize/maximize/close di pojok kanan atas title bar tidak muncul
- Window ga bisa di-fullscreen atau digerakkan (drag ga jalan)
- Title bar mungkin kehilangan `-webkit-app-region: drag`

## 2. BUILD | PLAN huruf besar semua
- Tulisan "build" dan "plan" di composer jadi "BUILD" dan "PLAN" (capslock)
- Harusnya: "build" dan "plan" (lowercase)

## 3. Dropdown provider background putih, tulisan tidak terbaca
- Di model selector (THINKER/CRAFTER/SPRINTER), dropdown provider/model background-nya putih
- Tulisan putih di background putih → tidak terbaca
- Harusnya: dark theme (background gelap, tulisan terang)

## 4. Model isolation masih belum fix
- Provider A dipilih, tapi model dari Provider B juga muncul
- Solusi user: simpan model config per-provider dalam JSON
- Fetch baru update model list

## 5. Icon desktop masih logo lain
- Windows icon di taskbar/title bar belum logo AIC ADE
- Perlu generate `.ico` multi-size + optimized PNG

## 6. UI chat kepotong
- Composer terlalu besar, area chat kepotong
- Perlu kompaksi vertical

## 7. Model selector belum muncul di empty state
- THINKER/CRAFTER/SPRINTER dropdown hanya muncul setelah session dibuat

## 8. Build icon optimalisasi
- `build/icon.png` 1.89MB terlalu besar
- Perlu resize + compress + generate `.ico`

## 5. Context size mismatch (model capacity vs displayed)
- minimax-m3 punya context ~397k di 9Router
- Tapi di chat bar nunjukin `4 / 1,000,000` (1M hardcoded)
- Harusnya ambil context window real dari model (397k)
- Juga: `4` itu message count, bukan token usage

## 6. Composer layout — area kosong di kanan
- Baris BUILD | PLAN + THINKER/CRAFTER/SPRINTER ga memanjang sampai kanan
- Ada ruang kosong di sebelah kanan
- Harusnya flex-wrap atau justify-content biar penuh

## 7. Context bar styling
- Label "Context" harusnya warna biru (sama kaya BUILD aktif)
- Progress bar: hijau (low) → kuning (medium) → merah (high)
- Contoh: < 50% = hijau, 50-80% = kuning, > 80% = merah