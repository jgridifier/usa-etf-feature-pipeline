#!/usr/bin/env bash
# Build the Pages v2 Vite + React app into docs/.
# Usage: bash scripts/build_pages_v2.sh [--data-only]
#
# --data-only  re-run only the Python data/viz build (scripts/build_pages.py),
#              skipping the Vite JS build. Useful after a new run-strategies call.
#
# What this does:
#   1. Optionally rebuild viz JSON snapshots via scripts/build_pages.py.
#   2. Remove stale v2-* assets from docs/assets/ (prevents accumulation).
#   3. Run `npm run build` in apps/pages/ → outputs to docs/.
#   4. Remind you to commit docs/.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PAGES_DIR="$REPO_ROOT/apps/pages"
DOCS_DIR="$REPO_ROOT/docs"
ASSETS_DIR="$DOCS_DIR/assets"

DATA_ONLY=false
for arg in "$@"; do
  [[ "$arg" == "--data-only" ]] && DATA_ONLY=true
done

echo "=== Pages v2 build ==="
echo "Repo root: $REPO_ROOT"

# Step 1: rebuild viz JSON (data pipeline)
echo
echo "--- Step 1: Rebuild viz JSON snapshots (build_pages.py) ---"
python3 "$REPO_ROOT/scripts/build_pages.py" || {
  echo "Warning: build_pages.py failed or skipped (may need CIO CSV inputs)."
}

# SPA owns Books/Runs hash routes — drop any leftover static HTML shells.
rm -fv "$DOCS_DIR/books.html" "$DOCS_DIR/runs.html"

if $DATA_ONLY; then
  echo "-- data-only flag set; skipping Vite JS build."
  echo "=== Done (data only). Preview: python -m http.server 8000 --directory docs ==="
  exit 0
fi

# Step 2: clean stale v2 assets
echo
echo "--- Step 2: Clean stale v2-* assets from docs/assets/ ---"
if ls "$ASSETS_DIR"/v2-* 1>/dev/null 2>&1; then
  rm -v "$ASSETS_DIR"/v2-*
fi

# Step 3: Vite build
echo
echo "--- Step 3: npm run build (apps/pages → docs/) ---"
cd "$PAGES_DIR"
npm run build

echo
echo "=== Build complete ==="
echo "Preview locally:"
echo "  python -m http.server 8000 --directory $DOCS_DIR"
echo
echo "Then commit docs/ when happy:"
echo "  git add docs/ && git commit -m 'chore: rebuild Pages v2'"
