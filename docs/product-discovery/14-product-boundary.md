# AIC-ADE Product Boundary Review

## Final Boundary Between Product Features, Advanced Configuration, and Internal System

### Review Purpose

Determine where to draw the line between:
- **Product Features** — visible in main navigation, used by end users regularly
- **Advanced Configuration** — settings area, optional but useful for power users
- **Internal System** — implementation details, should NEVER appear in normal UI

Thinking as VP of Product (not software engineer): "Would a new customer naturally expect this feature?"

---

## Decision Criteria (10 Questions Per Feature)

For EACH feature, answer:

1. What user goal does this support? (Not backend purpose)
2. Would a new customer naturally expect this feature?
3. How frequently would users interact with it?
4. Does this belong in user's mental model or only system's?
5. Does exposing this increase or decrease usability?
6. Should users actively control it or should AI manage automatically?
7. If hidden, would product become worse?
8. If removed from UI, would backend still deliver same value?
9. Should this be: Primary Sidebar / Secondary Navigation / Settings / Advanced Settings / Developer Mode / Hidden / Automatic / No UI?
10. Where would commercial competitors (ChatGPT, Claude, Cursor) place it?

---

## Feature Reviews

### 1. Chat Interface

| Question | Answer | Reasoning |
|----------|--------|-----------|
| User goal | Natural conversation with AI assistant | Core use case |
| New customer expects? | YES ✅ | Standard AI chat interface |
| Interaction frequency | Multiple times per session | Primary interaction surface |
| Mental model owner | USER | "I talk to AI" is natural |
| Expose increases usability? | NO — hiding makes product useless | Essential feature |
| User controls OR auto-manage? | User types, AI responds | Natural dialogue pattern |
| Hiding reduces capability? | YES — product ceases to work | Critical function |
| Backend delivers value without UI? | NO — need user input channel | Chat UI = primary interface |
| Placement recommendation | Primary Sidebar #1 | Standard pattern |
| Competitor placement | All AI products have this | Universal UX expectation |

**Verdict:** KEEP in sidebar — Category A - Core Product  
**Reason:** Without chat interface, product has zero value proposition

---

### 2. Workspace Dashboard

| Question | Answer | Reasoning |
|----------|--------|-----------|
| User goal | Quick overview of recent activity & pending tasks | Reduce friction finding work |
| New customer expects? | YES ✅ | Most apps show dashboard on login |
| Interaction frequency | Daily (first screen when app opens) | Habit-forming entry point |
| Mental model owner | USER | "Dashboard" is common pattern |
| Expose increases usability? | YES — shows context at glance | Reduces navigation effort |
| User controls OR auto-manage? | Semi-auto (AI suggests next actions) | Passive monitoring + proactive help |
| Hiding reduces capability? | Slightly — more clicks to find things | UX degradation, not functionality loss |
| Backend delivers value without UI? | YES — data exists regardless | Dashboard = presentation layer |
| Placement recommendation | Primary Sidebar #1 (Home/Workspace) | Standard landing page |
| Competitor placement | Slack, Notion, VS Code all have workspace | Industry standard |

**Verdict:** KEEP as default landing page — Category A - Core Product  
**Reason:** Modern UX expectation, reduces cognitive load for task switching

---

### 3. Projects/Missions Management

| Question | Answer | Reasoning |
|----------|--------|-----------|
| User goal | Organize multiple related tasks into cohesive workflows | Team collaboration, complex projects |
| New customer expects? | MAYBE ⚠️ (depends on target market) | Individuals less interested, teams need it |
| Interaction frequency | Weekly to daily (for project managers) | Power user territory |
| Mental model owner | BOTH | Users understand "project", system tracks progress |
| Expose increases usability? | YES — better than managing via ad-hoc notes | Structured workflow advantage |
| User controls OR auto-manage? | User creates projects, AI fills in details | Hybrid approach |
| Hiding reduces capability? | YES — loose organization becomes chaos | Losing structured management |
| Backend delivers value without UI? | PARTIALLY — can create tasks individually | Missing grouping capability in UI |
| Placement recommendation | Primary Sidebar #2 | Or secondary if targeting individuals |
| Competitor placement | ClickUp, Asana, Notion have project view | Enterprise expectation |

