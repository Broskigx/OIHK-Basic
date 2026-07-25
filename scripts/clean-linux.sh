#!/usr/bin/env bash
# OIHK Basic — Linux Clean Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Cleaning OIHK Basic build artifacts ==="

DIRS_TO_REMOVE=(
    "$PROJECT_ROOT/backend/venv"
    "$PROJECT_ROOT/backend/__pycache__"
    "$PROJECT_ROOT/backend/*.egg-info"
    "$PROJECT_ROOT/backend/*.db"
    "$PROJECT_ROOT/backend/storage"
    "$PROJECT_ROOT/frontend/node_modules"
    "$PROJECT_ROOT/frontend/dist"
    "$PROJECT_ROOT/frontend/.vite"
    "$PROJECT_ROOT/src-tauri/target"
    "$PROJECT_ROOT/build"
    "$PROJECT_ROOT/dist/sidecar"
)

for dir in "${DIRS_TO_REMOVE[@]}"; do
    # Expand globs
    for expanded in $dir; do
        if [ -e "$expanded" ]; then
            echo "  Removing: $expanded"
            rm -rf "$expanded"
        fi
    done
done

# Remove stray Python cache
find "$PROJECT_ROOT" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$PROJECT_ROOT" -type f -name "*.pyc" -delete 2>/dev/null || true
find "$PROJECT_ROOT" -type f -name "*.pyo" -delete 2>/dev/null || true

echo ""
echo "Clean complete. Project is ready for fresh build."
