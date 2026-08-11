# AIC-ADE Feature Purpose Investigation

## Methodology

Setiap fitur dievaluasi dengan 15 pertanyaan:
1. Why does this feature exist?
2. What business problem does it solve?
3. Who uses it? (End User / Power User / Operator / Developer)
4. What backend components use it?
5. Is it manually or automatically invoked?
6. Can the product function normally if users never open this page?
7. Classification: Core / Power / Operator / Developer Tool / Internal
8. Does it expose implementation details?
9. Does it duplicate another feature?
10. Could same capability exist without dedicated page?
11. Is current UI actually useful?
12. Would hiding change product capability?
13. Would removing only UI still preserve backend functionality?
14. Does ConversationEngine already use this automatically?
15. Does user need to understand this concept?

---

## Feature 1: RAG Docs Upload

### Evaluation

| Question | Answer |
|----------|--------|
| Why exist? | Enable AI to answer based on custom knowledge base |
| Business problem | Users want context-specific answers (internal docs, manuals) |
| Target user | Power users, knowledge workers |
| Backend component | RAG Service + Context Builder |
| Invocation | Manual upload → automatic retrieval during chat |
| Required for normal function? | No — basic chat works without it |
| Classification | Category B - Power User |
| Exposes implementation detail? | Partially — "RAG" is technical term, should rename to "Knowledge Base" |
| Duplicate feature? | No |
| Could exist without dedicated page? | Yes — could be dialog/modal in ChatView |
| Current UI useful? | Yes — needs file list, upload status, relevance scoring |
| Would hiding reduce capability? | No — backend RAG service still functional via API |
| Would removing UI preserve backend? | YES |
| ConversationEngine uses auto? | NOT CURRENTLY WIRED — but should detect relevance automatically |
| User needs to understand concept? | NO — just wants AI to know stuff; don't need user to configure RAG |

### Recommendation

**REMOVE dedicated RAG Docs page.**  
Move to Settings > Knowledge (as configuration area, not sidebar). Better UX: user uploads docs once, AI automatically applies them per-project (no manual trigger needed).

**Evidence:** Backend RAG service exists but not wired to primary path. Users shouldn't need to manually "enable" knowledge retrieval.

---

## Feature 2: MCP Servers Configuration

*Note: If implemented, evaluate separately.*

### Classification Criteria

| Aspect | Determination |
|--------|---------------|
| Why exist? | Connect external tools/APIs to AI system |
| Business problem | Extend AI capabilities beyond basic chat |
| Target user | Developers, power users with custom integrations |
| Backend component | MCP Client/Service layer |
| Invocation | Manual setup → automatic during relevant tasks |
| Required? | No — core features work without extensions |
| Classification | Category C - Configuration (if exposed) |
| Should be in sidebar? | NO — settings area only |
| Remove from UI? | Keep as Settings > Integrations tab |

**Conclusion:** Configuration-only feature, no sidebar visibility. Move to Settings.

---

## Feature 3: Memory Management

### Evaluation

| Question | Answer |
|----------|--------|
| Why exist? | Persist conversation context across sessions |
| Business problem | User doesn't want to repeat information every chat |
| Target user | All users (auto-enabled by default) |
| Backend component | Memory Service + Context Builder |
| Invocation | Automatic per-conversation |
| Required for normal function? | No — stateless chat still works |
| Classification | Category B - Advanced Configuration |
| Exposes implementation detail? | YES — "Memory" is internal concept |
| Duplicate feature? | No |
| Could exist without dedicated page? | YES — user shouldn't see memory management at all |
| Current UI useful? | Maybe — allow toggle "save conversation history" |
| Would hiding reduce capability? | NO — Memory Service can run transparently |
| Would removing UI preserve backend? | YES |
| ConversationEngine uses auto? | YES — should be automatic background process |
| User needs to understand? | NO — just want AI remember things |

### Recommendation

**REMOVE dedicated Memory page.**  
Make memory behavior configurable via:
- `Settings > General` → Checkbox "Remember conversations"
- OR fully automatic (default ON), no config needed

Backend Memory Service must run silently — users don't care about "memory management."

---

## Feature 4: Audit Logs Viewer

### Evaluation

