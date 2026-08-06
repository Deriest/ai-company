// Worker status change test - reliable version
import { _electron as electron } from 'playwright';

async function main() {
  const app = await electron.launch({
    args: ['.', '--no-sandbox', '--disable-gpu'],
    cwd: '/home/tvd/AI-Company/app',
    env: { ...process.env, DISPLAY: ':99', AIC_BASE_URL: 'http://127.0.0.1:8000' },
  });
  const page = await app.firstWindow();
  await page.setViewportSize({ width: 1500, height: 950 });
  await page.waitForTimeout(6000);

  // === STEP 1: Navigate to OFFICE view and capture baseline ===
  console.log('=== NAVIGATING TO OFFICE VIEW ===');
  await page.locator('.nav-item').filter({ hasText: 'Office' }).click();
  await page.waitForTimeout(2000);
  
  const beforeStatus = await page.evaluate(() => {
    const t = document.body.innerText;
    const workers = ['Hermes','Rex','Aria','Sage','Luna','Echo','Atlas','Hugo','Leo','Eve','Pulse','Nova','Nexus','Flint','Sentinel'];
    const result = {};
    const lines = t.split('\n');
    for (const w of workers) {
      let found = false;
      for (let i = 0; i < lines.length; i++) {
        if (lines[i].includes(w)) {
          found = true;
          const statusLine = lines.slice(Math.max(0, i-2), Math.min(lines.length, i+3)).join(' ');
          const status = statusLine.match(/IDLE|WORKING|MEETING|COMPLETE/i);
          result[w] = status ? status[0].toUpperCase() : 'OFFLINE';
          break;
        }
      }
      if (!found) result[w] = 'NOT FOUND';
    }
    return result;
  });
  console.log('=== BEFORE (Office view) ===');
  console.log(JSON.stringify(beforeStatus, null, 2));

  // === STEP 2: Wait for task dispatch + worker execution (30s) ===
  console.log('=== WAITING FOR WORKER EXECUTION (30s) ===');
  await page.waitForTimeout(30000);

  // === STEP 3: Check Office view AGAIN ===
  console.log('=== CHECKING OFFICE VIEW AFTER DISPATCH ===');
  const afterStatus = await page.evaluate(() => {
    const t = document.body.innerText;
    const workers = ['Hermes','Rex','Aria','Sage','Luna','Echo','Atlas','Hugo','Leo','Eve','Pulse','Nova','Nexus','Flint','Sentinel'];
    const result = {};
    const lines = t.split('\n');
    for (const w of workers) {
      let found = false;
      for (let i = 0; i < lines.length; i++) {
        if (lines[i].includes(w)) {
          found = true;
          const statusLine = lines.slice(Math.max(0, i-2), Math.min(lines.length, i+3)).join(' ');
          const status = statusLine.match(/IDLE|WORKING|MEETING|COMPLETE/i);
          result[w] = status ? status[0].toUpperCase() : 'OFFLINE';
          break;
        }
      }
      if (!found) result[w] = 'NOT FOUND';
    }
    return result;
  });
  console.log('=== AFTER (Office view) ===');
  console.log(JSON.stringify(afterStatus, null, 2));

  // === COMPARE ===
  const changed = [];
  for (const [name, before] of Object.entries(beforeStatus)) {
    const after = afterStatus[name];
    if (before !== after) changed.push(`${name}: ${before} → ${after}`);
  }
  console.log('=== CHANGES DETECTED ===');
  if (changed.length > 0) {
    changed.forEach(c => console.log(`  ✓ ${c}`));
  } else {
    console.log('  No status changes detected (all workers still IDLE or not found)');
  }

  // Save full text
  const fullText = await page.evaluate(() => document.body.innerText);
  require('fs').writeFileSync('/tmp/office_final.txt', fullText);

  await app.close();
  console.log('TEST_DONE');
}

main().catch(e => { console.error('FAIL', e.stack); process.exit(1); });
