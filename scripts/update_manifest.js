#!/usr/bin/env node
/**
 * Update latest.json with real artifact hashes from release directory.
 * Usage: node update_manifest.js <latest.json> <release_dir>
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const [_, __, manifestPath, releaseDir] = process.argv;

if (!manifestPath || !releaseDir) {
  console.error('Usage: node update_manifest.js <latest.json> <release_dir>');
  process.exit(1);
}

const releaseDirPath = path.resolve(process.cwd(), releaseDir);
const files = fs.readdirSync(releaseDirPath);

// Find artifacts
let exeFile = null, appImageFile = null, debFile = null;

for (const file of files) {
  if (file.endsWith('.exe')) exeFile = file;
  else if (file.endsWith('.AppImage')) appImageFile = file;
  else if (file.endsWith('.deb')) debFile = file;
}

if (!exeFile || !appImageFile || !debFile) {
  console.error('Missing artifacts in release dir:', {
    exe: exeFile,
    appImage: appImageFile,
    deb: debFile
  });
  process.exit(1);
}

console.log(`Found artifacts: ${exeFile}, ${appImageFile}, ${debFile}`);

const calculateSha256 = (filePath) => {
  const content = fs.readFileSync(filePath);
  return crypto.createHash('sha256').update(content).digest('hex');
};

const calculateSize = (filePath) => fs.statSync(filePath).size;

// Read or create latest.json structure
const latestJsonPath = path.resolve(process.cwd(), manifestPath);
const latestData = JSON.parse(fs.readFileSync(latestJsonPath, 'utf8'));

latestData.platforms.win32.downloadUrl = `https://github.com/Deriest/ai-company/releases/download/v${latestData.version}/${exeFile}`;
latestData.platforms.win32.sha256 = calculateSha256(path.join(releaseDirPath, exeFile));
latestData.platforms.win32.size = calculateSize(path.join(releaseDirPath, exeFile));
latestData.platforms.win32.filename = exeFile;

latestData.platforms.linux.downloadUrl = `https://github.com/Deriest/ai-company/releases/download/v${latestData.version}/${appImageFile}`;
latestData.platforms.linux.sha256 = calculateSha256(path.join(releaseDirPath, appImageFile));
latestData.platforms.linux.size = calculateSize(path.join(releaseDirPath, appImageFile));
latestData.platforms.linux.filename = appImageFile;

latestData.platforms['linux-deb'].downloadUrl = `https://github.com/Deriest/ai-company/releases/download/v${latestData.version}/${debFile}`;
latestData.platforms['linux-deb'].sha256 = calculateSha256(path.join(releaseDirPath, debFile));
latestData.platforms['linux-deb'].size = calculateSize(path.join(releaseDirPath, debFile));
latestData.platforms['linux-deb'].filename = debFile;

fs.writeFileSync(latestJsonPath, JSON.stringify(latestData, null, 2) + '\n');
console.log('✅ Manifest updated with real hashes');