**Verdict:** KEEP in sidebar — Category B - Power User (or Category A if team-focused)  
**Reason:** Important for complexity management, especially for enterprise users

**Nuance:** If targeting individual developers → downgrade to Settings > Projects. If targeting teams → keep prominent in sidebar.

---

### 4. Live Company Dashboard

| Question | Answer | Reasoning |
|----------|--------|-----------|
| User goal | Monitor worker pool health, task execution status | DevOps oversight |
| New customer expects? | NO ❌ | End users don't care about infrastructure |
| Interaction frequency | Continuous for ops team, zero for normal users | Specialized audience only |
| Mental model owner | SYSTEM | Workers are internal processes |
| Expose increases usability? | DECREASES — confuses non-ops users | Shows unnecessary technical detail |
| User controls OR auto-manage? | Auto-manage (should never touch workers) | Scaling decisions belong to ops team |
| Hiding reduces capability? | NO — product works perfectly fine | Metrics already logged internally |
| Backend delivers value without UI? | YES — metrics stored, alerts can trigger elsewhere | UI exposes internal state unnecessarily |
| Placement recommendation | Hidden from normal users | Admin-only access via separate portal |
| Competitor placement | NOT in main app — external monitoring tools | Datadog, Grafana handle observability |

**Verdict:** REMOVE from main UI — Category D - Internal System  
**Action:** Create separate admin portal (`admin.aicompany.biz`) with auth-gated access. Main app shows read-only metrics ("X active workers") without management controls.

**Risk:** If removed from sidebar → ops team loses real-time visibility. Mitigation: add webhook alerts (Slack/Telegram) for critical failures instead of manual monitoring.

---

### 5. Provider Configuration

| Question | Answer | Reasoning |
|----------|--------|-----------|
| User goal | Connect different AI model providers (API keys, endpoints) | Flexibility to choose optimal models |
| New customer expects? | MAYBE ⚠️ (enterprise yes, individuals no) | Regular users use "default AI" |
| Interaction frequency | Infrequent (setup once, rarely change) | Configuration rather than usage |
| Mental model owner | ADMIN | API keys are security credentials |
| Expose increases usability? | MODERATELY — necessary for multi-provider setups | But not needed for single-provider default |
| User controls OR auto-manage? | User configures once, then AI auto-selects best provider | Manual setup → automatic optimization |
| Hiding reduces capability? | PARTIALLY — lose flexibility if hidden completely | Allow at least one custom endpoint option |
| Backend delivers value without UI? | YES — default provider works fine | Config is optional enhancement |
| Placement recommendation | Settings > Models (not sidebar) | Configuration area, infrequent access |
| Competitor placement | OpenAI playground has API config; Consumer apps hide this | B2B vs B2C split |

**Verdict:** MOVE to Settings area — Category C - Configuration  
**Rationale:** 
- For consumer product: remove entirely (single managed provider)
- For enterprise/self-hosted: expose in Settings (power users need customization)

**Recommendation:** Start with `Settings > Default Model` dropdown (preset choices). Add advanced "Custom Endpoint" field in Settings > Advanced for power users. Never put in primary sidebar.

---

### 6. Knowledge Base Upload (RAG Docs)

