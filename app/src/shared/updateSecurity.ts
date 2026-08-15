/**
 * Update Manifest Cryptographic Signature Verification
 * 
 * Protects against MITM attacks by verifying manifests are signed with
 * Ed25519 asymmetric keys. Public key is embedded in production builds.
 */

import * as crypto from "node:crypto";

// ── PUBLIC KEY (Ed25519) ──────────────────────────────────
// This key should be generated once during build and baked into the binary.
// For development/testing, replace with your own public key or use mock.

// C2 FIX: Bake Ed25519 public key as a source constant for packaged builds.
// Set AIC_UPDATE_PUBLIC_KEY at build time (electron-builder --extraMetadata or env).
// Packaged Electron does NOT reliably set NODE_ENV=production, so verification
// MUST use app.isPackaged semantics. The consumer (updateManager) passes
// isPackaged explicitly; this module also falls back to NODE_ENV for tests.
const PUBLIC_KEY_BASE64 = process.env.AIC_UPDATE_PUBLIC_KEY || "";

// Parse base64 public key if available
let publicKeyBytes: Buffer | null = null;
if (PUBLIC_KEY_BASE64) {
    try {
        publicKeyBytes = Buffer.from(PUBLIC_KEY_BASE64, "base64");
    } catch (e) {
        console.warn("[updateSecurity] Failed to parse public key:", e);
    }
}

/**
 * Returns true if the current runtime is considered "packaged" (production).
 * In Electron: app.isPackaged. In tests/CI: NODE_ENV=production.
 * Exposed so callers can inject the Electron check.
 */
export function isPackagedRuntime(isPackaged?: boolean): boolean {
    if (typeof isPackaged === "boolean") return isPackaged;
    return (process.env.NODE_ENV || "development") === "production";
}

/**
 * Verify manifest signature using Ed25519 digital signature.
 */
export function verifyManifestSignature(
    manifestJson: unknown,
    signatureBase64: string,
    isPackaged?: boolean
): boolean {
    // Validate inputs
    if (!publicKeyBytes || !signatureBase64) {
        const packaged = isPackagedRuntime(isPackaged);
        if (packaged) {
            console.error("[updateSecurity] Packaged build requires signed manifests — rejecting unsigned manifest");
            return false;
        }
        // Non-packaged: unsigned manifests are opt-in only (H4). Dev builds
        // that want them must set AIC_UPDATE_ALLOW_UNSIGNED=1 explicitly.
        // Test env (vitest NODE_ENV=test) uses unsigned mock manifests — allow
        // there, plus the explicit dev opt-in flag. Production stays fail-closed.
        const allowUnsigned =
            process.env.AIC_UPDATE_ALLOW_UNSIGNED === "1" ||
            process.env.NODE_ENV === "test";
        if (allowUnsigned) {
            console.warn("[updateSecurity] Unsigned manifest accepted (test/dev mode)");
            return true;
        }
        console.error("[updateSecurity] Unsigned manifest rejected — set AIC_UPDATE_ALLOW_UNSIGNED=1 for dev");
        return false;
    }

    try {
        const jsonString = JSON.stringify(manifestJson);
        
        // Create hash of manifest content (SHA256)
        const hash = crypto.createHash("sha256").update(jsonString).digest();
        
        // Create signature verifier with correct Ed25519 format
        // Ed25519 keys are raw 32-byte public keys, not PEM-encoded SPKI
        const pubKeyObj = crypto.createPublicKey({
            key: {
                kty: "OKP",
                crv: "Ed25519",
                x: Buffer.from(publicKeyBytes).toString("base64"),
            },
            format: "jwk",
        });
        
        // Verify signature
        const valid = crypto.verify(null, hash, pubKeyObj, Buffer.from(signatureBase64, "base64"));
        
        if (!valid) {
            console.error(
                "[updateSecurity] Manifest signature verification FAILED"
            );
        }
        
        return valid;
    } catch (e) {
        console.error("[updateSecurity] Signature verification error:", e);
        return false;
    }
}

/**
 * Verify RSA signature (alternative for backwards compatibility).
 */
export function verifyRSASignature(
    manifestJson: unknown,
    signatureBase64: string,
    rsaPublicKeyPem: string
): boolean {
    // M12: legacy helper kept for API compatibility, aligned with the
    // fail-closed policy — unsigned manifests are opt-in via env flag only.
    if (!signatureBase64) {
        return process.env.AIC_UPDATE_ALLOW_UNSIGNED === "1";
    }

    try {
        const jsonString = JSON.stringify(manifestJson);
        const hash = crypto.createHash("sha256").update(jsonString).digest();
        
        const verifier = crypto.createVerify("SHA256");
        verifier.update(hash);
        
        const pubKeyObj = crypto.createPublicKey(rsaPublicKeyPem);
        return verifier.verify(pubKeyObj, signatureBase64, "base64");
    } catch (e) {
        console.error("[updateSecurity] RSA signature verification error:", e);
        return false;
    }
}

/**
 * Get current verification status for diagnostics.
 */
export function getVerificationStatus(): {
    hasPublicKey: boolean;
    publicKeyLength: number | null;
    nodeEnv: string;
    allowUnsigned: boolean;
} {
    return {
        hasPublicKey: !!publicKeyBytes,
        publicKeyLength: publicKeyBytes?.length ?? null,
        nodeEnv: process.env.NODE_ENV || "development",
        allowUnsigned: process.env.AIC_UPDATE_ALLOW_UNSIGNED === "1",
    };
}
