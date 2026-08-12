# Documentation Audit v1.0 (Aug 2026)

## Before State

### Total Files
- **~1443 Markdown files** (excluding node_modules, .venv, workspace data)
- Active: ~145 files in root/docs/backend structure

### File Distribution
| Location | Count | Type |
|----------|-------|------|
| docs/sot/ | 62 | System of Truth (architecture/state/specs) |
| docs/archive/ | 110 | Old release reports |
| backend/docs/ | 51 | Backend technical docs |
| docs/product-discovery/ | 39 | Feature discovery notes |
| docs/ (root) | 19 | Various reports/states |
| app/docs/ | 25 | App documentation |
| Root | 7 | Project READMEs |

### Major Duplication Problems

1. **Version-specific reports** - RELEASE_SUMMARY_v2.6.1 through v2.6.5
2. **QA reports duplicated** - QA_REPORT, QA_RESULTS, QA_E2E_REPORT all for same versions
3. **SOT documents fragmented** - 62 System of Truth files, many overlapping concepts
4. **Error handling index** - 8 error-handling docs describing same patterns
5. **PR implementation logs** - PR-1 through PR-9 implementation reports (outdated)
6. **Codemaps** - One per backend folder (redundant with central codemap)
7. **Product discovery** - 39 incremental discovery notes (should be consolidated)

### Files Classified as DELETE
- All versioned reports (v2.6.1-v2.6.5) → merge to archive
- Error handling series (8 files) → consolidate to single doc
- Product discovery notes (39 files) → consolidate to single spec
- Codemaps in each backend folder → delete redundant ones
- Workspace deliverable files (~1000+) → DELETE (ephemeral AI outputs)

### Files Classified as ARCHIVE
- RELEASE_SUMMARY_v2.6.* (4 files)
- QA_*_v2.6.* (4 files)
- CODE_FIXES_APPLIED.md
- CLEANUP_REPORT_v2.6.3.md
- FIX_ATTEMPT_REPORT_v2.6.3.md
- LIMITATIONS_RESOLUTION_v2.6.3.md
- GITHUB_UPLOAD_INSTRUCTIONS_v2.6.2.md

### Files Classified as MERGE/REWRITE
- sot/*.md (62 files) → consolidate to canonical ARCHITECTURE, PRODUCT, WORKFLOW
- backend/docs/*.md (51 files) → map to canonical docs
- product-discovery/*.md (39 files) → merge into PRODUCT.md

### Files to KEEP
- README.md (root)
- latest.json (auto-update manifest)
- AGENTS.md files (only if they contain agent-specific instructions)
- LICENSE (if exists)
