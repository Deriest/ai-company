#!/bin/bash
# Generate Ed25519 keypair for update manifest signing
# Run this once during build, keep private key secret!

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")/.."
SECRETS_DIR="$PROJECT_ROOT/secrets"

mkdir -p "$SECRETS_DIR"

PRIVATE_KEY="$SECRETS_DIR/release_private_key.pem"
PUBLIC_KEY="$SECRETS_DIR/release_public_key.pub"

if [ -f "$PRIVATE_KEY" ]; then
    echo "⚠️  Private key already exists at $PRIVATE_KEY"
    echo "To regenerate: rm $PRIVATE_KEY $PUBLIC_KEY && $0"
    exit 0
fi

echo "🔑 Generating new Ed25519 signing keypair..."

# Generate Ed25519 keypair using openssl (requires OpenSSL 3.x)
openssl genpkey -algorithm ED25519 -out "$PRIVATE_KEY" 2>/dev/null

# Extract public key in PEM format
openssl pkey -in "$PRIVATE_KEY" -pubout -out "$PUBLIC_KEY" 2>/dev/null

chmod 600 "$PRIVATE_KEY"  # Owner read/write only for security
chmod 644 "$PUBLIC_KEY"

echo "✅ Generated keys:"
echo "   Private: $PRIVATE_KEY (SECURE - never commit)"
echo "   Public:  $PUBLIC_KEY (embed in production binary)"

echo ""
echo "📋 Next steps:"
echo "   1. Copy public key to app/src/shared/updateSecurity.ts PUBLIC_KEY_BASE64"
echo "   2. Keep private key secure and only use during release builds"
echo "   3. Add secrets/ to .gitignore (already should be there)"

# Show public key for easy copying
echo ""
echo "📄 Public key content (copy to updateSecurity.ts):"
cat "$PUBLIC_KEY" | head -c 1000
echo ""
