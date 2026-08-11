# AIC-ADE Architecture Diagrams

## System Topology

```mermaid
graph TB
    subgraph "Electron Desktop Client"
        UI[User Interface<br/>React + TypeScript]
        ElectronMain[Main Process<br/>Electron Native]
        Renderer[Renderer Process<br/>Vite Dev Server]
    end
    
    subgraph "FastAPI Backend"
        Routes[REST API Routes<br/>/api/v1/*]
        ChatService[ChatService<br/>Primary Handler]
        Provider[LLM Provider Abstraction]
        Delivery[Delivery Engine<br/>SSE Streamer]
    end
    
    subgraph "Worker Infrastructure"
        Dispatcher[Dispatcher Engine<br/>Task Router]
        WorkerPool[Worker Pool<br/>Process Isolation]
        RuntimeExecutor[Runtime Executor<br/>Sandbox Environment]
    end
    
    subgraph "Data Layer"
        SQLite[(SQLite Database<br/>Sessions, Tasks)]
        EventBus[(Event Bus<br/>Pub/Sub Messaging)]
        Cache[(In-Memory Cache<br/>Session Context)]
    end
    
    UI <-->|IPC contextBridge| ElectronMain
    ElectronMain <-->|HTTP REST + SSE| Routes
    Routes --> ChatService
    ChatService --> Provider
    ChatService --> Delivery
    Delivery -.->|WebSocket/SSE| UI
    Dispatcher --> WorkerPool
    WorkerPool --> RuntimeExecutor
    Routes <-->|Async tasks| Dispatcher
    SQLite <-->|ORM SQLAlchemy| ChatService
    SQLite <-->|ORM SQLAlchemy| Dispatcher
    EventBus <--> All
    Cache <--> ChatService
```

---

## Execution Flow: Chat Request

```mermaid
sequenceDiagram
    participant User
    participant Frontend as ChatView.tsx
    participant IPC as Electron IPC
    participant Backend as FastAPI Routes
    participant Service as ChatService
    participant LLM as LLM Provider
    participant Stream as Delivery Engine
    
    User->>Frontend: Type message, click send
    Frontend->>IPC: contextBridge.invoke('chat', 'execute', {prompt})
    IPC->>Backend: POST /api/v1/chat/execute
    Backend->>Service: execute_chat(prompt)
    Service->>LLM: get_completion(messages, model)
    LLM-->>Service: Streaming completion chunks
    Service->>Stream: stream_response()
    Stream-->>IPC: SSE event stream
    IPC-->>Frontend: Parse SSE data
    Frontend-->>User: Render tokens progressively
    Service->>SQLite: Save conversation state
```

---

## Execution Flow: Task/Mission (Current Status: Unwired)

**Intended Flow** (NOT currently active):

```mermaid
sequenceDiagram
    participant User
    participant MissionUI as MissionView.tsx
    participant Backend as FastAPI Routes
    participant Dispatcher as Dispatcher Engine
    participant Worker as Worker Process
    participant Executor as Runtime Executor
    participant EventBus as Event Bus
    participant WebSocket as Live Dashboard WS
    
    User->>MissionUI: Define mission parameters
    MissionUI->>Backend: POST /api/v1/missions/create
    Backend->>Dispatcher: schedule_task(definition)
    Dispatcher->>Worker: Assign to worker pool
    Worker->>Executor: Spawn sandboxed process
    Executor-->>Worker: Execute task steps
    Worker->>EventBus: Emit progress events
    EventBus->>WebSocket: Broadcast updates
    WebSocket-->>MissionUI: Real-time progress
    Worker-->>Backend: Return result JSON
    Backend-->>MissionUI: Display completion status
```

**Current Reality:** This flow is NOT executed. Tasks go through passthrough chat path instead.

---

## Data Flow: State Persistence

```mermaid
flowchart LR
    A[User Action] --> B{State Type}
    
    B -->|Chat Message| C[ConversationState]
    B -->|Task Progress| D[TaskState]
    B -->|Project Def| E[MissionState]
    B -->|Settings| F[ConfigSnapshot]
    
    C --> G[(SQLite DB)]
    D --> G
    E --> G
    F --> H[localStorage]
    
    G -.-> I[Restore on reload]
    H -.-> J[Sync with backend]
    
    style G fill:#f9f,stroke:#333
    style H fill:#ff9,stroke:#333
```

---

## Error Handling Flow

