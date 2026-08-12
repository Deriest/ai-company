# Documentation Maintenance Policy

## Philosophy

Documentation is a **small, authoritative knowledge base**, not a chronological log of development actions.

The repository maintains canonical documents as the primary source of truth. Every permanent document must justify its existence.

**Goal**: Maximum useful knowledge with minimum documentation surface area.

---

## Current Canonical Structure

```text
README.md              # Project overview & quick links
docs/
├── ARCHITECTURE.md    # System design, components, boundaries
├── PRODUCT.md         # Features, workflows, user-facing behavior
├── DEVELOPMENT.md     # Setup, workflow conventions, standards
├── TESTING.md         # Test strategy, categories, coverage goals
├── SECURITY.md        # Hardening notes, constraints, best practices
├── DEPLOYMENT.md      # Build process, release workflow, auto-update
└── archive/           # Historical material (intentionally preserved)
```

Target: **6-10 active files**, stable over time.

---

## 1. NO DOCUMENTATION SPRAWL

Do NOT create new `.md` files for:

| Category | ❌ Forbidden Examples |
|----------|---------------------|
| Task completion | `*_REPORT.md`, `*_COMPLETION.md`, `*_FINAL.md` |
| Bug fixes | `*_FIX.md`, `*_RESOLUTION.md` |
| Tests/QA | `*_RESULTS.md`, `*_VALIDATION.md`, `QA_REPORT.md` |
| Releases | `RELEASE_v2.7.0.md`, `*_SUMMARY.md` |
| Investigations | `*_ANALYSIS.md`, `INVESTIGATION_NOTES.md` |
| Reviews | `*_REVIEW.md`, `AUDIT.md` |
| Version updates | `ARCHITECTURE_v2.7.md`, `*_V2.md` |

Task completion should be represented by:
- Code changes
- Git commits / PR descriptions
- Updated canonical documentation when necessary
- CI test results

---

## 2. UPDATE EXISTING DOCUMENTATION FIRST

Before creating any new file:

1. Search existing `docs/`
2. Identify the canonical document responsible
3. Update the existing document

| Subject | Where to update |
|---------|-----------------|
| Architecture change | `docs/ARCHITECTURE.md` |
| Feature/specification change | `docs/PRODUCT.md` |
| Development workflow change | `docs/DEVELOPMENT.md` |
| Testing strategy change | `docs/TESTING.md` |
| Security constraint change | `docs/SECURITY.md` |
| Deployment process change | `docs/DEPLOYMENT.md` |

---

## 3. DOCUMENT ONLY DURABLE KNOWLEDGE

### ✅ Good Documentation
- Architecture decisions and invariants
- System boundaries and contracts
- API specifications
- Deployment requirements
- Security constraints
- Development conventions
- Testing strategy
- Product behavior
- Operational procedures
- Non-obvious technical decisions
- Important limitations that persist

### ❌ Bad Documentation
- "I changed X today"
- "All tests passed"
- "Task completed"
- "Fixed 17 issues"
- Temporary debugging notes
- Raw agent reasoning
- Chronological work logs
- Terminal output dumps
- Repetitive progress reports

---

## 4. VERSIONED DOCUMENTATION

Never create version-specific copies:

❌ `ARCHITECTURE_v2.7.md`  
✅ `docs/ARCHITECTURE.md` (always describes current state)

Historical version information belongs in `docs/archive/` only when it has genuine historical value.

---

## 5. RELEASE DOCUMENTATION

Releases do NOT automatically require Markdown files.

Prefer:
- Git tags
- GitHub Releases page
- CHANGELOG if project uses one

If a changelog is required, use ONE canonical file rather than per-release documents.

Create release documentation ONLY if explicitly requested.

---

## 6. QA AND TESTING

Do NOT create QA documents for every test pass.

Testing strategy belongs in `docs/TESTING.md`.

Test results belong in:
- CI/CD pipelines
- GitHub Actions
- Pull requests
- Terminal output
- Issue tracking

