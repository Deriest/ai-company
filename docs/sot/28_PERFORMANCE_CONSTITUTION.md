# 28 — Performance Constitution

**Subsystem:** Resource Optimization & Latency Guidelines  

---

## 1. Target Metrics

- **App Startup Time:** Desktop window renders in under 1.5 seconds.
- **Sidecar Boot Time:** FastAPI backend initializes database and endpoints in under 2.0 seconds.
- **UI Responsiveness:** 60 FPS rendering on modern desktop displays; no main thread blocking during SSE streaming.
- **Memory Footprint:** Electron + Python sidecar combined memory usage remains under 450 MB during active sessions.
