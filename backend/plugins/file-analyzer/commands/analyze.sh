#!/bin/bash
echo "=== File Analysis ==="
declare -A exts
while IFS= read -r f; do
    e="${f##*.}"
    ((exts[$e]++))
done < <(find . -type f ! -path './node_modules/*' ! -path './.venv/*' 2>/dev/null)
for e in "${!exts[@]}"; do printf "%-15s %d\n" "$e:" "${exts[$e]}"; done | sort -t: -k2 -rn
total=$(find . -type f ! -path './node_modules/*' ! -path './.venv/*' 2>/dev/null | wc -l)
echo "Total: $total files"
