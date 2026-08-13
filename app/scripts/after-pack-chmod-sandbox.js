// electron-builder afterPack hook: ensure the SUID sandbox helper is correct in
// the unpacked app so the packaged AppImage/deb has a working chrome-sandbox.
// Runs on every linux pack AFTER appOutDir is populated but BEFORE AppImage/deb
// are assembled — a post-build chmod can never reach the archive.
const fs = require("node:fs");
const path = require("node:path");

exports.default = async function afterPack(context) {
  if (context.electronPlatformName !== "linux") return;
  const sandbox = path.join(context.appOutDir, "chrome-sandbox");
  if (!fs.existsSync(sandbox)) return;
  try {
    // Best effort: SUID 4755 requires root. On error we log and continue — the
    // main-process --no-sandbox path still lets the app run.
    fs.chmodSync(sandbox, 0o4755);
    console.log("afterPack: chrome-sandbox SUID 4755 set ->", sandbox);
  } catch (e) {
    console.log("afterPack: WARNING could not set SUID on chrome-sandbox:", e.message);
  }
};