| Question | Answer |
|----------|--------|
| Why exist? | Track system events, debug failures, compliance |
| Business problem | Admins need to investigate errors, track changes |
| Target user | Operators, DevOps, admins |
| Backend component | Event Bus + EventLogger |
| Invocation | Manual query/search |
| Required for normal function? | NO — operational only |
| Classification | Category C - Operator |
| Exposes implementation detail? | YES — logs are internal system data |
| Duplicate feature? | No |
| Could exist without dedicated page? | YES — export logs to file instead of live viewer |
| Current UI useful? | Limited — log format hard to read, needs filtering/pagination |
| Would hiding reduce capability? | NO — logs still stored, just not easily accessible |
| Would removing UI preserve backend? | YES |
| ConversationEngine uses auto? | YES — event logging happens anyway |
| User needs to understand? | NO — ops team may need access, but not normal users |

### Recommendation

**MOVE from sidebar to Settings > Audit Logs** (as admin-only feature). Add auth guard requiring admin role to view. Export logs to CSV for offline analysis instead of live dashboard.

---

## Feature 5: Observability Dashboard

*Placeholder evaluation if implemented.*

### Anticipated Classification

Based on typical observability patterns:

- **Purpose:** Monitor performance, latency, error rates
- **Target user:** SRE, DevOps, operators
- **Classification:** Category C - Operator
- **Sidebar?** NO — move to Settings > Monitoring or external Grafana/Prometheus
- **User understands concepts?** NO — metrics are internal health signals

**Recommendation:** Hide from normal UI, provide webhook alerts for critical failures instead of live dashboard.

---

## Feature 6: Worker Pool Management

### Evaluation

| Question | Answer |
|----------|--------|
| Why exist? | Control how many parallel workers execute tasks |
| Business problem | Resource optimization, prevent overload |
| Target user | DevOps, ops team managing infrastructure |
| Backend component | WorkerPool + LeaseScanner |
| Invocation | Manual scaling or automatic based on load |
| Required for normal function? | NO — default pool size works for most cases |
| Classification | Category C - Operator |
| Exposes implementation detail? | YES — worker pools are internal architecture |
| Duplicate feature? | No |
| Could exist without dedicated page? | YES — auto-scaling should handle everything |
| Current UI useful? | Low value — ops prefer CLI or monitoring tools |
| Would hiding reduce capability? | NO — static pool or auto-scaling sufficient |
| Would removing UI preserve backend? | YES |
| ConversationEngine uses auto? | YES — worker assignment hidden from user |
| User needs to understand? | NO — user cares about task completion, not how many workers |

### Recommendation

**REMOVE from Live Company view.** Only show aggregate metrics ("X active workers") without control panel. Scaling decisions left to auto-scaler or ops CLI.

---

## Feature 7: Task Graph Visualization

### Evaluation

| Question | Answer |
|----------|--------|
| Why exist? | Visualize complex multi-step task dependencies |
| Business problem | Understand execution flow, debug failures |
| Target user | Developers, power users debugging workflows |
| Backend component | TaskGraph engine |
| Invocation | Manual inspection after task runs |
| Required for normal function? | NO — tasks run fine without visualization |
| Classification | Category D - Developer Tool |
| Exposes implementation detail? | YES — internal DAG structure |
| Duplicate feature? | May overlap with Mission view progress tracking |
| Could exist without dedicated page? | YES — export graph as DOT/PNG file |
| Current UI useful? | Niche value — only for deep debugging |
| Would hiding reduce capability? | NO |
| Would removing UI preserve backend? | YES |
| ConversationEngine uses auto? | YES — task graphs executed internally |
| User needs to understand? | NO — just want task done, don't need to see pipeline |

### Recommendation

**REMOVE from main navigation.** Move to Settings > Advanced as experimental feature (feature flag required). Default OFF.

---

## Feature 8: Autonomy Engine Controls

### Evaluation

