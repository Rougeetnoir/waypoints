#!/usr/bin/env bash
# One-command update: enrich new places → build site → commit → push
# Usage: ./update.sh "commit message"

set -e

MSG="${1:-update places}"

echo "═══════════════════════════════════════"
echo " Waypoints — update & deploy"
echo "═══════════════════════════════════════"

echo ""
echo "▶ Step 1/3  Enriching new places..."
venv/bin/python scripts/enrich_places.py

echo ""
echo "▶ Step 2/3  Building site..."
venv/bin/python scripts/build_site.py

echo ""
echo "▶ Step 3/3  Committing and pushing..."
git add .
git commit -m "$MSG" || echo "  Nothing to commit."
git push

echo ""
echo "═══════════════════════════════════════"
echo " ✓ Done! Live in ~1 min:"
echo "   https://rougeetnoir.github.io/waypoints/"
echo "═══════════════════════════════════════"