```mermaid
flowchart TD
    A[Request Start] --> B{Execution Phase}
    
    B -->|Auth Check| C{Valid JWT?}
    C -->|No| D[Return 401 Unauthorized]
    C -->|Yes| E[Call Service Layer]
    
    E --> F{LLM Call Success?}
    F -->|No| G[Retry with backoff]
    G --> H{Max attempts hit?}
    H -->|Yes| I[Fallback provider]
    H -->|No| E
    
    I --> J{Fallback available?}
    J -->|No| K[Return error to user]
    J -->|Yes| L[Use fallback model]
    
    L --> M{Success?}
    M -->|Yes| N[Return response]
    M -->|No| K
    
    E --> O{Streaming Active?}
    O -->|Yes| P[Yield chunks via SSE]
    O -->|No| Q[Buffer full response]
    
    P --> R{Client disconnect?}
    R -->|Yes| S[Close connection gracefully]
    R -->|No| T[Stream complete]
    
    Q --> U{Parse success?}
    U -->|No| V[Log error, retry]
    U -->|Yes| N
    
    style K fill:#f99,stroke:#f00
    style D fill:#f99,stroke:#f00
```

---

## Component Dependency Graph

```mermaid
graph LR
    subgraph "Frontend"
        AppShell --> ChatView
        AppShell --> MissionView
        AppShell --> LiveCompanyView
        AppShell --> SettingsView
        ChatView --> useChatHook
        useChatHook --> apiClient
    end
    
    subgraph "Backend Services"
        apiClient --> ChatService
        apiClient --> MissionService
        apiClient --> WorkerStatsService
        
        ChatService --> ProviderFactory
        ChatService --> DeliveryEngine
        
        ProviderFactory --> OpenAIProvider
        ProviderFactory --> AnthropicProvider
        ProviderFactory --> CustomAICProvider
        
        MissionService --> DispatcherFactory
        DispatcherFactory --> Engine
    end
    
    subgraph "Infrastructure"
        SQLite --> ChatService
        SQLite --> MissionService
        SQLite --> WorkerStateStore
        
        EventBus --> WorkerEvents
        EventBus --> ChatEvents
    end
    
    style ChatService fill:#9f9
    style ProviderFactory fill:#ccf
    style DeliveryEngine fill:#fc9
```

---

## Security Boundaries

```mermaid
flowchart TB
    A[Client Browser] --> B[Electron IPC Bridge]
    B --> C{Authentication Check}
    
    C -->|JWT Valid| D[Backend Route Handler]
    C -->|Invalid| E[Reject request 401]
    
    D --> F[CORS Validation]
    F --> G[Input Sanitization]
    G --> H[Rate Limiting Check]
    
    H -->|Pass| I[Route to Service Layer]
    H -->|Fail| J[Return 429 Too Many Requests]
    
    I --> K[LLM API Key Injection]
    K --> L[External LLM Provider]
    
    L -.-> M{Rate limit exceeded?}
    M -->|Yes| N[Backoff, return cached or partial]
    M -->|No| O[Return response]
    
    style C fill:#ff9,stroke:#f60
    style H fill:#ff9,stroke:#f60
    style K fill:#ff9,stroke:#f60
```

**Security Layers:**
1. **JWT Validation** — At IPC bridge level
2. **CORS Enforcement** — Only allow trusted origins
3. **Input Sanitization** — Prevent injection attacks
4. **Rate Limiting** — Prevent abuse (per-user/IP)
5. **API Key Management** — Encrypted storage for LLM keys

---

## Scalability Points

```mermaid
flowchart LR
    A[Single Backend Instance] --> B{Load Increase}
    
    B -->|Horizontal Scale| C[Add Backend Instances]
    C --> D[Load Balancer]
    D --> E[Session Store Redis]
    E --> F[Shared SQLite read-only mirror]
    
    B -->|Worker Growth| G[Increase Worker Pool Size]
    G --> H[Docker containerization]
    H --> I[Kubernetes orchestration]
    
    B -->|Storage Pressure| J[Partition SQLite by session age]
    J --> K[Archive old sessions to cold storage]
    
    style C fill:#ccf,stroke:#339
    style G fill:#ccf,stroke:#339
    style J fill:#ccf,stroke:#339
```

**Current State:** Single-instance deployment  
**Planned Improvements:** Horizontal scaling, Redis cache, Docker/K8s orchestration

---

*Architecture diagrams extracted from:* code inspection, runtime logs, component tree analysis  
*Date: 2026-08-11 11:29 WIB*
