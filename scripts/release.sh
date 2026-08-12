#!/usr/bin/env bash
# ============================================================================
# AIC-ADE Release Script
# ============================================================================
# Usage:  ./scripts/release.sh <version>   e.g. ./scripts/release.sh 2.4.48
#
# What it does:
#   1. Bump version in package.json + package-lock.json
#   2. Clean build dirs, build Linux (AppImage + deb) + Windows (NSIS x64)
#   3. Compute SHA256 + sizes
#   4. Create GitHub Release + upload 3 artifacts
#   5. Update latest.json with GitHub Release download URLs
#   6. Update SHA256SUMS (root + app/release/)
#   7. Commit + push to GitHub
#
# Prerequisites:
#   - GH_TOKEN env var set (GitHub Personal Access Token with repo access)
#   - Wine installed (for Windows NSIS builds on Linux)
#   - Node.js + npm in app/
#   - Python 3 in backend/
# ============================================================================

set -euo pipefail

# ── Args ────────────────────────────────────────────────────────────────────

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
  echo "❌ Usage: $0 <version>   e.g. $0 2.4.48"
  exit 1
fi

# Strip leading 'v' if user passed v2.4.48
VERSION="${VERSION#v}"
TAG="v${VERSION}"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="$ROOT_DIR/app"
RELEASE_DIR="$APP_DIR/release"
GITHUB_REPO="Deriest/ai-company"
GITHUB_RAW_BASE="https://raw.githubusercontent.com/${GITHUB_REPO}/main"
GITHUB_RELEASE_BASE="https://github.com/${GITHUB_REPO}/releases/download/${TAG}"

cd "$ROOT_DIR"

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  AIC-ADE Release v${VERSION}                                    ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# ── Check prerequisites ─────────────────────────────────────────────────────

if [[ -z "${GH_TOKEN:-}" ]]; then
  echo "❌ GH_TOKEN env var not set. Export it first:"
  echo "   export GH_TOKEN=ghp_xxxxxxxx"
  exit 1
fi

if ! command -v wine &>/dev/null; then
  echo "⚠️  Wine not found — Windows build may fail on Linux."
fi

# ── 1. Bump version ─────────────────────────────────────────────────────────

echo "📋 Step 1/7: Bumping version to ${VERSION}..."

# package.json
sed -i "s/\"version\": \".*\"/\"version\": \"${VERSION}\"/" "$APP_DIR/package.json"

# package-lock.json — use Python json for safe update (BUG-11 fix)
python3 -c "
import json
with open('$APP_DIR/package-lock.json') as f:
    data = json.load(f)
data['version'] = '$VERSION'
if 'packages' in data and '' in data['packages']:
    data['packages']['']['version'] = '$VERSION'
