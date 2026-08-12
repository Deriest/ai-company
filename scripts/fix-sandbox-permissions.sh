#!/bin/bash
# ============================================================================
# Fix Chrome Sandbox Permissions for AIC-ADE AppImage
# ============================================================================

set -euo pipefail

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Fix Chrome Sandbox Permissions                          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

APPIMAGE="/home/tvd/AI-Company/app/dist/AIC-ADE-2.6.9.AppImage"

if [ ! -f "$APPIMAGE" ]; then
    echo "❌ AppImage not found at $APPIMAGE"
    exit 1
fi

echo "Extracting AppImage..."
"$APPIMAGE" --appimage-extract
cd squashfs-root

echo ""
echo "🔧 Fixing permissions..."

# Fix chrome-sandbox ownership and mode
echo "   • Setting chrome-sandbox owner to root"
chown root:root ./chrome-sandbox

echo "   • Setting chrome-sandbox mode to 4755 (suid)"
chmod 4755 ./chrome-sandbox

echo ""
echo "✅ Permissions fixed!"
echo ""
echo "To test:"
echo "  cd squashfs-root"
echo "  ./aic-ade"
echo ""
echo "Or rebuild with correct permissions in electron-builder config"
