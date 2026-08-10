#!/bin/bash
echo "=== Git Audit ==="
git log --oneline -10 2>/dev/null || echo "No git history"
git status --porcelain 2>/dev/null | head -20
if [ $(git status --porcelain 2>/dev/null | wc -l) -gt 0 ]; then
    echo "- Warning: Uncommitted changes present"
fi
echo "Audit complete"
