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

function allowUnsigned(): boolean {
    if (process.env.AIC_UPDATE_ALLOW_UNSIGNED === "1") return true;
    return process.env.NODE_ENV !== "production";
}

/**
 * Verify manifest signature using Ed25519 digital signature.
 */
export function verifyManifestSignature(
    manifestJson: unknown,
    signatureBase64: string
): boolean {
    if (!signatureBase64) {
        if (allowUnsigned()) return true;
        console.error("[updateSecurity] No signature provided for manifest verification");
        return false;
    }
    if (!publicKeyBytes) {
        if (allowUnsigned()) return true;
        console.error("[updateSecurity] No public key configured for signature verification");
        return false;
    }

    try {
        const jsonString = JSON.stringify(manifestJson);
        const verifier = crypto.createVerify("SHA256");
        verifier.update(jsonString);

        const pubKeyObj = crypto.createPublicKey({
            key: publicKeyBytes,
            format: "der",
            type: "spki",
        });

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
        if (allowUnsigned()) return true;
        return false;
    }

    try {
        const jsonString = JSON.stringify(manifestJson);
        const verifier = crypto.createVerify("SHA256");
        verifier.update(jsonString);

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
        allowUnsigned: allowUnsigned(),
    };
}