---

## 7. INVESTIGATION NOTES

Temporary investigations should not become permanent documentation.

**Flow:**
```
Investigation
     ↓
Extract durable knowledge
     ↓
Update canonical documentation
     ↓
Discard temporary notes
```

Preserve entire investigation ONLY if it has legitimate architectural or historical value.

---

## 8. ARCHIVE POLICY

`docs/archive/` is intentional preservation, not a dumping ground.

Archive only when:
- Records an important architectural transition
- Documents a previous production release
- Explains a significant migration
- Provides useful historical context
- Required for future debugging/auditing

If no meaningful historical value exists → DELETE.

---

## 9. AGENTS.md

Special instruction file for coding agents (not ordinary documentation).

Before modifying:
1. Check if still valid
2. Remove obsolete instructions
3. Remove duplicated content
4. Preserve repository-specific constraints
5. Keep concise and actionable

Do NOT create multiple `AGENTS.md` files unless directory-specific agent behavior genuinely requires it.

---

## 10. SOURCE-OF-TRUTH RULE

Every major topic has ONE authoritative location.

If two documents conflict:
1. Determine actual implementation
2. Determine intended contract
3. Update the canonical document
4. Remove or archive the obsolete document

NEVER solve contradictions by creating a third document.

---

## 11. CODE IS THE IMPLEMENTATION AUTHORITY

Documentation must reflect actual system behavior.

When updating documentation:
- Inspect relevant source code
- Verify configuration
- Check API routes/contracts
- Review tests

If documentation disagrees with implementation:
- Correct documentation to match actual system, OR
- Document the intended contract if different from current state

---

## 12. DOCUMENTATION BUDGET

Target metrics:

| Category | Target Count |
|----------|--------------|
| Active docs | 6-10 |
| Archive items | Intentional only |
| Temp files | Zero |

New permanent documentation category = architectural decision requiring justification.

---

## 13. DECISION TREE

```
Did system behavior change?
        |
        +-- NO --> No doc change required
        |
        +-- YES
              |
              v
Does existing canonical doc cover it?
              |
              +-- YES --> Update canonical doc
              |
              +-- NO
                    |
                    v
Is new permanent source of truth required?
                    |
                    +-- NO --> Do not create
                    |
                    +-- YES --> Create one focused doc
```

---

## 14. TASK COMPLETION CHECKLIST

Before marking a task complete:

- [ ] Did I create unnecessary `.md` files?
- [ ] Did I duplicate existing documentation?
- [ ] Did I create a temporary report?
- [ ] Did I create unnecessary version-specific docs?
- [ ] Did I update the correct canonical document?
- [ ] Are any existing docs now obsolete?
- [ ] Did I introduce conflicting sources of truth?

If unnecessary documentation was created → REMOVE it before completion.

---

## 15. PERIODIC AUDIT

During major milestones/releases/refactors:

Run lightweight audit:

```bash
find . -type f \( -name "*.md" -o -name "AGENTS.md" \) ! -path "./node_modules/*" ! -path "./.git/*" ! -path "./backend/.venv/*" ! -path "./backend/data/workspace*" ! -path "./app/node_modules/*"
```

Check for:
- Duplicate documents
- Stale/obsolete files
- Broken links
- Conflicting instructions
- Docs describing deleted functionality
- Temporary reports to remove

Make only justified changes.

---

## 16. SUCCESS CRITERIA

Documentation system should remain:

| Criterion | Description |
|-----------|-------------|
| Small | 6-10 active files |
| Canonical | Single authoritative source per topic |
| Current | Reflects actual system |
| Discoverable | Clear structure |
| Consistent | No internal conflicts |
| Agent-friendly | Clear, actionable |
| Low-maintenance | Minimal upkeep required |

**Key principle**: Code changes should not automatically produce documentation changes. Task completion should not automatically produce reports. Every document must justify its existence.
