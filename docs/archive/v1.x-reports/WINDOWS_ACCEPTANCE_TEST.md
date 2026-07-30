# AIC ADE — Physical Windows Acceptance Test

**Primary artifact:** `AIC-ADE-Setup-1.0.0.exe`  
**Public URL:** `https://download.aicompany.biz.id/AIC-ADE-Setup-1.0.0.exe`  
**LAN fallback:** `http://192.168.2.10:8088/AIC-ADE-Setup-1.0.0.exe`  
**SHA256:** `115c87cb5014c4bb9f061e496839ad5684304a619e596d5650f8a43a45b7df8d`

Secondary portable (optional):
`AIC-ADE-1.0.0-Windows-Portable.exe`  
SHA256: `129c4b5ab1aeb8fb475fc6de4efa418cc603d2be37fa8765f6ef32b2c6633c82`

---

## Preconditions (clean machine preferred)

- Windows 10/11 x64
- **No** Python installed (or temporarily remove from PATH)
- **No** Node/npm
- **No** AIC source checkout
- **No** manual backend start

---

## Steps

1. Download **Setup.exe** from the public URL.
2. Verify size ~141 MB and optional SHA256 match.
3. Run installer → install to default user location → open Start Menu **AIC ADE**.
4. Confirm:
   - Window title: **AIC ADE**
   - Status becomes **Engine: Ready** without terminal commands
   - No “Runtime connection / Base URL / Username / Password” form
5. Settings → AI Providers:
   - Add **Custom OpenAI-Compatible** (or OpenAI / OpenRouter)
   - Enter Base URL + API key + **Model ID**
   - Test Connection (expect Connected / Auth Failed / Unreachable — not raw “Failed to fetch”)
   - Activate provider
6. Titlebar model control shows:  
   `model-id · ProviderName`  
   not “Active Provider”
7. Home → Open/Create project → Talk to Hermes with a real request.
8. Observe task progress and that files change on disk when engineering runs.
9. Close AIC ADE → Task Manager has no orphaned `python.exe` owned by AIC.
10. Reopen → provider + project state persist.

---

## Report back

- Launch: SUCCESS / FAIL
- Engine: Ready / Error (paste message)
- Model label: (exact string shown)
- Task/files: PASS / FAIL
- Cleanup: Clean / Orphans
- Python preinstalled on machine? YES / NO
