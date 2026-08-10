# Context & Knowledge Intelligence Module

**Module**: `backend/context/`  
**Version**: 2.3.7  
**Purpose**: Persistent engineering memory and context assembly for LLM-driven code generation

---

## 1. Responsibility

This directory implements a **Context & Knowledge Intelligence subsystem** that provides persistent engineering memory and structured context assembly to all backend engines in the AIC Platform. The module serves as the central hub for:

- **Knowledge Management**: Storing and retrieving project-specific knowledge entries across domains (repository structure, architecture patterns, coding conventions, business rules)
- **Context Assembly**: Orchestrating multi-source context retrieval with token budget management
- **Memory Persistence**: Maintaining conversation history, decision records, and workspace state
- **RAG Integration**: Providing document retrieval capabilities via Retrieval-Augmented Generation patterns
- **Context Compression**: Intelligent text compression and summarization for long-context optimization

The module follows the **Repository Pattern** for data access abstraction and employs **Dependency Injection** for database session management, enabling testability and runtime configurability.

---

## 2. Design Patterns

### 2.1 Strategy Pattern
Implemented via the abstract base class `ContextSource` in `sources.py`, defining a unified interface for heterogeneous context sources:
- `ConversationSource`: Message history retrieval
- `RAGSource`: Document-based retrieval via RAG service
- `KnowledgeSource`: Project knowledge base queries
- `MemorySource`: Multi-scope memory entry retrieval
- `WorkspaceSource`: File system context reading
- `CodeContextSource`: Source file content indexing
- `ToolHistorySource`: Recent tool execution context

Concrete strategies implement `retrieve(query, max_tokens)` allowing interchangeable source composition within the pipeline.

### 2.2 Pipeline Pattern
`ContextPipeline` class in `pipeline.py` orchestrates sequential processing:
1. Source availability checking (`is_available()`)
2. Concurrent source querying (`retrieve()`)
3. Result merging and token budget enforcement
4. Relevance-based sorting
5. Budget-compliant trimming
6. Optional caching and persistence

The pipeline uses a **TokenBudget** mechanism to allocate tokens across sources proportionally to priority.

### 2.3 Factory Method Pattern
- `create_default_sources()`: Instantiates standard source set sorted by priority
- `create_default_pipeline()`: Constructs fully configured pipeline with cache wiring
- `create_builder()`: Assembles builder instance from pipeline and config

### 2.4 Singleton Pattern
Global instances provided via accessor functions:
- `get_context_cache()`: TTL/LRU context cache (configured default: 100 entries, 300s TTL)
- `get_context_emitter()`: Event emission infrastructure
- `context_engine`: Context engine singleton (though instantiated per-engine)

### 2.5 Caching Pattern (TTL + LRU Hybrid)
`ContextCache` class implements hybrid eviction strategy:
- TTL expiration based on creation timestamp
- LRU selection using hit count as proxy for recency
- Conversation-scoped invalidation for cleanup
- MD5-based key derivation from query parameters

### 2.6 Builder Pattern
`ContextBuilder` class constructs formatted context output with configurable:
- Source inclusion filters
- Format styles (structured, raw, compact)
- Deduplication rules
- Token budget override

### 2.7 Composite Pattern
`ContextAssembly` aggregates multiple `ContextChunk` objects into unified context unit with metadata tracking (sources used, token usage, timing metrics).

### 2.8 Data Mapper Pattern
ORM layer abstracted through SQLAlchemy async sessions in `engine.py`, mapping between Python dataclasses (`KnowledgeEntry`, `DecisionRecord`, `ProjectContext`) and database tables (`knowledge_entries`, `decision_records`).

---

## 3. Data & Control Flow

### 3.1 Input Pathways

| Entry Point | Description | Parameter Types |
|-------------|-------------|-----------------|
| `pipeline.assemble(query, max_tokens, **kwargs)` | Primary context assembly API | `query: str`, `max_tokens: int` |
| `builder.build(query, max_tokens, **kwargs)` | High-level context building | Same as above + format config |
| `sources.retrieve(query, max_tokens, **kwargs)` | Individual source queries | Varies by source implementation |
| `config.ContextConfig.from_env()` | Runtime configuration load | Environment variables |

### 3.2 Internal Processing Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Client Code   │────▶│   ContextBuilder │────▶│   ContextPipeline │
│ (Engine/Agent)  │     └──────────────────┘     └─────────────────┘
│                 │                                  │ assemble()    │
│                 │                                  ▼               │
│                 │                          ┌──────────────────┐    │
│                 │                          │ Source Orchestrator│   │
│                 │                          └──────────────────┘    │
│                 │                                 │                │
│                 │                                 ▼                │
│                 │                    ┌────────────────────┐        │
│                 │                    │ ContextSources     │        │
│                 │                    │ - Conversation    │        │
│                 │                    │ - RAG             │        │
│                 │                    │ - Knowledge       │        │
│                 │                    │ - Memory          │        │
│                 │                    │ - Workspace       │        │
│                 │                    └────────────────────┘        │
│                 │                                 │                │
│                 │                                 ▼                │
│                 │                          ┌──────────────────┐    │
│                 │                          │ ContextCache     │    │
│                 │                          │ (TTL/LRU)        │    │
│                 │                          └──────────────────┘    │
│                 │                                    │             │
│                 │                                    ▼             │
│                 │                          ┌──────────────────┐    │
│                 │                          │ ContextAssembly  │    │
│                 │                          │ (merged chunks)  │    │
│                 │                          └──────────────────┘    │
│                 │                                    │             │
│                 │                                    ▼             │
│                 │                          ┌──────────────────┐    │
│                 │                          │ compress/format  │    │
│                 │                          └──────────────────┘    │
└─────────────────┘                                              ▼
                                                                   │
                                                                   ▼
                                                          ┌──────────────────┐
                                                          │   Engine         │
                                                          │   receives ctx   │
                                                          └──────────────────┘
