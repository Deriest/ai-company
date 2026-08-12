#!/usr/bin/env bash
# ============================================================================
# FIX Python Backend Path - Rebuild AIC-ADE v2.6.11
# Changed extraResources.to from "python-linux" to "." so backend finds it at $APPDIR/python-linux
# ============================================================================

set -euo pipefail

VERSION="2.6.11"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="$ROOT_DIR/app"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Fix Python Backend Path - v2.6.11                       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Update version
echo "📋 Bumping version to ${VERSION}..."
sed -i "s/\"version\": \"[^\"]*\"/\"version\": \"${VERSION}\"/" "$APP_DIR/package.json"

# Check dependencies installed
if [ ! -d "$APP_DIR/node_modules" ] || [ $(find "$APP_DIR/node_modules" -type d | wc -l) -eq 0 ]; then
    echo "📦 Installing dependencies..."
    cd "$APP_DIR"
    npm install --ci
fi

# Build
echo ""
echo "🔨 Building Linux & Windows..."
cd "$APP_DIR"
npm run build

echo ""
echo "📦 Building packages..."
mkdir -p ../app/dist

# Linux build
echo "   Building Linux..."
npx electron-builder --linux AppImage deb
if [ $? -ne 0 ]; then
    echo "❌ Linux build failed"
    exit 1
fi

# Windows build  
echo "   Building Windows..."
npx electron-builder --win nsis --x64
if [ $? -ne 0 ]; then
    echo "❌ Windows build failed"
    exit 1
fi

cd "$ROOT_DIR"

# Fix chrome-sandbox permissions
echo ""
echo "🔧 Fixing chrome-sandbox SUID bit..."
chmod 4755 "$APP_DIR/linux-unpacked/chrome-sandbox" 2>/dev/null || echo "⚠️  SUID fix requires root"

# Verify python-linux is in correct location
echo ""
echo "🔍 Verifying python-linux placement..."
if [ -d "$APP_DIR/squashfs-root/python-linux" ]; then
    echo "✅ python-linux found at ROOT level (correct!)"
elif [ -d "$APP_DIR/squashfs-root/resources/python-linux" ]; then
    echo "⚠️  python-linux still at resources/python-linux (OLD LOCATION)"
    echo "   Need to rebuild or move manually"
else
    echo "❌ python-linux NOT FOUND anywhere!"
fi

echo ""
echo "✅ Build complete!"
echo ""
echo "📦 Artifacts:"
ls -lh "$APP_DIR/dist/" | grep -E "(AppImage|deb|exe)"

echo ""
echo "🎯 Summary:"
echo "   • Fixed extraResources.to path for electron-builder"
echo "   • Python backend will now be placed at $APPDIR/python-linux"
echo "   • Backend startup scripts should find it correctly"
echo ""
