# AIC Platform — System Surface Map
## Date: 2026-07-21

---

## Frontend Routes (13 pages)

| Route | Page | Auth Required |
|-------|------|---------------|
| `/` | Dashboard | Yes |
| `/chat` | Chat | Yes |
| `/projects` | Projects | Yes |
| `/tasks` | Tasks | Yes |
| `/workers` | Workers | Yes |
| `/workers/:id` | WorkerDetail | Yes |
| `/approvals` | Approvals | Yes |
| `/providers` | Providers | Yes |
| `/usage` | Usage | Yes |
| `/console` | Console | Yes |
| `/audit` | Audit | Yes |
| `/settings` | Settings | Yes |
| `/login` | Login | No |
| `*` | Redirect to `/` | — |

---

## Backend API Routes (55 endpoints)

### Auth (`/api/auth`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/login` | No | Login, returns JWT |
| POST | `/register` | No | Register user |
| GET | `/me` | Yes | Get current user |
| POST | `/api-key` | Yes | Generate API key |

### Conversations (`/api/conversations`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Yes | List conversations (user-scoped) |
| POST | `/` | Yes | Create conversation |
| PUT | `/{id}` | Yes | Update conversation |
| DELETE | `/{id}` | Yes | Delete conversation |
| GET | `/{id}/messages` | Yes | Get messages |
| POST | `/{id}/messages` | Yes | Send message (regular) |
| POST | `/{id}/messages/stream` | Yes | Send message (SSE) |
| DELETE | `/{id}/messages` | Yes | Clear message history |
| POST | `/batch` | Yes | Batch operations |

### Dashboard (`/api/dashboard`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/overview` | Yes | Stats overview |
| GET | `/events` | Yes | Recent events |
| GET | `/metrics` | Yes | Metrics |
| GET | `/audit` | Yes | Audit trail |

### Workers (`/api/workers`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Yes | List workers |
| GET | `/registry` | Yes | Worker registry |
| GET | `/{id}` | Yes | Worker detail |
| GET | `/{id}/leases` | Yes | Worker leases |

### Tasks (`/api/tasks`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Yes | List tasks |
| GET | `/{id}` | Yes | Task detail |
| POST | `/` | Yes | Create task |
| POST | `/{id}/dispatch` | Yes | Dispatch task |
| POST | `/{id}/cancel` | Yes | Cancel task |

### Projects (`/api/projects`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Yes | List projects |
| GET | `/{id}` | Yes | Project detail |
| GET | `/{id}/tasks` | Yes | Project tasks |
| GET | `/{id}/milestones` | Yes | Project milestones |
| POST | `/` | Yes | Create project |

### LLM (`/api/llm`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/providers` | Yes | List providers |
| POST | `/providers` | Yes | Create provider |
| PUT | `/providers/{id}` | Yes | Update provider |
| DELETE | `/providers/{id}` | Yes | Delete provider |
| GET | `/providers/{id}/models` | Yes | List models |
| POST | `/providers/{id}/activate` | Yes | Set active provider |
| POST | `/providers/{id}/test` | Yes | Test connection |
| GET | `/usage` | Yes | Usage stats |
| GET | `/usage/summary` | Yes | Usage summary |
| GET | `/usage/breakdown` | Yes | Usage by provider/model |
| GET | `/usage/timeline` | Yes | Usage timeline |

### Console (`/api/console`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/logs` | Yes | Backend logs |
| GET | `/events` | Yes | Platform events |
| GET | `/audit` | Yes | Audit trail |
| GET | `/metrics` | Yes | System metrics |
| GET | `/status` | Yes | System status |

### Approvals (`/api/approvals`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Yes | List approvals |
| GET | `/pending` | Yes | Pending approvals |
| POST | `/{id}/decide` | Yes | Approve/reject |

### Users (`/api/users`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Yes | List users |
| PUT | `/{id}` | Yes | Update user |
| DELETE | `/{id}` | Yes | Delete user |

---

## Database Entities

| Entity | Table | Key Fields |
|--------|-------|------------|
| User | `users` | id, username, email, role, hashed_password, api_keys |
| Conversation | `conversations` | id, user_id, project_id, title, context |
| Message | `messages` | id, conversation_id, role, content, intent, metadata |
| Project | `projects` | id, name, description |
| Task | `tasks` | id, project_id, title, description, type, status, worker_type, progress |
| Worker | `workers` | id, name, type, status, capabilities, config |
| Lease | `leases` | id, worker_id, task_id, phase, status |
| Approval | `approvals` | id, task_id, type, status, approver_id |
| Event | `events` | id, type, data, severity, trace_id |
| AuditLog | `audit_logs` | id, actor, action, resource_type, resource_id, result |
| Metric | `metrics` | id, name, value, unit, labels |
| LLMProviderConfig | `llm_provider_configs` | id, name, base_url, api_key, models, is_active |
| LLMUsageLog | `llm_usage_logs` | id, provider, model, tier, purpose, tokens |

---

## FSM Phases (AIC-Skill Canonical)

```
CREATED → INVESTIGATE → PLANNING → IMPLEMENTATION → VERIFICATION → CLOSEOUT → COMPLETE
                                                              ↓
                                                         CANCELLED/BLOCKED
```

## Canonical Workers (15)

| Type | Name | Tier | Phase(s) |
|------|------|------|----------|
| pm | Project Manager | thinker | INVESTIGATE, PLANNING, CLOSEOUT |
| architect | Architect | thinker | PLANNING |
| research | Researcher | thinker | PLANNING |
| designer | Designer | thinker | PLANNING |
| backend | Backend Engineer | crafter | IMPLEMENTATION |
| frontend | Frontend Engineer | crafter | IMPLEMENTATION |
| qa | QA Engineer | crafter | VERIFICATION |
| coding | Full-Stack Developer | crafter | (extension) |
| database | Database Engineer | crafter | (extension) |
| security | Security Analyst | thinker | (extension) |
| documentation | Documentation Writer | crafter | (extension) |
| deployment | Deployment Engineer | crafter | (extension) |
| devops | DevOps Engineer | crafter | (extension) |
| performance | Performance Engineer | crafter | (extension) |
| debugger | Debugger | thinker | (extension) |
