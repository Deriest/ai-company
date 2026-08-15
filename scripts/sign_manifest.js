#!/usr/bin/env node
/**
 * Sign an update manifest (latest.json) with the Ed25519 release private key.
 *
 * CRITICAL — canonicalization must match the verifier exactly.
 * app/src/shared/updateSecurity.ts:verifyManifestSignature() computes:
 *     hash = sha256( JSON.stringify( JSON.parse(manifestBytes) ) )
 *     crypto.verify(null, hash, publicKey, signature)
 * so we MUST parse + re-stringify with the same Node JSON.stringify (no
 * pretty-printing) and sign the sha256 DIGEST (Ed25519 PureEdDSA over the
 * 32-byte hash), then emit the signature base64 to <manifest>.sig.
 *
 * Usage:
 *   node scripts/sign_manifest.js <manifest.json> <private_key.pem> [out.sig]
 *
 * Exit codes: 0 ok, 1 usage/error.
 */
"use strict";

const fs = require("node:fs");
const crypto = require("node:crypto");

function die(msg) {
  console.error(`[sign_manifest] ${msg}`);
  process.exit(1);
}

const [, , manifestPath, keyPath, outPathArg] = process.argv;
if (!manifestPath || !keyPath) {
  die("usage: node scripts/sign_manifest.js <manifest.json> <private_key.pem> [out.sig]");
}
const outPath = outPathArg || `${manifestPath}.sig`;

let manifestBytes;
try {
  manifestBytes = fs.readFileSync(manifestPath, "utf8");
} catch (e) {
  die(`cannot read manifest ${manifestPath}: ${e.message}`);
}

let parsed;
try {
  parsed = JSON.parse(manifestBytes);
} catch (e) {
  die(`manifest is not valid JSON: ${e.message}`);
}

// Canonical form = exactly what the verifier hashes.
const canonical = JSON.stringify(parsed);
const hash = crypto.createHash("sha256").update(canonical).digest();

let privateKey;
try {
  privateKey = crypto.createPrivateKey(fs.readFileSync(keyPath));
} catch (e) {
  die(`cannot load private key ${keyPath}: ${e.message}`);
}
if (privateKey.asymmetricKeyType !== "ed25519") {
  die(`private key must be Ed25519, got ${privateKey.asymmetricKeyType}`);
}

// Ed25519 is PureEdDSA — sign the digest bytes directly (algorithm=null),
// mirroring crypto.verify(null, hash, pubKey, sig) in the verifier.
const signature = crypto.sign(null, hash, privateKey);
fs.writeFileSync(outPath, signature.toString("base64"));

// Self-check: derive the raw public key and verify our own signature so a
// release never ships a manifest the client would reject.
const pubDer = crypto.createPublicKey(privateKey).export({ format: "der", type: "spki" });
// Ed25519 SPKI DER is a fixed 44-byte structure; the raw 32-byte key is the tail.
const rawPub = pubDer.subarray(pubDer.length - 32);
const pubKeyObj = crypto.createPublicKey({
  key: { kty: "OKP", crv: "Ed25519", x: rawPub.toString("base64url") },
  format: "jwk",
});
const ok = crypto.verify(null, hash, pubKeyObj, signature);
if (!ok) {
  die("self-verification FAILED — signature would be rejected by clients");
}

console.log(`[sign_manifest] wrote ${outPath} (${signature.length} bytes, self-verify OK)`);
console.log(`[sign_manifest] AIC_UPDATE_PUBLIC_KEY=${rawPub.toString("base64")}`);
