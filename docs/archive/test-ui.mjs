import { chromium } from 'playwright';

const pages = [
  { path: '/', name: '01-command-center', wait: 4000 },
  { path: '/#/office', name: '02-live-office', wait: 3000 },
  { path: '/#/company', name: '03-live-company', wait: 2000 },
  { path: '/#/skills', name: '04-skills', wait: 2000 },
  { path: '/#/mcp', name: '05-mcp', wait: 2000 },
  { path: '/#/settings', name: '06-settings', wait: 2000 },
];

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();

// Capture console errors
const errors = [];
page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
page.on('pageerror', err => errors.push(err.message));

let passed = 0;
let failed = 0;

for (const p of pages) {
  try {
    await page.goto(`http://127.0.0.1:5174${p.path}`, { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(p.wait);
    await page.screenshot({ path: `/tmp/screenshots/${p.name}.png`, fullPage: false });
    
    // Check for critical elements
    const bodyText = await page.textContent('body');
    if (bodyText && bodyText.length > 50) {
      console.log(`✅ ${p.name} — rendered OK`);
      passed++;
    } else {
      console.log(`⚠️ ${p.name} — minimal content`);
      failed++;
    }
  } catch (e) {
    console.log(`❌ ${p.name}: ${e.message.slice(0,80)}`);
    failed++;
  }
}

if (errors.length > 0) {
  console.log(`\n⚠️ Console errors (${errors.length}):`);
  errors.slice(0,5).forEach(e => console.log(`  ${e.slice(0,100)}`));
}

console.log(`\nResults: ${passed} passed, ${failed} failed`);
await browser.close();
