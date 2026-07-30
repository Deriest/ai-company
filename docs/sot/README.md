# AIC-ADE Single Source of Truth (SoT) Index

**Product:** AIC-ADE (Agentic Development Environment)
**Repository:** `AI-Company`
**Version:** SoT v2.0.2 → v2.1.0

This directory contains the official permanent engineering constitution of **AIC-ADE**. Every autonomous software decision, architecture change, worker specification, and release policy must follow these documents.

---

## Document Map — Foundational Constitution (00-34)

| # | Document Title | File |
|---|---|---|
| 00 | Product Constitution | `00_PRODUCT_CONSTITUTION.md` |
| 01 | Product Vision (Legacy) | `01_PRODUCT_VISION.md` |
| 02 | Product Identity | `02_PRODUCT_IDENTITY.md` |
| 03 | Architecture | `03_ARCHITECTURE.md` |
| 04 | AIC Runtime | `04_AIC_RUNTIME.md` |
| 05 | Project Runtime | `05_PROJECT_RUNTIME.md` |
| 06 | Worker Runtime | `06_WORKER_RUNTIME.md` |
| 07 | Hermes Dispatcher | `07_HERMES_DISPATCHER.md` |
| 08 | Worker Specification | `08_WORKER_SPECIFICATION.md` |
| 09 | Department Specification | `09_DEPARTMENT_SPECIFICATION.md` |
| 10 | Provider Runtime | `10_PROVIDER_RUNTIME.md` |
| 11 | Conversation Runtime | `11_CONVERSATION_RUNTIME.md` |
| 12 | Memory Runtime | `12_MEMORY_RUNTIME.md` |
| 13 | Knowledge Runtime | `13_KNOWLEDGE_RUNTIME.md` |
| 14 | Task Runtime | `14_TASK_RUNTIME.md` |
| 15 | Timeline Runtime | `15_TIMELINE_RUNTIME.md` |
| 16 | Event Runtime | `16_EVENT_RUNTIME.md` |
| 17 | Workspace Runtime | `17_WORKSPACE_RUNTIME.md` |
| 18 | UI Constitution | `18_UI_CONSTITUTION.md` |
| 19 | Design System | `19_DESIGN_SYSTEM.md` |
| 20 | Engineering Workflow | `20_ENGINEERING_WORKFLOW.md` |
| 21 | Project Structure | `21_PROJECT_STRUCTURE.md` |
| 22 | Folder Structure | `22_FOLDER_STRUCTURE.md` |
| 23 | Database Specification | `23_DATABASE_SPECIFICATION.md` |
| 24 | API Specification | `24_API_SPECIFICATION.md` |
| 25 | Testing Constitution | `25_TESTING_CONSTITUTION.md` |
| 26 | Release Engineering | `26_RELEASE_ENGINEERING.md` |
| 27 | Security Constitution | `27_SECURITY_CONSTITUTION.md` |
| 28 | Performance Constitution | `28_PERFORMANCE_CONSTITUTION.md` |
| 29 | Product State | `29_PRODUCT_STATE.md` |
| 30 | Roadmap | `30_ROADMAP.md` |
| 31 | Architecture Decisions | `31_ARCHITECTURE_DECISIONS.md` |
| 32 | Adaptive Runtime | `32_ADAPTIVE_RUNTIME.md` |
| 32 | Autonomous Engineering | `32_AUTONOMOUS_ENGINEERING.md` |
| 33 | Glossary | `33_GLOSSARY.md` |
| 34 | Future Vision | `34_FUTURE_VISION.md` |

---

## Document Map — Implementation Contract v2.0.2 → v2.1.0 (40-60)

**These documents are the AUTHORITATIVE source of truth for all implementation work between v2.0.2 and v2.1.0. If existing code conflicts with these documents, the code is considered incorrect.**

| # | Document Title | File |
|---|---|---|
| 40 | Product Vision | `40_PRODUCT_VISION.md` |
| 41 | Product Principles | `41_PRODUCT_PRINCIPLES.md` |
| 42 | Desktop Architecture | `42_DESKTOP_ARCHITECTURE.md` |
| 43 | Information Architecture | `43_INFORMATION_ARCHITECTURE.md` |
| 44 | User Journeys | `44_USER_JOURNEYS.md` |
| 45 | Workspace Specification | `45_WORKSPACE_SPECIFICATION.md` |
| 46 | AI Company Specification | `46_AI_COMPANY_SPECIFICATION.md` |
| 47 | Navigation Specification | `47_NAVIGATION_SPECIFICATION.md` |
| 48 | Design System | `48_DESIGN_SYSTEM.md` |
| 49 | Component Library | `49_COMPONENT_LIBRARY.md` |
| 50 | Workflow Specification | `50_WORKFLOW_SPECIFICATION.md` |
| 51 | Provider System | `51_PROVIDER_SYSTEM.md` |
| 52 | Model Discovery | `52_MODEL_DISCOVERY.md` |
| 53 | Update System | `53_UPDATE_SYSTEM.md` |
| 54 | Mission System | `54_MISSION_SYSTEM.md` |
| 55 | Timeline Specification | `55_TIMELINE_SPECIFICATION.md` |
| 56 | Evidence Center | `56_EVIDENCE_CENTER.md` |
| 57 | Company Office | `57_COMPANY_OFFICE.md` |
| 58 | Acceptance Criteria | `58_ACCEPTANCE_CRITERIA.md` |
| 59 | Technical Debt | `59_TECHNICAL_DEBT.md` |
| 60 | Execution Plan | `60_EXECUTION_PLAN_v2.0.2-v2.1.0.md` |

---

## Governance

- **00-34 series**: Foundational constitution (architecture, runtime specs, domain models). Superseded only by explicit 40-60 decisions.
- **40-60 series**: Implementation contract for v2.0.2→v2.1.0. These documents govern all code changes in this release cycle.
- When 40-60 conflicts with 00-34, **40-60 wins**.
- When code conflicts with 40-60, **code is incorrect** and must be changed.
