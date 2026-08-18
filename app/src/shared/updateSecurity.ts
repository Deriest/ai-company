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
 * 
 * Matches signer.js canonicalization: SHA256 over JSON.stringify(JSON.parse(raw))
 * Uses JWK "OKP/Ed25519" format with raw 32-byte public point for verification.
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
    
    // Use baked public key or env override for production builds
    const BAKED_UPDATE_PUBLIC_KEY = "fXxYzXuiMkeMi4u7obc7RmJI07Whuvewlkl308ThH+o=";
    const publicKeyBase64 = process.env.AIC_UPDATE_PUBLIC_KEY || BAKED_UPDATE_PUBLIC_KEY;
    
    if (!publicKeyBase64) {
        if (allowUnsigned()) return true;
        console.error("[updateSecurity] No public key configured for signature verification");
        return false;
    }

    try {
        const jsonString = JSON.stringify(manifestJson);
        
        // Parse the base64 public key to get raw 32 bytes
        const rawPubKey = Buffer.from(publicKeyBase64, "base64");
        
        // Build JWK object matching signer's derivation
        const pubKeyObj = crypto.createPublicKey({
            key: { kty: "OKP", crv: "Ed25519", x: rawPubKey.toString("base64url") },
            format: "jwk",
            type: "spki",
        });

        // Ed25519 PureEdDSA: verify over the 32-byte SHA256 DIGEST directly
        const hash = crypto.createHash("sha256").update(jsonString).digest();
        const valid = crypto.verify(null, hash, pubKeyObj, Buffer.from(signatureBase64, "base64"));

        if (!valid) {
            console.error("[updateSecurity] Manifest signature verification FAILED");
        }

        return valid;
    } catch (e: unknown) {
        console.error("[updateSecurity] Signature verification error:", String(e));
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
