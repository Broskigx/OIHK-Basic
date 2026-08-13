#!/usr/bin/env bash
# OIHK Basic — macOS Build Script
# Builds: backend sidecar + frontend + Tauri app (.app + .dmg)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
TAURI_DIR="$PROJECT_ROOT/src-tauri"
DIST_DIR="$PROJECT_ROOT/dist"
SIDECAR_DIR="$DIST_DIR/sidecar"

# Detect architecture
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    TARGET_DIR="arm64"
    TARGET_FLAG="aarch64-apple-darwin"
else
    TARGET_DIR="x64"
    TARGET_FLAG="x86_64-apple-darwin"
fi

echo "=== OIHK Basic Build (macOS) ==="
echo "Architecture: $ARCH"
echo "Project root: $PROJECT_ROOT"
python3 "$PROJECT_ROOT/scripts/version.py" check

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
python -m pip install -e "$BACKEND_DIR[dev,release]" --quiet
python -m pip check
python -m pip_audit "$BACKEND_DIR"
echo "  Done"

# 4. Run lint
echo ""
echo "[4/8] Running lint..."
python -m ruff check "$BACKEND_DIR/app" "$BACKEND_DIR/run.py" "$PROJECT_ROOT/scripts" "$PROJECT_ROOT/tests" --config "$BACKEND_DIR/pyproject.toml" --quiet

# 5. Run backend tests
echo ""
echo "[5/8] Running backend tests..."
cd "$PROJECT_ROOT"
python -m pytest backend/tests tests --quiet --tb=short --no-header -x || {
    echo "  ✗ Tests failed"
    exit 1
}
echo "  Tests passed"

# 6. Build backend sidecar (native arch)
echo ""
echo "[6/8] Building backend sidecar..."
cd "$PROJECT_ROOT"
rm -rf build
rm -rf "$SIDECAR_DIR"
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
cd "$FRONTEND_DIR"
npm ci --silent
npm audit --audit-level=high
npm run build || {
    echo "  ✗ Frontend build failed"
    exit 1
}
echo "  Frontend built"

# 8. Build Tauri desktop app
echo ""
echo "[8/8] Building Tauri desktop app..."
cd "$PROJECT_ROOT"
"$FRONTEND_DIR/node_modules/.bin/tauri" build --bundles dmg \
    --config "src-tauri/tauri.sidecar.conf.json" 2>&1 || {
    echo "  ✗ Tauri build failed"
    echo "  Note: codesigning requires Apple Developer account."
    echo "  For unsigned .app: codesign --force --deep --sign - target/release/bundle/macos/*.app"
    exit 1
}

# Copy artifacts to dist
TAURI_TARGET="$TAURI_DIR/target/release"
mkdir -p "$DIST_DIR/macos/$TARGET_DIR"
if [ -d "$TAURI_TARGET/bundle" ]; then
    cp -R "$TAURI_TARGET/bundle/macos/"*.app "$DIST_DIR/macos/$TARGET_DIR/" 2>/dev/null || true
    cp "$TAURI_TARGET/bundle/dmg/"*.dmg "$DIST_DIR/macos/$TARGET_DIR/" 2>/dev/null || true
fi

# Generate SHA-256
echo ""
echo "Artifact checksums:"
find "$DIST_DIR/macos/$TARGET_DIR" -maxdepth 1 -type f | while read -r f; do
    shasum -a 256 "$f" | tee "$f.sha256"
done

echo ""
echo "=== Build complete! ==="
echo "Artifacts: $DIST_DIR/macos/$TARGET_DIR/"
echo ""
echo "Note: .dmg is NOT signed or notarized. To sign:"
echo "  codesign --force --deep --sign \"Developer ID Application: Your Name\" path.app"
echo "  xcrun notarytool submit path.dmg --apple-id ... --team-id ... --password ..."
cd "$PROJECT_ROOT"