```

### 3.3 Output Pathways

| Output Destination | Format | Usage |
|-------------------|--------|-------|
| LLM Prompt | String via `to_prompt_context()` | Agent reasoning |
| Database Records | `ContextAssemblyRecord` ORM model | Audit trail, replay |
| Event Bus | Async events via `ContextEventEmitter` | Observability |
| Cache Storage | `CacheEntry` with TTL | Repeat query optimization |

### 3.4 Data Models

**Core Entities**:

- `KnowledgeEntry`: Domain-tagged knowledge (`id`, `domain`, `key`, `value`, `confidence`)
- `DecisionRecord`: Architectural decisions with rationale (`decision`, `rationale`, `outcome`)
- `ProjectContext`: Aggregated context delivered to engines (`knowledge_entries`, `past_decisions`, `freshness_score`)
- `ContextChunk`: Atomic context unit (`source`, `content`, `relevance`, `token_count`)
- `ContextAssembly`: Merged result of pipeline (`chunks`, `sources_used`, `total_tokens`, `metadata`)

**Configuration**:

- `ContextConfig`: Feature flags and thresholds (`enabled`, `max_knowledge_entries`, `context_freshness_minutes`, `enable_learning`)
- `BuildConfig`: Builder behavior (`include_sources`, `format_style`, `deduplicate`)

### 3.5 Token Budget Mechanism

The module implements a hierarchical token allocation strategy:

1. **Global budget**: Default 4000 tokens, configurable per request
2. **Priority ordering**: Sources sorted by `priority` attribute (lower = higher precedence)
3. **Sequential allocation**: Iterate sources, stop when budget exhausted
4. **Relevance filtering**: Post-retrieval sort by chunk relevance score
5. **Trimming**: Final budget compliance check before return

Budget tracking via `TokenBudget` class provides per-source allocation reporting.

---

## 4. Integration Points

### 4.1 External Dependencies

| Dependency | Module | Purpose |
|------------|--------|---------|
| `storage.models` | `storage/` | ORM models for persistence (`ContextAssemblyRecord`, `Message`, `KnowledgeEntry`, `DecisionRecord`) |
| `backend.services.rag_service` | `services/` | RAG document retrieval (`RAGService.build_context()`) |
| `backend.services.memory_service` | `services/` | Memory entry retrieval (`MemoryService.retrieve()`) |
| `backend.services.content_utils` | `services/` | Content parsing (`content_to_text()`) |
| `sqlalchemy.ext.asyncio` | External | Async database session management |
| `uuid` | Standard Lib | ID generation |
| `dataclasses` | Standard Lib | Type-safe data structures |

### 4.2 Consumer Modules

| Module | Integration Method | Use Case |
|--------|-------------------|----------|
| Agents | `create_builder()` → `build()` | LLM prompt context assembly |
| Engines | `ContextEngine.get_context()` | Engineering memory injection |
| Workflows | `ContextPipeline.persist()` | Execution audit logging |
| API Routes | `ContextEventEmitter.emit_*()` | Observability event publishing |

### 4.3 Event Bus Contract

The module publishes events to external event bus:

- `context.assembled`: Context completion (`assembly_id`, `sources_used`, `total_tokens`, `assembly_time_ms`)
- `context.cached`: Cache access (`query`, `cache_hit`)
- `context.compressed`: Compression metrics (`original_tokens`, `compressed_tokens`, `compression_ratio`, `strategy`)
- `context.source.query`: Per-source query info (`source`, `query`, `chunks_found`, `tokens`, `query_time_ms`)

Events are published asynchronously; failure is logged but does not block primary flow.

### 4.4 Environment Configuration

Runtime behavior controlled via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `AIC_CONTEXT_ENABLED` | `true` | Enable/disable module |
| `AIC_CONTEXT_MAX_ENTRIES` | `10000` | Max knowledge entries |
| `AIC_CONTEXT_FRESHNESS_MINUTES` | `5` | Context TTL window |
| `AIC_CONTEXT_LEARNING_ENABLED` | `true` | Enable adaptive learning |

---

## 5. Implementation Artifacts

### 5.1 File Inventory

| File | Lines | Primary Role |
|------|-------|--------------|
| `__init__.py` | 15 | Public API exports |
| `config.py` | 43 | Configuration management |
| `models.py` | 73 | Dataclass entities |
| `pipeline.py` | 284 | Context orchestration |
| `sources.py` | 565 | Source adapters |
| `cache.py` | 186 | TTL/LRU caching |
| `engine.py` | 218 | Knowledge CRUD operations |
| `builder.py` | 178 | Formatting & composition |
| `compressor.py` | 179 | Text compression utilities |
| `tokens.py` | 175 | Token counting & budgeting |
| `events.py` | 137 | Event emission |
| `migration.py` | 52 | Database schema initialization |

### 5.2 Performance Optimizations

- **Cache warming**: `pipeline.assemble()` checks cache before source queries when `conversation_id` present
- **Deep copy semantics**: `ContextAssembly.copy()` prevents caller mutation of cached results
- **Early exit**: Source iteration terminates immediately on budget exhaustion
- **Connection pooling**: Async SQLAlchemy sessions enable concurrent source queries

### 5.3 Concurrency Model

All data access methods are `async def` decorated, leveraging `AsyncSession` for non-blocking I/O. Source retrieval operates sequentially (sorted by priority), but future expansion could parallelize independent sources with coordination at merge phase.

---

## 6. Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.3.7 | Current | Global TTL/LRU cache integration, deep-copy semantics |
| 2.x | Previous | Initial context assembly architecture |
