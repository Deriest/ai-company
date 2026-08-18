const fs = require("node:fs");
const crypto = require("node:crypto");

const manifestJson = JSON.parse(fs.readFileSync("latest.json", "utf8"));
const sigBase64 = fs.readFileSync("latest.json.sig", "utf8").trim();

const BAKED_UPDATE_PUBLIC_KEY = "fXxYzXuiMkeMi4u7obc7RmJI07Whuvewlkl308ThH+o=";
const publicKeyBase64 = BAKED_UPDATE_PUBLIC_KEY;

console.log("=== MANIFEST SIGNATURE VERIFICATION TEST ===");

try {
    const jsonString = JSON.stringify(manifestJson);

    const rawPubKey = Buffer.from(publicKeyBase64, "base64");
    console.log("Raw public key bytes:", rawPubKey.length);

    const pubKeyObj = crypto.createPublicKey({
        key: { kty: "OKP", crv: "Ed25519", x: rawPubKey.toString("base64url") },
        format: "jwk",
        type: "spki",
    });

    console.log("OK: JWK object created");

    const hash = crypto.createHash("sha256").update(jsonString).digest();
    console.log("SHA256 hash:", hash.toString("hex").slice(0, 32));

    const valid = crypto.verify(null, hash, pubKeyObj, Buffer.from(sigBase64, "base64"));

    if (valid) {
        console.log("RESULT: SIGNATURE VERIFIED - VALID");
    } else {
        console.log("RESULT: SIGNATURE FAILED - INVALID");
        process.exit(1);
    }
} catch (e) {
    console.error("ERROR:", e.message);
    process.exit(1);
}
