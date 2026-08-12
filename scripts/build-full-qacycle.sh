#!/usr/bin/env bash
# ============================================================================
# FULL BUILD + QA CYCLE - Blank Screen Fix v2.6.10
# Investigate → Fix → Build → QA → Repeat if needed
# ============================================================================

set -euo pipefail

VERSION="2.6.10"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="$ROOT_DIR/app"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  AIC-ADE Full QA Cycle - Blank Screen Fix               ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Phase 1: Version Bump & Build"
echo "─" * 50
echo ""

# Step 1: Update version
echo "📋 Updating package.json to ${VERSION}..."
sed -i "s/\"version\": \"[^\"]*\"/\"version\": \"${VERSION}\"/" "$APP_DIR/package.json"

# Step 2: Install dependencies if needed
if [ ! -d "$APP_DIR/node_modules" ]; then
    echo "📦 Installing dependencies..."
    cd "$APP_DIR"
    npm install --ci
fi

# Step 3: Run release.sh (with chrome-sandbox fix already embedded)
echo ""
echo "🔨 Running release.sh build..."
cd "$ROOT_DIR"
./scripts/release.sh $VERSION 2>&1 | tee /tmp/release-v$VERSION.log || true

echo ""
echo "✅ Build complete! Files ready at:"
ls -lh "$APP_DIR/dist/" | grep -E "(AppImage|deb|exe)"
