#!/usr/bin/env bash
# OIHK Basic — Linux Build Script
# Builds: backend sidecar + frontend + Tauri app (AppImage + .deb)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
TAURI_DIR="$PROJECT_ROOT/src-tauri"
DIST_DIR="$PROJECT_ROOT/dist"
SIDECAR_DIR="$DIST_DIR/sidecar"

echo "=== OIHK Basic Build (Linux) ==="
echo "Project root: $PROJECT_ROOT"

# 1. Verify tools
echo ""
echo "[1/8] Verifying tools..."
for tool in python3 npm cargo rustc; do
    if command -v "$tool" &>/dev/null; then
        echo "  ✓ $tool found"
    else
        echo "  ✗ $tool not found"
        exit 1
    fi
done
# 2. Python virtual environment
echo ""
echo "[2/8] Setting up Python virtual environment..."
if [ ! -d "$BACKEND_DIR/venv" ]; then
    python3 -m venv "$BACKEND_DIR/venv"
fi
source "$BACKEND_DIR/venv/bin/activate"

# 3. Install Python dependencies
echo ""
echo "[3/8] Installing Python dependencies..."
pip install -e "$BACKEND_DIR[dev]" pyinstaller --quiet
echo "  Done"

# 4. Run lint
echo ""
echo "[4/8] Running lint..."
python -m ruff check "$BACKEND_DIR/app" "$BACKEND_DIR/tests" --quiet

# 5. Run backend tests
echo ""
echo "[5/8] Running backend tests..."
cd "$BACKEND_DIR"
python -m pytest --quiet --tb=short --no-header -x || {
    echo "  ✗ Tests failed"
    exit 1
}
echo "  Tests passed"

# 6. Build backend sidecar
echo ""
echo "[6/8] Building backend sidecar..."
cd "$PROJECT_ROOT"
rm -rf build dist/sidecar
python -m PyInstaller oihk-basic-backend.spec --clean --noconfirm --distpath "$SIDECAR_DIR" || {
    echo "  ✗ PyInstaller build failed"
    exit 1
}
chmod +x "$SIDECAR_DIR/oihk-basic-backend"
TARGET_TRIPLE=$(rustc -vV | sed -n 's/^host: //p')
cp "$SIDECAR_DIR/oihk-basic-backend" "$SIDECAR_DIR/oihk-basic-backend-$TARGET_TRIPLE"
chmod +x "$SIDECAR_DIR/oihk-basic-backend-$TARGET_TRIPLE"
echo "  Sidecar built"

# 7. Build frontend
echo ""
echo "[7/8] Building frontend..."
cd "$PROJECT_ROOT"
npm ci --silent
npm run build || {
    echo "  ✗ Frontend build failed"
    exit 1
}
echo "  Frontend built"

# 8. Build Tauri desktop app
echo ""
echo "[8/8] Building Tauri desktop app..."
cd "$FRONTEND_DIR"
# Install Linux system deps if needed
if command -v apt-get &>/dev/null; then
    sudo apt-get update -qq && sudo apt-get install -y -qq \
        libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev \
        librsvg2-dev patchelf libssl-dev 2>/dev/null || true
fi

"$FRONTEND_DIR/node_modules/.bin/tauri" build --bundles "appimage,deb" \
    --config "src-tauri/tauri.sidecar.conf.json" 2>&1 || {
    echo "  ✗ Tauri build failed (may need system deps)"
    echo "  See: https://v2.tauri.app/start/prerequisites/"
    exit 1
}

# Copy artifacts to dist
TAURI_TARGET="$TAURI_DIR/target/release"
mkdir -p "$DIST_DIR/linux"
if [ -d "$TAURI_TARGET/bundle" ]; then
    cp "$TAURI_TARGET/bundle"/appimage/*.AppImage "$DIST_DIR/linux/" 2>/dev/null || true
    cp "$TAURI_TARGET/bundle"/deb/*.deb "$DIST_DIR/linux/" 2>/dev/null || true
fi

# Generate SHA-256
echo ""
echo "Artifact checksums:"
find "$DIST_DIR/linux" -maxdepth 1 -type f | while read -r f; do
    sha256sum "$f" | tee "$f.sha256"
done

echo ""
echo "=== Build complete! ==="
echo "Artifacts: $DIST_DIR/linux/"
cd "$PROJECT_ROOT"
