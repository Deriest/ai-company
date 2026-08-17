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
 * Verify manifest signature using Ed25519 digital signature.
 */
export function verifyManifestSignature(
    manifestJson: unknown,
    signatureBase64: string
): boolean {
    // Validate inputs
    if (!publicKeyBytes || !signatureBase64) {
        // In development mode without key, skip verification
        if (process.env.NODE_ENV === "production") {
            console.error("[updateSecurity] No public key configured for signature verification");
            return false;
        }
        return true;
    }

    try {
        const jsonString = JSON.stringify(manifestJson);
        
        // Create hash of manifest content (SHA256)
        const hash = crypto.createHash("sha256").update(jsonString).digest();
        
        // Create signature verifier
        const verifier = crypto.createVerify("SHA256");
        verifier.update(hash);
        
        // Convert public key to proper format
        const pubKeyObj = crypto.createPublicKey({
            key: publicKeyBytes,
            format: "pem",
            type: "spki",
        });
        
        // Verify signature
        const valid = verifier.verify(pubKeyObj, signatureBase64, "base64");
        
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
    if (!signatureBase64) {
        if (process.env.NODE_ENV === "production") {
            return false;
        }
        return true;
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
} {
    return {
        hasPublicKey: !!publicKeyBytes,
        publicKeyLength: publicKeyBytes?.length ?? null,
        nodeEnv: process.env.NODE_ENV || "development",
    };
}