| Question | Answer | Reasoning |
|----------|--------|-----------|
| User goal | Enable AI to reference company documents, manuals, research papers | Context-specific answers |
| New customer expects? | YES ✅ | Growing expectation (Perplexity, Claude Docs) |
| Interaction frequency | Moderate — upload occasionally, retrieval automatic | One-time setup + ongoing benefit |
| Mental model owner | USER | "AI knows my stuff" is intuitive |
| Expose increases usability? | INCREASES — clear value proposition | Knowledge base directly improves answers |
| User controls OR auto-manage? | User uploads files, AI automatically retrieves relevant chunks | Should feel seamless, no configuration needed |
| Hiding reduces capability? | YES — lose differentiation if hidden | Key competitive feature |
| Backend delivers value without UI? | PARTIALLY — RAG service exists, but needs user-facing upload mechanism | Must make easy to add knowledge |
| Placement recommendation | Drag-drop in ChatView OR Settings > Documents (simple form) | Never dedicated sidebar page! |
| Competitor placement | Claude allows file upload directly in chat | Pattern established by leader |

**Verdict:** REMOVE dedicated RAG Docs page, implement as seamless upload experience — Category B - Advanced Feature  
**UX Pattern:**
1. User drags PDF/docx into ChatView
2. Notification appears: "AI now knows [filename]"
3. Next time user asks related question, AI references uploaded docs automatically
4. No "enable RAG" checkbox, no relevance tuning parameters exposed

**Critical insight:** Current RAG Docs page exposes too much complexity (chunking, embedding configs, similarity thresholds). Strip everything down to "upload file → AI uses it".

---

### 7. Memory Controls

| Question | Answer | Reasoning |
|----------|--------|-----------|
| User goal | AI remembers past conversations across sessions | Continuity in dialogue |
| New customer expects? | YES ✅ | ChatGPT has memory, Claude has history |
| Interaction frequency | Constant (happens automatically every session) | Shouldn't need user intervention |
| Mental model owner | SYSTEM | Users expect continuity, don't think about persistence mechanism |
| Expose increases usability? | DECREASES — shouldn't need to configure memory | "Remember me" is default behavior |
| User controls OR auto-manage? | AUTOMATIC — AI saves important conversations, deletes old ones | User shouldn't see "memory management" |
| Hiding reduces capability? | NO — memory still works, just hidden | Only UX simplification needed |
| Backend delivers value without UI? | YES — memory service runs silently | User doesn't need to see memory database |
| Placement recommendation | Fully automatic OR simple toggle in Settings > General | Never dedicated page! |
| Competitor placement | ChatGPT Memory settings in account preferences (not homepage) | Simple opt-in/out, not management panel |

**Verdict:** REMOVE dedicated Memory page entirely — Category C - Configuration (but minimal)  
**Recommended UX:**
```
Settings > General section:
☑ Remember my conversations
   Helps AI provide better responses based on past interactions
   
[Clear chat history] button — occasional maintenance task
```

**Critical insight:** Current Memory management page is over-engineered. Users don't want to "manage memory"; they just want AI to remember what matters. Simple toggle + periodic cleanup is sufficient.

---

### 8. Audit Logs Viewer

