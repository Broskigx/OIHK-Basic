#!/usr/bin/env bash
# OIHK Basic — macOS Test Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Backend Tests ==="

VENV_DIR="$PROJECT_ROOT/backend/venv"
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
fi

cd "$PROJECT_ROOT/backend"
pip install -e "." --quiet
pip install pytest pytest-asyncio httpx --quiet

echo "Running pytest..."
python -m pytest --verbose --tb=short --no-header -x
echo "✓ Backend tests passed"

echo ""
echo "=== Frontend Tests ==="
cd "$PROJECT_ROOT/frontend"
npm install --silent
if grep -q '"test"' package.json; then
    npm test
    echo "✓ Frontend tests passed"
else
    echo "No test script found, skipping"
fi

echo ""
echo "=== All tests passed! ==="