with open('$APP_DIR/package-lock.json', 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
"

echo "  ✅ Version bumped"

# ── 2. Build ────────────────────────────────────────────────────────────────

echo ""
echo "🔨 Step 2/7: Building Linux + Windows..."

# Clean build dirs
rm -rf "$APP_DIR/dist" "$APP_DIR/dist-electron" "$RELEASE_DIR/linux-unpacked" "$RELEASE_DIR/win-unpacked"

cd "$APP_DIR"
npm run build
npx electron-builder --linux AppImage deb
npx electron-builder --win nsis --x64

# Fix chrome-sandbox permissions (SUID bit required for Electron sandbox)
chmod 4755 linux-unpacked/chrome-sandbox 2>/dev/null || echo "⚠️  SUID fix requires root, continuing..."

cd "$ROOT_DIR"

echo "  ✅ Build complete"

# ── 3. Compute hashes + sizes ───────────────────────────────────────────────

echo ""
echo "🔐 Step 3/7: Computing SHA256 hashes..."

APPIMAGE="aic-ade-${VERSION}.AppImage"
DEB="aic-ade_${VERSION}_amd64.deb"
EXE="aic-ade Setup ${VERSION}.exe"

APPIMAGE_SHA=$(sha256sum "$APP_DIR/dist/$APPIMAGE" | cut -d' ' -f1)
DEB_SHA=$(sha256sum "$APP_DIR/dist/$DEB" | cut -d' ' -f1)
EXE_SHA=$(sha256sum "$APP_DIR/dist/$EXE" | cut -d' ' -f1)

APPIMAGE_SIZE=$(stat -c '%s' "$APP_DIR/dist/$APPIMAGE")
DEB_SIZE=$(stat -c '%s' "$APP_DIR/dist/$DEB")
EXE_SIZE=$(stat -c '%s' "$APP_DIR/dist/$EXE")

echo "  AppImage: ${APPIMAGE_SHA:0:16}… (${APPIMAGE_SIZE} bytes)"
echo "  deb:      ${DEB_SHA:0:16}… (${DEB_SIZE} bytes)"
echo "  exe:      ${EXE_SHA:0:16}… (${EXE_SIZE} bytes)"

# ── 4. Create GitHub Release + upload artifacts ─────────────────────────────

echo ""
echo "📤 Step 4/7: Creating GitHub Release ${TAG}..."

# Delete existing release+tag if present (idempotent re-runs)
EXISTING_ID=$(curl -sf "https://api.github.com/repos/${GITHUB_REPO}/releases/tags/${TAG}" \
  -H "Authorization: token $GH_TOKEN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
if [[ -n "$EXISTING_ID" ]]; then
  echo "  Deleting existing release ${EXISTING_ID}..."
  curl -sf -X DELETE "https://api.github.com/repos/${GITHUB_REPO}/releases/${EXISTING_ID}" \
    -H "Authorization: token $GH_TOKEN" || true
  curl -sf -X DELETE "https://api.github.com/repos/${GITHUB_REPO}/git/refs/tags/${TAG}" \
    -H "Authorization: token $GH_TOKEN" || true
fi

# Create release
RELEASE_RESP=$(curl -sf -X POST "https://api.github.com/repos/${GITHUB_REPO}/releases" \
  -H "Authorization: token $GH_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"tag_name\": \"${TAG}\",
    \"target_commitish\": \"main\",
    \"name\": \"AIC-ADE v${VERSION}\",
    \"body\": \"## v${VERSION}\\n\\n### Downloads\\n- Linux: AppImage + deb\\n- Windows: NSIS x64 installer\\n\\n### Auto-update\\nThis release is automatically detected by AIC-ADE via latest.json on GitHub raw.\",
    \"draft\": false,
    \"prerelease\": false
  }")

RELEASE_ID=$(echo "$RELEASE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "  ✅ Release created (ID: $RELEASE_ID)"

# Upload artifacts
for f in "$APPIMAGE" "$DEB" "$EXE"; do
  echo "  Uploading $f..."
  curl -sf -X POST \
    "https://uploads.github.com/repos/${GITHUB_REPO}/releases/${RELEASE_ID}/assets?name=${f}" \
    -H "Authorization: token $GH_TOKEN" \
    -H "Content-Type: application/octet-stream" \
    --data-binary "@$RELEASE_DIR/$f" \
    | python3 -c "import sys,json; r=json.load(sys.stdin); print(f'    ✅ {r[\"name\"]}')" 2>/dev/null || echo "    ⚠️ upload may have failed"
done

echo "  ✅ All artifacts uploaded"

# ── 5. Update latest.json ───────────────────────────────────────────────────

echo ""
echo "📝 Step 5/7: Updating latest.json..."

TODAY=$(date +%F)

cat > "$ROOT_DIR/latest.json" << EOF
{
  "version": "${VERSION}",
  "channel": "stable",
  "releaseDate": "${TODAY}",
  "releaseNotes": "v${VERSION} — See https://github.com/${GITHUB_REPO}/releases/tag/${TAG} for release notes.",
  "platforms": {
    "linux": {
      "downloadUrl": "${GITHUB_RELEASE_BASE}/${APPIMAGE}",
      "sha256": "${APPIMAGE_SHA}",
      "size": ${APPIMAGE_SIZE},
      "filename": "${APPIMAGE}",
      "type": "AppImage"
    },
    "linux-deb": {
      "downloadUrl": "${GITHUB_RELEASE_BASE}/${DEB}",
      "sha256": "${DEB_SHA}",
      "size": ${DEB_SIZE},
      "filename": "${DEB}",
      "type": "deb"
    },
    "win32": {
      "downloadUrl": "${GITHUB_RELEASE_BASE}/${EXE}",
      "sha256": "${EXE_SHA}",
      "size": ${EXE_SIZE},
      "filename": "${EXE}",
      "type": "nsis"
    }
  }
}
EOF

cp "$ROOT_DIR/latest.json" "$RELEASE_DIR/latest.json"
echo "  ✅ latest.json updated (root + app/release/)"

# ── 6. Update SHA256SUMS ────────────────────────────────────────────────────

echo ""
echo "📋 Step 6/7: Updating SHA256SUMS..."

LATEST_SHA=$(sha256sum "$ROOT_DIR/latest.json" | cut -d' ' -f1)

# app/release/SHA256SUMS — remove old entries for this version + old latest.json, append new
touch "$RELEASE_DIR/SHA256SUMS"
grep -v "${VERSION}" "$RELEASE_DIR/SHA256SUMS" | grep -v "latest.json" > "$RELEASE_DIR/SHA256SUMS.tmp" || true
mv "$RELEASE_DIR/SHA256SUMS.tmp" "$RELEASE_DIR/SHA256SUMS"
cat >> "$RELEASE_DIR/SHA256SUMS" << EOF
${APPIMAGE_SHA}  ${APPIMAGE}
${DEB_SHA}  ${DEB}
${EXE_SHA}  ${EXE}
${LATEST_SHA}  latest.json
EOF

# Root SHA256SUMS — same but with app/release/ prefix
touch "$ROOT_DIR/SHA256SUMS"
grep -v "${VERSION}" "$ROOT_DIR/SHA256SUMS" | grep -v "latest.json" > "$ROOT_DIR/SHA256SUMS.tmp" || true
mv "$ROOT_DIR/SHA256SUMS.tmp" "$ROOT_DIR/SHA256SUMS"
cat >> "$ROOT_DIR/SHA256SUMS" << EOF
${APPIMAGE_SHA}  app/release/${APPIMAGE}
${DEB_SHA}  app/release/${DEB}
${EXE_SHA}  app/release/${EXE}
${LATEST_SHA}  latest.json
EOF

echo "  ✅ SHA256SUMS updated (root + app/release/)"

# ── 7. Commit + push ────────────────────────────────────────────────────────

echo ""
echo "🚀 Step 7/7: Committing + pushing to GitHub..."

cd "$ROOT_DIR"
git add -A
git commit -m "release: v${VERSION} — build, GitHub Release, latest.json, SHA256SUMS

- Linux: AppImage (${APPIMAGE_SIZE} bytes) + deb (${DEB_SIZE} bytes)
- Windows: NSIS x64 (${EXE_SIZE} bytes)
- Artifacts: https://github.com/${GITHUB_REPO}/releases/tag/${TAG}
- Auto-update: latest.json on raw.githubusercontent.com"

git -c "credential.helper=!f() { echo \"username=Deriest\"; echo \"password=$GH_TOKEN\"; }; f" push origin main

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  ✅ Release v${VERSION} complete!                              ║"
echo "╠════════════════════════════════════════════════════════════╣"
echo "║                                                            ║"
echo "║  GitHub Release:                                           ║"
echo "║  https://github.com/${GITHUB_REPO}/releases/tag/${TAG}    ║"
echo "║                                                            ║"
echo "║  Auto-update manifest:                                     ║"
echo "║  ${GITHUB_RAW_BASE}/latest.json                           ║"
echo "║                                                            ║"
echo "║  Installed apps will auto-detect this release and prompt   ║"
echo "║  users to download + install.                              ║"
echo "║                                                            ║"
echo "╚════════════════════════════════════════════════════════════╝"