| Question | Answer | Reasoning |
|----------|--------|-----------|
| User goal | Track system events, debug failures, compliance reporting | Security & operations requirement |
| New customer expects? | NO ❌ (regular users), YES ✅ (admins/compliance officers) | Specialized audience only |
| Interaction frequency | Rare (quarterly audit reports, incident investigation) | Emergency/batch usage, not daily |
| Mental model owner | SYSTEM | Logs are internal event data |
| Expose increases usability? | DECREASES for normal users — confusing log format | Increases cognitive load |
| User controls OR auto-manage? | AUTO-GENERATED logs (users read/export, don't configure) | Read-only auditing |
| Hiding reduces capability? | NO — logs still exist, just harder to access | Compliance requirements met via export, not live viewer |
| Backend delivers value without UI? | YES — logging happens anyway | UI is convenience for debugging |
| Placement recommendation | Hidden from normal UI — separate admin portal | Auth-gated URL (`admin.aicompany.biz/audit`) |
| Competitor placement | GitHub Actions has logs per workflow; Notion has edit history | Specialized feature outside main app |

**Verdict:** REMOVE from Settings tab in main app — Category D - Internal System  
**Alternative:**
1. CLI command: `aic-audit export --from=2026-08-01 --to=2026-08-11 > audit.json`
2. Separate admin portal at `https://admin.aicompany.biz/audit` (requires admin JWT token)
3. Email notification for critical events (optional webhook integration)

**Risk assessment:** Removing from Settings might frustrate developers who like quick inspection. Mitigation: add `/debug/` route prefix requiring password/role check for developer tools.

---

### 9. Backup & Restore

| Question | Answer | Reasoning |
|----------|--------|-----------|
| User goal | Export/import app configuration, session data for disaster recovery | Data portability, migration |
| New customer expects? | YES ✅ (enterprise customers require it) | Compliance + operational necessity |
| Interaction frequency | Rare (monthly backup, occasional restore) | Maintenance task |
| Mental model owner | USER | "Backup" is familiar concept |
| Expose increases usability? | YES — clear value, straightforward operation | Export/restore is common pattern |
| User controls OR auto-manage? | HYBRID — manual export button + optional scheduled auto-backup | Best of both worlds |
| Hiding reduces capability? | NO — backend supports backup even if hidden | But removing UI lowers adoption |
| Backend delivers value without UI? | YES — serialization works independently | Need user-facing entry point though |
| Placement recommendation | Settings > Backup & Restore (with cloud sync option) | Configuration area, reasonable discoverability |
| Competitor placement | Google Drive has backup options; VS Code has settings sync | Cloud sync expected in modern apps |

**Verdict:** KEEP in Settings (don't remove) — Category C - Operator/Admin  
**Enhancement recommendations:**
1. Add auto-backup schedule (daily/weekly/monthly)
2. Support cloud storage sync (Google Drive, S3, Dropbox)
3. Encrypt backup files (password protection)
4. Version backups (keep last 30 days)

**Why keep:** Enterprise customers WILL ask for this. Not having it = compliance blocker.

---

### 10. Advanced Settings Panel

| Question | Answer | Reasoning |
|----------|--------|-----------|
| User goal | Debug features, experimental flags, dev tools access | Troubleshooting, testing, experimentation |
| New customer expects? | NO ❌ — dangerous to expose to regular users | Security risk if misused |
| Interaction frequency | Rare (developers only, debugging specific issues) | Specialized audience |
| Mental model owner | SYSTEM | Tech stack details belong to developers |
| Expose increases usability? | DECREASES — confuses non-devs, risks breaking production | Not appropriate for general users |
| User controls OR auto-manage? | AUTO-MANAGED defaults (experimental flags off by default) | Stability prioritization |
| Hiding reduces capability? | MINIMALLY — experts can access via alternative means | Environment variables override config |
| Backend delivers value without UI? | YES — flags configured via code/env vars | UI just convenient shortcut |
| Placement recommendation | Hidden completely (require special URL + auth) | Developer mode must be opt-in |
| Competitor placement | VS Code has `settings.json` file editing; Chrome has `chrome://flags` | Hidden behind deliberate action |

**Verdict:** REMOVE from normal Settings — Category D - Developer Tool (hidden)  
**Implementation:**
- Route: `/debug/*` requires admin role + additional confirmation dialog
- Alternative: environment variable `AIC_DEV_MODE=1` enables full debug suite
- Better: separate desktop app `aic-dev-tools` that connects to production instance (isolated tool)

**Safety rationale:** Accidental toggling of experimental flags can break production. Must require deliberate intent to access.

---

### 11. Observability Dashboard

*Evaluation assuming hypothetical implementation.*

| Question | Answer | Reasoning |
|----------|--------|-----------|
| User goal | Monitor latency metrics, error rates, resource utilization | Infrastructure health tracking |
| New customer expects? | NO ❌ — this is DevOps responsibility | Not end-user concern |
| Interaction frequency | Continuous for SRE team, zero for others | Specialized operations role |
| Mental model owner | SYSTEM | Metrics are internal signals |
| Expose increases usability? | DECREASES — overwhelms non-ops users | Too many charts confuse everyone |
| User controls OR auto-manage? | AUTO-MANAGED alerting (no manual chart viewing needed) | Proactive notifications better than passive dashboards |
| Hiding reduces capability? | NO — metrics logged anyway, can query externally | Just moves UI to right tool |
| Backend delivers value without UI? | YES — Prometheus/Grafana already do this | Don't reinvent wheel inside app |
| Placement recommendation | NONE — use external monitoring stack | Built-in dashboard = bad UX |
| Competitor placement | NEVER seen in consumer apps — always external tools | Datadog, New Relic, CloudWatch handle this |

**Verdict:** DO NOT IMPLEMENT INSIDE APP — Category D - Internal System (external)  
**Better approach:**
1. Export metrics to Prometheus (`/metrics` endpoint)
2. Configure Grafana dashboards (hosted separately)
3. Set up PagerDuty/OpsGenie alerts for critical thresholds
4. Optional: simple `/health` endpoint for k8s probes only

**Cost-benefit:** Building in-app observability wastes engineering resources better spent on core features. External tools already mature and customizable.

---

### 12. Worker Pool Controls

| Question | Answer | Reasoning |
|----------|--------|-----------|
| User goal | Manually scale number of parallel workers based on demand | Resource optimization |
| New customer expects? | NO ❌ — workers should auto-scale | Operations concern, not product feature |
| Interaction frequency | Rare (ops team adjusts monthly/quarterly) | Batch management task |
| Mental model owner | SYSTEM | Worker pools are infrastructure |
| Expose increases usability? | DECREASES — micromanagement distracts from actual work | Should trust auto-scaler |
| User controls OR auto-manage? | AUTO-MANAGED (dynamic scaling based on queue depth) | Humans shouldn't manually adjust |
| Hiding reduces capability? | NO — static pool size or auto-scaling handles both cases | Control unnecessary |
| Backend delivers value without UI? | YES — workers run regardless of visibility | UI just adds human intervention point |
| Placement recommendation | REMOVE from Live Company → show ONLY metrics (read-only indicator) | Hide controls entirely |
| Competitor placement | AWS Lambda has concurrency limits (config file); Serverless apps auto-scale | Control via IaC, not dashboard |

**Verdict:** REMOVE worker scaling controls from UI — Category D - Internal System (infrastructure)  
**What stays:**
- Read-only indicator: "🟢 5/10 workers active" (just info, no controls)
- Alert notification: "Worker pool nearing capacity → consider scaling" (passive warning)
- Ops CLI command: `aic-worker scale --target=15` (for scripted automation)

**Philosophy:** Auto-scaling removes human from loop. Manual controls invite micromanagement and introduce failure points.

---

## Final Classification Summary

### Category A - Core Product (Sidebar Navigation)

| Feature | Sidebar Position | Reason |
|---------|------------------|--------|
| Workspace (Dashboard) | #1 (Home) | Landing page, reduces friction |
| Chat | #2 | Primary interaction surface |
| Projects | #3 | Team workflows, moderate complexity |

**Total:** 3 items (optimal count for primary nav)

---

### Category B - Power User Features (Settings Area)

| Feature | Settings Tab | Reason |
|---------|--------------|--------|
| Models/Providers | `Settings > Models` | Configuration for flexibility |
| Documents/Knowledge | `Settings > Documents` (drag-drop upload) | Seemless UX, not complex RAG config |
| Conversations History | `Settings > General` (toggle) | Simple memory control |
| Backup & Restore | `Settings > Backup` | Compliance requirement |
| Autoscaling Limits | `Settings > Performance` (advanced) | Optional cap for enterprise |

**Total:** 5 tabs in Settings (reasonable cognitive load)

---

### Category C - Operator Tools (Admin-Only Access)

| Feature | Access Method | Reason |
|---------|---------------|--------|
| Audit Logs | Separate admin portal (`admin.aicompany.biz`) | Specialized ops audience |
| Worker Pool Metrics | Read-only indicator in Live Company (no controls) | Info only, no manipulation |
| Observability | External Grafana/Prometheus | Mature tools, avoid duplication |

**Total:** 3 tools (all restricted access)

---

### Category D - Developer/Internal (Hidden Completely)

| Feature | Implementation | Reason |
|---------|----------------|--------|
| Task Graph Visualization | `/debug/task-graph` (auth required) | Debugging aid only |
| Autonomy Engine Controls | Mission creation checkbox (temporary) → future dashboard if mature | Delay until proven |
| Advanced Settings | `/admin/*` route (admin role + password confirmation) | Safety-first design |
| Database Browser | CLI tool `aic-db-console` (dev use only) | Never expose GUI |
| Event Inspector | CLI stream `aic-event-log --follow` (developer tool) | Raw output, not pretty UI |

**Total:** 6 hidden tools (strictly internal)

---

## Commercial Competitor Benchmarking (Final State)

| Feature | ChatGPT | Claude | AIC-ADE (Current) | AIC-ADE (Recommended) | Verdict |
|---------|---------|--------|-------------------|----------------------|---------|
| Chat | ✅ Sidebar | ✅ Home | ✅ Sidebar | ✅ Sidebar | Match industry standard |
| Dashboard | ✅ Account page | ✅ Recent chats | ✅ Workspace | ✅ Workspace | Match |
| Projects | ❌ | ✅ Beta | ✅ Sidebar | ✅ Sidebar | Competitive |
| Memory | ✅ Opt-in settings | ✅ History retention | ⚠️ Dedicated page | ✅ Toggle in settings | Improve UX |
| Knowledge Base | ✅ Custom instructions | ✅ File upload in chat | ⚠️ RAG Docs page | ✅ Drag-drop in chat | Major improvement |
| Provider Config | ❌ Single provider | ❌ Single provider | ⚠️ Settings tab | ✅ Settings > Models | Acceptable |
| Backup | ❌ Export chats only | ✅ Session export | ✅ Settings tab | ✅ Settings > Backup | Match |
| Audit Logs | ✅ Usage history | ✅ Conversation export | ⚠️ Settings tab | 🚫 Separate admin portal | More secure |
| Worker Scaling | ❌ N/A | ❌ N/A | ⚠️ Live Company controls | 🚫 Hidden (auto-scaling) | Better ops practice |
| Observability | ❌ N/A | ❌ N/A | 🚫 Not implemented yet | 🚫 Use external tools | Smart decision |

**Overall assessment:** AIC-ADE currently exposes too many internal concepts. Recommended changes align product closer to competitor patterns while maintaining enterprise-grade capabilities.

---

## Implementation Priority

### Immediate (This Sprint)
1. Rename "RAG Docs" → "Documents" and move to Settings
2. Remove Memory page, add simple toggle to Settings > General
3. Hide worker pool controls (only show read-only metrics)
4. Add auto-backup schedule to Backup settings

### Short-Term (Next Sprint)
5. Create separate admin portal skeleton (future audit logs host)
6. Implement drag-drop file upload in ChatView (seamless knowledge injection)
7. Restrict `/admin/*` routes behind role-based access control
8. Document ops CLI commands (`aic-worker`, `aic-audit`, `aic-db-console`)

### Medium-Term (Roadmap Planning)
9. Evaluate autonomy feature maturity → decide whether to build dashboard
10. Decide on provider strategy: single managed provider (consumer) vs multi-provider (enterprise)
11. Externalize observability stack (Prometheus + Grafana deployment)
12. Conduct UX regression testing after all navigation changes

---

*Boundary review via:* feature evaluation framework, competitor benchmarking, product strategy analysis  
*Date: 2026-08-11 11:32 WIB*
