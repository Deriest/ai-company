# AIC-ADE User Interface Navigation Map

## Sidebar Navigation Structure

### Primary Navigation Items (Core Product)

| Item ID | Label | Component | Route | Purpose | Frequency | Target User |
|---------|-------|-----------|-------|---------|-----------|-------------|
| `home` | Workspace | HomeView | `/` | Dashboard & recent activity | Constant | All users |
| `hermes` | Chat | ChatView | `/chat` | Multi-turn conversations | Daily power users | Developers, analysts |
| `mission` | Projects | MissionView | `/missions` | Task/project management | Multiple times/week | Project leads |
| `live` | Live Company | LiveCompanyView | `/live` | Real-time worker monitoring | Continuous ops team | DevOps, SRE |
| `settings` | Settings | SettingsView | `/settings` | App configuration | Infrequent | Admins |

**Total Core Items:** 5

---

## Secondary Navigation (Power User Features)

### Integrated into Settings Tabs

| Tab Name | View Component | Purpose | Backend Feature | Classification |
|----------|----------------|---------|-----------------|----------------|
| **Providers** | ProvidersView | Manage AI model providers | `data/providers.json` | Configuration |
| **Memory** | MemoryView | Persistent memory settings | Memory Service | Advanced |
| **RAG Docs** | RAGDocsView | Knowledge base documents | RAG Service | Advanced |
| **Audit Logs** | AuditLogsView | System event history | Event Bus logs | Operator |
| **Backup** | BackupView | Export/import config | Backup service | Operator |
| **Advanced** | AdvancedSettingsView | Dev tools, experimental flags | Feature toggles | Developer |

**Note:** These tabs moved out of sidebar to keep core navigation focused.

---

## UI Element Inventory (Manual Audit)

### Desktop App Screens

#### 1. Home / Workspace (`/`)

**Visible Elements:**
- Recent chats list (last 10 sessions)
- Quick action buttons: New Chat, New Project
- System status widget (backend health)
- Worker pool utilization indicator
- Notification badge for pending tasks

**Classification:** Category A - Core Product  
**Justification:** Primary entry point, essential for daily work

---

#### 2. Chat Interface (`/chat`)

**Visible Elements:**
- Message list with timestamps
- Text input field + send button
- Model selector dropdown
- Conversation controls: Clear, Export, Archive
- Streaming indicator (typing animation)
- Error state banner (if failure occurs)

**Classification:** Category A - Core Product  
**Justification:** Main interaction surface, no UX can function without it

---

#### 3. Mission Management (`/missions`)

**Visible Elements:**
- Project list view (table/grid)
- Create mission dialog
- Task assignment table
- Progress bars per project
- Status filter dropdown (Active/Draft/Archived)
- Bulk actions toolbar

**Classification:** Category B - Power User  
**Justification:** Important but not all users need complex project tracking

---

#### 4. Live Company (`/live`)

**Visible Elements:**
- Worker pool dashboard (cards)
- Real-time metrics (CPU, memory, latency)
- Log stream panel (collapsible)
- Timeline view (Gantt-style task flow)
- Evidence viewer (artifacts from tasks)
- Metrics comparison chart

**Classification:** Category C - Operator  
**Justification:** Ops team only, not needed by regular end users

---

#### 5. Settings (`/settings`)

**Tabs:**
- General (app name, theme, default model)
- Providers (API keys, endpoints)
- Memory (context retention settings)
- RAG Docs (knowledge base upload)
- Audit Logs (filter/search events)
- Backup (export/import JSON)
- Advanced (debug mode, feature flags)

**Classification:** Mixed
- General → Category A (essential defaults)
- Providers → Category B (configuration, used occasionally)
- Memory/RAG → Category B (advanced features)
- Audit Logs → Category C (monitoring)
- Backup → Category C (admin only)
- Advanced → Category D (Developer/Internal)

---

### Dialogs & Modals

| Dialog | Trigger | Purpose | Classification | Should Be Visible? |
|--------|---------|---------|----------------|--------------------|
| New Chat Modal | "New Chat" button | Start conversation | Category A | Yes |
| New Mission Dialog | "Create Project" | Define task parameters | Category B | Yes |
| Provider Config Modal | "Add Provider" tab | Set up API key | Category B | Yes (as tab) |
| RAG Upload Dialog | "Upload Documents" | Add knowledge base | Category B | Yes (as tab) |
| Export Data Modal | Settings > Backup | Download all data | Category C | Yes (hidden from normal UI?) |
| Debug Console | Settings > Advanced | Inspect runtime state | Category D | No (hide from non-devs) |
| Performance Profiler | Settings > Advanced | Measure response times | Category D | No (developer tool) |

---

### Context Menus & Right-Click Actions

| Menu Target | Available Actions | Classification |
|-------------|-------------------|----------------|
| Chat message | Copy, Edit, Delete, Regenerate | Category A |
| Project card | Clone, Archive, Share, Duplicate | Category B |
| Worker card | Restart, Kill, View Logs | Category C |
| Settings item | Reset to default | Category D |

---

### Toolbar & Floating Controls

| Location | Control | Purpose | Classification |
|----------|---------|---------|----------------|
| Chat header | Model selector | Switch LLM provider | Category A |
| Chat header | Export button | Download conversation | Category B |
| Live Company toolbar | Filter dropdown | By worker type/status | Category C |
| Mission list | Search bar | Find projects | Category B |
| Settings header | Save button | Apply changes | Category A |

---

## Navigation Hierarchy Recommendations

### Ideal Sidebar (Post-Cleanup)

```
├── 📊 Workspace (Home)          ← Default landing page
├── 💬 Chat                       ← Primary interaction
├── 📁 Projects                   ← Task management
├── 🏢 Live Company               ← Ops monitoring (optional hide)
└── ⚙️ Settings                   ← Configuration hub
    ├── General
    ├── Providers
    ├── Memory
    ├── RAG Docs
    └── Audit & Backup
```

**Removed from Sidebar:**
- ~~Observability~~ → Moved to Settings > Audit Logs
- ~~MCP Servers~~ → Would move to Settings if implemented
- ~~Worker Pools~~ → Part of Live Company or hidden (operator-only)
- ~~Task Graph~~ → Experimental, show in Settings > Advanced
- ~~Autonomy Engine~~ → Roadmap feature, hide until ready

---

## Hidden/Internal UI (Category D - Should Not Appear)

These exist in codebase but should never be exposed to normal users:

1. **Database Browser** — Admin tool for direct DB inspection (internal dev use only)
2. **Event Inspector** — Raw event bus viewer (debugging only)
3. **Lease Scanner Debugger** — Heartbeat mechanism troubleshooting (ops only)
4. **Migration Runner** — Manual migration trigger (dev deployment process)
5. **Feature Flag Toggle Panel** — A/B test control (not for production UI)

**Action:** Mark as internal, add auth guard requiring admin role, or completely remove.

---

*UI audit via:* component inspection (`app/src/renderer/src/components/`), route analysis (`App.tsx`), user session observation  
*Date: 2026-08-11 11:28 WIB*
