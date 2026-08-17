# 40 — Product Vision

**Release Scope:** v2.0.2 → v2.1.0
**Status:** Source of Truth (Implementation Contract)
**Last Updated:** 2026-07-26

---

## What is AIC-ADE?

AIC-ADE (AI Company Agentic Development Environment) is a **local-first desktop application** that enables users to define, dispatch, monitor, and review software engineering work executed by a team of 15 specialized AI workers.

It is NOT a code editor. It is NOT a chatbot wrapper. It is NOT a dashboard.

It is an **AI Engineering Operating System** — a single desktop shell where a user can:
1. Talk to an AI engineering partner (Hermes)
2. Define projects and missions
3. Let autonomous workers plan, build, test, verify, and deliver software
4. Review evidence, approve work, and export artifacts

## Target User

**Primary:** Solo developers and small engineering teams who want to accelerate software delivery by delegating engineering tasks to AI agents while maintaining full control and review authority.

**Secondary:** Technical leads who need visibility into AI agent execution, evidence-based verification, and artifact management.

## Core Problem Solved

Software engineering is bottlenecked by:
- Manual coding, testing, and debugging cycles
- Context switching between planning, building, and reviewing
- Lack of visibility into AI agent work quality
- Difficulty managing multiple AI workers across a project

AIC-ADE solves this by providing a unified shell where the user's role shifts from **implementer** to **reviewer and orchestrator**.

## Product Philosophy

| Principle | Meaning |
|---|---|
| **Local-First** | All data, execution, and storage happen on the user's machine. No cloud dependency. |
| **Evidence-Based** | Every worker action produces auditable evidence. Claims without proof are rejected. |
| **Conversation-First** | Work begins with a conversation, not a form. Hermes clarifies before creating missions. |
| **Progressive Disclosure** | Show only what the user needs. Complexity is available but never forced. |
| **Desktop-Native** | Keyboard-first, instant interactions, native window management, auto-update. |

## What AIC-ADE is NOT

- NOT a replacement for human judgment — users approve, reject, and steer
- NOT a cloud SaaS — runs entirely on localhost
- NOT a generic AI chat — structured around engineering missions with real deliverables
- NOT a code editor — it contains a file explorer/editor for reviewing deliverables, not for daily coding

## Success Criteria (v2.1.0)

1. A user can open the app, configure one provider, and dispatch a mission within 2 minutes
2. Every mission produces real deliverables (files, test results, ZIP exports)
3. The desktop experience feels as polished as Cursor, VS Code, or Linear
4. Auto-update works reliably for all supported platforms
5. The update system delivers versioned artifacts with SHA256 verification
