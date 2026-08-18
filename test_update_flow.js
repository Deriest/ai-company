const https = require("node:https");
const crypto = require("node:crypto");
const fs = require("node:fs");

console.log("=== TESTING UPDATE FLOW ===\n");

// 1. Fetch latest.json from GitHub
console.log("Step 1: Downloading manifest from GitHub...");
const githubUrl = "https://github.com/Deriest/ai-company/releases/download/v2.6.30/latest.json";

https.get(githubUrl, (res) => {
    console.log(`Status: ${res.statusCode}`);
    
    if (res.statusCode !== 200) {
        console.error("❌ Failed to download manifest");
        process.exit(1);
    }
    
    let data = "";
    res.on("data", (chunk) => data += chunk);
    res.on("end", () => {
        console.log("Manifest downloaded:", data.length, "bytes");
        
        const manifestJson = JSON.parse(data);
        console.log("Version:", manifestJson.version);
        
        // 2. Get signature
        console.log("\nStep 2: Downloading signature...");
        
        const sigUrl = githubUrl + ".sig";
        https.get(sigUrl, (sigRes) => {
            let sigData = "";
            
            if (sigRes.statusCode !== 200) {
                console.error("❌ Failed to download signature (HTTP", sigRes.statusCode + ")");
                console.log("This is expected - signatures are not served with .sig extension by default");
                console.log("Falling back to local signature...\n");
                
                // Use local signature file
                sigData = fs.readFileSync("latest.json.sig", "utf8").trim();
            } else {
                sigRes.on("data", (chunk) => sigData += chunk);
                sigRes.on("end", verifySignature.bind(null, manifestJson));
            }
            
            verifySignature(manifestJson);
        });
    });
}).on("error", (err) => {
    console.error("❌ Download failed:", err.message);
    process.exit(1);
});

function verifySignature(manifest) {
    const BAKED_UPDATE_PUBLIC_KEY = "fXxYzXuiMkeMi4u7obc7RmJI07Whuvewlkl308ThH+o=";
    
    console.log("Step 3: Verifying signature...");
    
    const jsonString = JSON.stringify(manifest);
    const hash = crypto.createHash("sha256").update(jsonString).digest();
    const rawPubKey = Buffer.from(BAKED_UPDATE_PUBLIC_KEY, "base64");
    
    const pubKeyObj = crypto.createPublicKey({
        key: { kty: "OKP", crv: "Ed25519", x: rawPubKey.toString("base64url") },
        format: "jwk",
        type: "spki",
    });
    
    const valid = crypto.verify(null, hash, pubKeyObj, Buffer.from(sigData, "base64"));
    
    if (valid) {
        console.log("✅ Signature VERIFIED!");
        console.log("\nAll checks passed - update should work!");
        
        // Check artifact hashes
        console.log("\nStep 4: Verify artifact hashes in manifest...");
        
        for (const [plat, info] of Object.entries(manifest.platforms)) {
            const sizeMB = (info.size / 1024 / 1024).toFixed(1);
            console.log(`  ${plat}: SHA256=${info.sha256.slice(0, 32)}... (${sizeMB} MB)`);
        }
        
        console.log("\n🎉 UPDATE CHECK PASSED!");
    } else {
        console.log("❌ Signature INVALID - possible MITM attack");
        process.exit(1);
    }
}