| Question | Answer |
|----------|--------|
| Why exist? | Allow AI to make autonomous decisions without explicit prompts |
| Business problem | Reduce user intervention for repetitive tasks |
| Target user | Power users, advanced automation scenarios |
| Backend component | AutonomyEngine decision loop |
| Invocation | Configure policy → AI applies automatically |
| Required for normal function? | NO — safety-first default is human-in-loop |
| Classification | Category B - Advanced Feature (if complete) |
| Exposes implementation detail? | Partially — "autonomy level" is conceptual |
| Duplicate feature? | No |
| Could exist without dedicated page? | YES — policy selection as dropdown in mission creation |
| Current UI useful? | Depends on maturity — experimental feature might confuse users |
| Would hiding reduce capability? | Potentially — if autonomy is core differentiator |
| Would removing UI preserve backend? | YES (but removes UX surface) |
| ConversationEngine uses auto? | YES — autonomy decisions happen internally |
| User needs to understand? | Partially — need to trust AI won't do bad things |

### Recommendation

**DO NOT add dedicated page yet.** Start with simple checkbox in mission creation: "Allow AI to make autonomous decisions?" Toggle OFF by default (safe). Add autonomy dashboard ONLY when mature enough to explain what AI decided and why.

---

## Feature 9: Backup & Restore

### Evaluation

| Question | Answer |
|----------|--------|
| Why exist? | Export/import app configuration and session data |
| Business problem | Disaster recovery, migration between devices |
| Target user | Admins, power users managing multiple instances |
| Backend component | BackupService (serializes JSON configs) |
| Invocation | Manual export, manual import |
| Required for normal function? | NO — operational necessity only |
| Classification | Category C - Operator |
| Exposes implementation detail? | NO — backup is standard practice |
| Duplicate feature? | No |
| Could exist without dedicated page? | YES — CLI command `aic-backup export` |
| Current UI useful? | Moderate — GUI makes it easier than CLI for non-devs |
| Would hiding reduce capability? | NO — backend backup still works |
| Would removing UI preserve backend? | YES |
| ConversationEngine uses auto? | NO — separate concern |
| User needs to understand? | Partially — understand what's backed up |

### Recommendation

**KEEP but move to Settings > Backup & Restore** (not sidebar). Consider adding auto-backup schedule (daily/weekly) with email notification instead of manual triggers only.

---

## Feature 10: Advanced Settings Panel

### Evaluation

| Question | Answer |
|----------|--------|
| Why exist? | Expose debug features, experimental flags, developer tools |
| Business problem | Allow testing/config tuning without code changes |
| Target user | Developers, QA, power users troubleshooting |
| Backend component | FeatureFlagRegistry |
| Invocation | Manual toggle each setting |
| Required for normal function? | NO — production defaults are stable |
| Classification | Category D - Developer/Internal |
| Exposes implementation detail? | YES — full tech stack details |
| Duplicate feature? | No (consolidates dev tools) |
| Could exist without dedicated page? | YES — environment variables override config |
| Current UI useful? | High for devs, zero for normal users |
| Would hiding reduce capability? | NO — but makes debugging harder |
| Would removing UI preserve backend? | YES |
| ConversationEngine uses auto? | NO — separate concern |
| User needs to understand? | NO — only relevant when troubleshooting |

### Recommendation

**REMOVE from normal UI.** Require admin password or role-based access. Better approach: hide behind `/debug` route prefix, require authentication token or IP whitelist.

---

## Summary Table

| Feature | Current Location | Recommended Action | Final Location | Priority |
|---------|------------------|-------------------|----------------|----------|
| RAG Docs | Sidebar? | Remove dedicated page | Settings > Knowledge | HIGH |
| Memory | Sidebar? | Remove dedicated page | Settings > General (toggle) | HIGH |
| Audit Logs | Settings tab | Keep but restrict access | Settings > Audit (admin-only) | MEDIUM |
| Observability | Not yet implemented | Skip for now | External monitoring tool | LOW |
| Worker Pool | Live Company | Remove controls, keep metrics | Live Company (read-only only) | HIGH |
| Task Graph | Sidebar? | Remove | Settings > Advanced (feature-flagged) | LOW |
| Autonomy | Not yet implemented | Delay until mature | Mission creation checkbox | MEDIUM |
| Backup | Settings | Keep but improve UX | Settings > Backup & Restore | MEDIUM |
| Advanced Settings | Settings | Restrict access | Hidden (admin-only URL) | HIGH |

---

*Feature audit via:* source code inspection, runtime logs, user experience evaluation  
*Date: 2026-08-11 11:30 WIB*
