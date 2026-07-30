# BACKEND WIRING INVESTIGATION

==================================================
DATE: 2026-07-29
SOURCE: Product Discovery 1-28
==================================================

==================================================
EXECUTIVE SUMMARY
==================================================

Dari investigasi product discovery 1-28, ditemukan bahwa:

**SUDAH DI-WIRING (Fully Functional):**
- ConversationEngine ✓
- Runtime Executor ✓ (melalui _dispatch_created_task)
- Tool Dispatcher ✓
- Chat Service ✓
- Worker Runtime Service ✓
- Artifact Service ✓

**BELUM DI-WIRING (Exists but NOT connected to chat path):**
- Context Builder ✗
- Memory Service ✗
- RAG Service ✗
- Discovery Engine ✗
- Planning Engine ✗
- TaskGraph Engine ✗
- Dispatcher Engine ✗
- Verification Engine ✗
- Delivery Engine ✗
- Autonomy Engine ✗

==================================================
DETAIL ANALYSIS
==================================================

--------------------------------------------------
1. CONTEXT BUILDER
--------------------------------------------------
Status: EXISTS but NOT WIRED
File: context/builder.py
Function: build_chat_context()
Evidence: backend/services/chat_service.py:18-45
Problem: Function exists but NEVER called in chat_stream()
Impact: Context tidak diambil dari memory/RAG saat chat

--------------------------------------------------
2. MEMORY SERVICE
--------------------------------------------------
Status: EXISTS but NOT WIRED
File: backend/services/memory_service.py
Function: store(), retrieve(), compress()
Evidence: Tidak ada import di chat_service.py
Problem: Memory tidak disimpan/diambil otomatis
Impact: AI tidak ingat konteks dari conversation sebelumnya

--------------------------------------------------
3. RAG SERVICE
--------------------------------------------------
Status: EXISTS but NOT WIRED
File: backend/services/rag_service.py
Function: load_document(), retrieve()
Evidence: Tidak ada import di chat_service.py
Problem: Document knowledge tidak diakses saat chat
Impact: AI tidak bisa akses dokumen user

--------------------------------------------------
4. DISCOVERY ENGINE
--------------------------------------------------
Status: EXISTS but NOT WIRED to chat
File: discovery/engine.py
Function: discover(), respond_to_clarification()
Evidence: Hanya diakses via REST API /api/discovery/*
Problem: Tidak otomatis dijalankan saat user request
Impact: Discovery hanya jalan jika manual via API

--------------------------------------------------
5. PLANNING ENGINE
--------------------------------------------------
Status: EXISTS but NOT WIRED to chat
File: planning/engine.py
Function: plan()
Evidence: Hanya diakses via REST API /api/planning/*
Problem: Planning tidak otomatis dijalankan
Impact: Planning hanya jalan jika manual via API

--------------------------------------------------
6. TASKGRAPH ENGINE
--------------------------------------------------
Status: EXISTS but NOT WIRED to chat
File: taskgraph/engine.py
Function: generate_graph()
Evidence: Hanya diakses via REST API /api/taskgraph/*
Problem: Task decomposition tidak otomatis
Impact: TaskGraph hanya jalan jika manual via API

--------------------------------------------------
7. DISPATCHER ENGINE
--------------------------------------------------
Status: EXISTS but NOT WIRED to chat
File: dispatcher/engine.py
Function: dispatch()
Evidence: Hanya diakses via REST API /api/dispatcher/*
Problem: Dispatch tidak otomatis (Runtime Executor sudah handle)
Impact: Dispatcher hanya jalan jika manual via API

--------------------------------------------------
8. VERIFICATION ENGINE
--------------------------------------------------
Status: EXISTS but NOT WIRED to chat
File: verification/engine.py
Function: verify()
Evidence: Hanya diakses via REST API /api/verification/*
Problem: Verification tidak otomatis setelah task selesai
Impact: Verification hanya jalan jika manual via API

--------------------------------------------------
9. DELIVERY ENGINE
--------------------------------------------------
Status: EXISTS but NOT WIRED to chat
File: delivery/engine.py
Function: generate_report()
Evidence: Hanya diakses via REST API /api/delivery/*
Problem: Delivery report tidak otomatis generate
Impact: Delivery hanya jalan jika manual via API

--------------------------------------------------
10. AUTONOMY ENGINE
--------------------------------------------------
Status: EXISTS but NOT WIRED to chat
File: autonomy/engine.py
Function: detect_anomaly(), recover(), heal()
Evidence: Hanya diakses via REST API /api/autonomy/*
Problem: Self-healing tidak otomatis
Impact: Autonomy hanya jalan jika manual via API

==================================================
CURRENT CHAT PATH
==================================================

User → ChatView → /chat/stream → Intent Detection → ConversationEngine

↓

If chat/question: ChatService.chat_stream() → LLM → Response

↓

If task_request: ConversationEngine._handle_task_request() → Clarification

↓

If task_confirm: ConversationEngine._handle_task_confirm() → Task Creation

↓

Background: _dispatch_created_task() → Runtime Executor → Workers

==================================================
WHAT'S MISSING
==================================================

1. Context Builder tidak dijalankan sebelum chat
   - Seharusnya: build_chat_context() dipanggil sebelum LLM call
   - Akibat: LLM tidak punya konteks dari memory/RAG

2. Memory Service tidak menyimpan otomatis
   - Seharusnya: Setiap conversation disimpan ke memory
   - Akibat: AI tidak ingat conversation sebelumnya

3. RAG Service tidak diakses otomatis
   - Seharusnya: Dokumen user diakses saat chat
   - Akibat: AI tidak bisa akses dokumen user

4. Discovery/Planning/TaskGraph tidak otomatis
   - Seharusnya: Otomatis dijalankan saat task_request
   - Akibat: Hanya jalan manual via API

5. Verification tidak otomatis
   - Seharusnya: Otomatis setelah task selesai
   - Akibat: Hanya jalan manual via API

6. Delivery tidak otomatis
   - Seharusnya: Otomatis generate report setelah task selesai
   - Akibat: Hanya jalan manual via API

==================================================
RECOMMENDATION
==================================================

Untuk membuat AIC-ADE fully functional, perlu wiring:

PRIORITY 1 (Critical):
- Context Builder → Dipanggil sebelum setiap chat
- Memory Service → Menyimpan dan mengambil memory otomatis

PRIORITY 2 (Important):
- RAG Service → Mengakses dokumen user otomatis
- Verification Engine → Verifikasi otomatis setelah task selesai

PRIORITY 3 (Nice to have):
- Discovery/Planning/TaskGraph → Otomatis untuk complex tasks
- Delivery → Otomatis generate report
- Autonomy → Otomatis detect dan recover dari error

==================================================
END OF INVESTIGATION
==================================================
