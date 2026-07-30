# 10 — Provider Runtime

**Subsystem:** Provider & Model Management Core  
**Package:** `aic-platform/llm`  
**Files:** `llm/provider.py`, `backend/routes/llm.py`  

---

## 1. Multi-Provider BYOK Architecture

AIC-ADE supports any OpenAI-compatible API endpoint:
- OpenAI (`api.openai.com`)
- OpenRouter (`openrouter.ai/api/v1`)
- Local Models (Ollama, LM Studio, vLLM)
- Custom Routers (VansRouter, 9Router, AMRouter)

---

## 2. Smart Tier Fallback Chain

```
User Request
     │
     ▼
[Thinker Tier] ──(On Error)──► [Crafter Tier] ──(On Error)──► [Sprinter Tier] ──(On Error)──► Real Error
```

- **Thinker:** High-reasoning tasks (Architecture, System Design, Security Audit).
- **Crafter:** Primary execution tasks (Coding, Task Breakdown, Refactoring).
- **Sprinter:** Fast tasks (Unit test generation, Status formatting, Reviews).

No "Default Model" is used. If a requested tier fails, the system automatically retries with lower tiers before surfacing the true provider error.
