#!/usr/bin/env bash
# Render deployment progress by counting checkboxes in each phase's CHECKLIST.md.
# Tick an item by changing "- [ ]" to "- [x]" in the file.
#
#   bash deployment/progress.sh          # summary
#   bash deployment/progress.sh -v       # also list outstanding items
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERBOSE="${1:-}"
WIDTH=32

# colours only when attached to a terminal
if [ -t 1 ]; then
  G=$'\033[32m'; Y=$'\033[33m'; D=$'\033[2m'; B=$'\033[1m'; R=$'\033[0m'
else
  G=""; Y=""; D=""; B=""; R=""
fi

bar() {  # bar <done> <total>
  local done=$1 total=$2 filled=0
  [ "$total" -gt 0 ] && filled=$(( done * WIDTH / total ))
  local out="" i
  for ((i=0; i<WIDTH; i++)); do
    if [ "$i" -lt "$filled" ]; then out+="█"; else out+="░"; fi
  done
  printf "%s" "$out"
}

total_done=0; total_all=0
printf "\n%sSwarna Andhra — production deployment%s\n\n" "$B" "$R"

for phase in "$DIR"/[0-9]*/; do
  name=$(basename "$phase")
  file="$phase/CHECKLIST.md"
  [ -f "$file" ] || continue

  d=$(grep -c '^- \[x\]' "$file" 2>/dev/null || true); d=${d:-0}
  o=$(grep -c '^- \[ \]' "$file" 2>/dev/null || true); o=${o:-0}
  t=$(( d + o ))
  total_done=$(( total_done + d )); total_all=$(( total_all + t ))

  pct=0; [ "$t" -gt 0 ] && pct=$(( d * 100 / t ))
  if   [ "$pct" -eq 100 ]; then c="$G"
  elif [ "$pct" -gt 0 ];   then c="$Y"
  else                          c="$D"; fi

  printf "  %s%-18s%s %s%s%s  %2d/%-2d  %3d%%\n" \
    "$B" "$name" "$R" "$c" "$(bar "$d" "$t")" "$R" "$d" "$t" "$pct"

  if [ "$VERBOSE" = "-v" ] && [ "$o" -gt 0 ]; then
    grep '^- \[ \]' "$file" | sed "s/^- \[ \] /      ${D}·${R} /" | head -20
    echo
  fi
done

pct=0; [ "$total_all" -gt 0 ] && pct=$(( total_done * 100 / total_all ))
printf "\n  %sOVERALL%s            %s  %2d/%-2d  %3d%%\n\n" \
  "$B" "$R" "$(bar "$total_done" "$total_all")" "$total_done" "$total_all" "$pct"

# surface the next actionable item
next=$(grep -m1 -r '^- \[ \]' "$DIR"/[0-9]*/CHECKLIST.md 2>/dev/null | head -1)
if [ -n "$next" ]; then
  ph=$(echo "$next" | sed 's|.*/deployment/||; s|/CHECKLIST.md.*||')
  item=$(echo "$next" | sed 's/.*- \[ \] //')
  printf "  %sNext:%s [%s] %s\n\n" "$B" "$R" "$ph" "$item"
else
  printf "  %sAll items complete.%s\n\n" "$G" "$R"
fi
