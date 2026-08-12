#!/bin/bash
# ============================================================================
# Fix chrome-sandbox permissions after electron builder finishes
# This ensures AppImage has correct SUID bits set for Electron sandbox
# ============================================================================

set -euo pipefail

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Fix Chrome Sandbox Permissions                          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if app was built (look for squashfs-root or unpacked dir)
if [ -d "squashfs-root" ]; then
    APP_DIR="squashfs-root"
elif [ -d "linux-unpacked" ]; then
    APP_DIR="linux-unpacked"
else
    echo "❌ No Electron build directory found"
    exit 1
fi

CHROME_SANDBOX="$APP_DIR/chrome-sandbox"

if [ ! -f "$CHROME_SANDBOX" ]; then
    echo "❌ chrome-sandbox not found at $CHROME_SANDBOX"
    exit 1
fi

echo "📍 Found chrome-sandbox: $CHROME_SANDBOX"

# Get current permissions
CURRENT_PERMS=$(stat -c "%a" "$CHROME_SANDBOX")
echo "   Current permissions: $CURRENT_PERMS ($(stat -c "%U:%G" "$CHROME_SANDBOX"))"

# Check if already has setuid bit
if [[ "$CURRENT_PERMS" =~ ^4 ]]; then
    echo "✅ Already has SUID bit (4755)"
    exit 0
fi

echo ""
echo "🔧 Setting SUID bit (chmod 4755)..."

# Try sudo first, fallback to direct chmod
if command -v sudo &> /dev/null && [[ "$(whoami)" != "root" ]]; then
    echo "   Using sudo (current user: $(whoami))"
    sudo chmod 4755 "$CHROME_SANDBOX"
    CHMOD_RESULT=$?
else
    echo "   Direct chmod (running as root or no sudo available)"
    chmod 4755 "$CHROME_SANDBOX"
    CHMOD_RESULT=$?
fi

if [ $CHMOD_RESULT -ne 0 ]; then
    echo "❌ Failed to set permissions: $?"
    exit 1
fi

NEW_PERMS=$(stat -c "%a" "$CHROME_SANDBOX")
echo "✅ New permissions: $NEW_PERPS ($(stat -c "%U:%G" "$CHROME_SANDBOX"))"

echo ""
echo "✨ Chrome sandbox is now ready for production use!"
