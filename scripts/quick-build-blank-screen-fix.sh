#!/usr/bin/env bash
# ============================================================================
# QUICK BUILD SCRIPT - Blank Screen Fix v2.6.10
# Just builds and creates release with the fix applied
# ============================================================================

set -euo pipefail

VERSION="2.6.10"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="$ROOT_DIR/app"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  AIC-ADE Quick Build - Blank Screen Fix                  ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Update version
echo "📋 Bumping version to ${VERSION}..."
sed -i "s/\"version\": \"[^\"]*\"/\"version\": \"${VERSION}\"/" "$APP_DIR/package.json"
python3 << EOF
import json
with open('$APP_DIR/package-lock.json') as f:
    data = json.load(f)
data['version'] = '$VERSION'
if 'packages' in data and '' in data['packages']:
    data['packages']['']['version'] = '$VERSION'
with open('$APP_DIR/package-lock.json', 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
EOF

echo "✅ Version bumped to ${VERSION}"

# Step 2: Install dependencies if needed
cd "$APP_DIR"
if [ ! -d "node_modules" ] || [ $(find node_modules -type d | wc -l) -eq 0 ]; then
    echo "Installing dependencies..."
    npm install
fi

# Step 3: Build
echo ""
echo "🔨 Building application..."
npm run build

# Step 4: Build binaries
echo ""
echo "📦 Building platforms..."
mkdir -p dist
npm run dist:win
npm run dist:linux

echo "✅ Build complete!"

# Step 5: Generate latest.json
cd ..
cat > latest.json << EOF
{
  "version": "${VERSION}",
  "channel": "stable",
  "releaseDate": "$(date +%F)",
  "releaseNotes": "v${VERSION} — Fixed blank screen issue on fresh install",
  "platforms": {
    "linux": {
      "downloadUrl": "https://github.com/Deriest/ai-company/releases/download/v${VERSION}/AIC-ADE-${VERSION}.AppImage",
      "sha256": "TO_BE_GENERATED",
      "size": 0,
      "filename": "AIC-ADE-${VERSION}.AppImage",
      "type": "AppImage"
    },
    "linux-deb": {
      "downloadUrl": "https://github.com/Deriest/ai-company/releases/download/v${VERSION}/aic-ade_${VERSION}_amd64.deb",
      "sha256": "TO_BE_GENERATED",
      "size": 0,
      "filename": "aic-ade_${VERSION}_amd64.deb",
      "type": "deb"
    },
    "win32": {
      "downloadUrl": "https://github.com/Deriest/ai-company/releases/download/v${VERSION}/AIC-ADE%20Setup%20v${VERSION}.exe",
      "sha256": "TO_BE_GENERATED",
      "size": 0,
      "filename": "AIC-ADE Setup v${VERSION}.exe",
      "type": "nsis"
    }
  }
}
EOF

echo "✅ latest.json created (SHA256 will be updated after upload)"

# Step 6: Git commit & push
git add .
git commit -m "fix: resolve blank screen issue on fresh install

- Added proper error handling in useBoot.ts for IPC connection failures
- Shows actionable error message instead of stuck loading state  
- Provides fetchErrorCount tracking for better debugging
- Clear error messages when backend engine cannot start

Fixes: Black screen on app launch after fresh installation"
git push origin main

echo ""
echo "🎉 QUICK BUILD COMPLETE!"
echo ""
echo "Next steps:"
echo "1. Upload artifacts to GitHub Release: https://github.com/Deriest/ai-company/releases/new"
echo "2. Tag: v${VERSION}"
echo "3. Files from: $APP_DIR/dist/"
echo ""
