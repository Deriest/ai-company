// Generate AIC_JWT_SECRET and create .env file
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

console.log("=== AIC_JWT_SECRET GENERATION ===\n");

// Generate random 64-char hex secret (256-bit)
const jwtSecret = crypto.randomBytes(32).toString('hex');
console.log(`Generated JWT Secret: ${jwtSecret}\n`);

console.log("⚠️  IMPORTANT: Store this securely!");
console.log("   • Never commit to Git\n");
console.log("   • Set as environment variable in production\n");
console.log("   • Keep backup of this value\n");

// Write to .env file (if it exists) or create suggestion
const envPath = path.join(__dirname, ".env");

// Check if .env already has the secret
let existingSecret = null;
try {
    const envContent = fs.readFileSync(envPath, "utf-8");
    const match = envContent.match(/^AIC_JWT_SECRET=([^\n]+)$/m);
    if (match) {
        existingSecret = match[1];
        console.log("\nFound existing AIC_JWT_SECRET in .env");
    }
} catch (e) {
    // .env doesn't exist or can't be read
}

if (!existingSecret) {
    console.log("\nTo set the secret, add to your .env file:");
    console.log(`\n# Create or edit .env file:`);
    console.log("AIC_JWT_SECRET=" + jwtSecret);
} else {
    console.log("\n✅ .env file already configured");
}

console.log("\n--- How to use in production ---");
console.log("\nLinux/Mac:");
console.log("  export AIC_JWT_SECRET=\"" + jwtSecret + "\"");
console.log("  npm start");
console.log("");
console.log("Windows:");
console.log("  $env:AIC_JWT_SECRET=\""+jwtSecret+"\"");
console.log("  npm start");
console.log("");
console.log(".env file method:");
console.log("  echo \"AIC_JWT_SECRET="+jwtSecret+"\" > .env");
console.log("  node server.js");
console.log("");

// Also show where backend might be looking for config
const appDataDir = require("os").homedir();
const aicDir = path.join(appDataDir, "AppData", "Roaming", "aic-ade");

console.log("Likely locations for .env configuration:");
console.log("  • ./ai-company/.env");
console.log("  • " + aicDir + "/.env");
console.log("");

// Save to temp file for easy copy-paste
const savedPath = path.join(__dirname, "generated-secret.txt");
fs.writeFileSync(savedPath, `
# AIC-ADE JWT SECRET (generated ${new Date().toISOString()})
# Copy this value and set as environment variable:

export AIC_JWT_SECRET=${jwtSecret}

# Or add to .env file:
# AIC_JWT_SECRET=${jwtSecret}
`.trim());

console.log(`Saved temporary instructions to: generated-secret.txt`);
console.log("\nDone!");
