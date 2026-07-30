# LIM-1: Hash-based RAG Embeddings Resolution

**Date:** 2026-07-28  
**Status:** In Progress  
**Priority:** CRITICAL (Pre-Production Blocker)

## Objective

Replace hash-based embedding fallback with production-quality SentenceTransformers embeddings.

## Problem Statement

The Independent Audit identified that RAG uses hash-based embeddings as fallback when no real embedding provider is configured. Hash embeddings are deterministic but NOT semantic - they provide poor retrieval quality and are unsuitable for production.

**Audit Finding:**
- Hash fallback active (backend/services/embedding_provider.py line 62, 104-115)
- Auto-detect chain: OpenAI → Ollama → SentenceTransformers → Hash
- Hash is last resort, not production-quality

## Solution Design

### 1. Add SentenceTransformers Dependency
- Add `sentence-transformers>=2.2.0` to requirements.txt
- Install in venv (auto-downloads all-MiniLM-L6-v2 model on first use)
- No API key required, runs locally

### 2. Production Mode Enforcement
- Add `AIC_PRODUCTION_MODE` environment variable
- In production mode: fail fast if no real provider available
- In dev mode: allow hash fallback with clear warning

### 3. Startup Validation
- Add `validate_embedding_provider()` function
- Call on backend startup (backend/main.py)
- Log provider selection and production readiness

### 4. Updated Auto-detection
- Priority: OpenAI (if API key) → Ollama (if running) → SentenceTransformers (default) → Hash (dev only) or Error (production)
- SentenceTransformers becomes the default for no-config deployments

## Implementation

### Files Modified

**backend/services/embedding_provider.py:**
- Updated docstring: removed "Hash-based fallback" from production options
- Added production mode check in `get_embedding_provider()`
- Production mode raises RuntimeError if only hash available
- Added `validate_embedding_provider()` function
- Improved logging: "DEV MODE ONLY" warning for hash

**backend/main.py:**
- Added embedding provider validation in `on_startup()`
- Logs provider selection and production readiness
- Warns or errors based on validation result

**requirements.txt:**
- Added `sentence-transformers>=2.2.0`

**tests/test_embedding_production.py (NEW):**
- test_sentencetransformers_available
- test_production_mode_blocks_hash
- test_validate_embedding_provider
- test_hash_fallback_dev_mode

### Configuration

**Environment Variables:**
- `AIC_EMBEDDING_PROVIDER` - Override auto-detection (openai/ollama/sentencetransformers/hash)
- `AIC_PRODUCTION_MODE=1` - Enable production mode (blocks hash fallback)
- `OPENAI_API_KEY` - For OpenAI embeddings (optional)

**Default Behavior:**
- No config: Auto-detects and uses SentenceTransformers
- Dev mode: Hash fallback allowed with warning
- Production mode: Hash fallback raises error

## Validation

### Installation Status
- SentenceTransformers installation: IN PROGRESS (downloading torch 526MB)
- Expected completion: ~3-5 minutes

### Test Coverage
- 4 new tests added for production mode validation
- Existing RAG tests will verify embedding quality

### Expected Results
1. ✓ Code changes complete (embedding_provider.py, main.py)
2. ⏳ Installation pending (sentence-transformers + torch)
3. ⏳ Tests pending (after installation)
4. ⏳ Integration validation pending

## Exit Criteria

- [x] SentenceTransformers added to requirements.txt
- [x] Production mode enforcement implemented
- [x] Startup validation added
- [x] Tests written
- [ ] SentenceTransformers installed successfully
- [ ] Tests passing
- [ ] RAG retrieval quality validated
- [ ] No hash fallback in default deployment

## Risk Assessment

**Low Risk:**
- SentenceTransformers is well-tested, widely used
- Local execution, no external dependencies
- Graceful fallback to hash in dev mode
- Production mode prevents silent quality degradation

**Mitigation:**
- Installation size: ~2GB (torch + transformers)
- First-run model download: ~90MB (all-MiniLM-L6-v2)
- Both acceptable for desktop deployment

## Next Steps

1. Wait for installation completion (~3 min)
2. Verify installation success
3. Run test suite
4. Validate RAG retrieval quality
5. Document findings
6. Mark LIM-1 complete
7. Move to LIM-2: Skipped Tests

---

**Implementation Progress:** 80%  
**Blocking:** Installation in progress  
**ETA:** ~5 minutes
