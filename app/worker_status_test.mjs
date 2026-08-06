// Worker status change test: chat -> trigger worker -> check Office status
import { _electron as electron } from 'playwright';
import { writeFileSync } from 'fs';

async function main() {
  const app = await electron.launch({
    args: ['.', '--no-sandbox', '--disable-gpu'],
    cwd: '/home/tvd/AI-Company/app',
    env: { ...process.env, DISPLAY: ':99', AIC_BASE_URL: 'http://127.0.0.1:8000' },
  });
  const page = await app.firstWindow();
  await page.setViewportSize({ width: 1500, height: 950 });
  await page.waitForTimeout(8000);

  // === STEP 1: Check Office BEFORE chat — all workers should be IDLE ===
  await page.keyboard.down('Control'); await page.keyboard.press('1'); await page.keyboard.up('Control');
  await page.waitForTimeout(2000);
  const beforeWorkers = await page.evaluate(() => {
    const t = document.body.innerText;
    // Extract each worker name + their status
    const workers = ['Hermes','Rex','Aria','Sage','Luna','Echo','Atlas','Hugo','Leo','Eve','Pulse','Nova','Nexus','Flint','Sentinel'];
    const result = {};
    for (const w of workers) {
      const idx = t.indexOf(w);
      if (idx >= 0) {
        const seg = t.slice(idx, idx + 80);
        const status = seg.match(/IDLE|WORKING|MEETING|COMPLETE/i);
        result[w] = status ? status[0] : 'UNKNOWN';
      }
    }
    return result;
  });
  console.log('=== BEFORE CHAT (Office worker status) ===');
  console.log(JSON.stringify(beforeWorkers, null, 2));

  // === STEP 2: Go to Command Center, send a chat message that triggers a worker ===
  await page.keyboard.down('Control'); await page.keyboard.press('2'); await page.keyboard.up('Control');
  await page.waitForTimeout(2000);

  // Check textarea visible
  const taVisible = await page.evaluate(() => {
    const ta = document.querySelector('textarea');
    if (!ta) return false;
    const r = ta.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  });
  console.log('textarea visible:', taVisible);

  if (taVisible) {
    await page.fill('textarea', 'Create task to build a simple REST API with FastAPI and SQLite that returns JSON responses');
    await page.keyboard.press('Enter');
    console.log('=== CHAT SENT — waiting for task creation + worker dispatch ===');

    // Wait for task to be created and dispatched (15s)
    await page.waitForTimeout(15000);
  }

  // === STEP 3: Go back to Office — check if worker status CHANGED ===
  await page.keyboard.down('Control'); await page.keyboard.press('1'); await page.keyboard.up('Control');
  await page.waitForTimeout(3000);
  const afterWorkers = await page.evaluate(() => {
    const t = document.body.innerText;
    const workers = ['Hermes','Rex','Aria','Sage','Luna','Echo','Atlas','Hugo','Leo','Eve','Pulse','Nova','Nexus','Flint','Sentinel'];
    const result = {};
    for (const w of workers) {
      const idx = t.indexOf(w);
      if (idx >= 0) {
        const seg = t.slice(idx, idx + 80);
        const status = seg.match(/IDLE|WORKING|MEETING|COMPLETE/i);
        result[w] = status ? status[0] : 'UNKNOWN';
      }
    }
    // Also capture the "active workers" count and "active missions"
    const activeMatch = t.match(/(\d+)\s*active/);
    const missionsMatch = t.match(/(\d+)\s*(?:missions|Active Missions)/);
    return { workers: result, activeCount: activeMatch ? activeMatch[1] : '?', missions: missionsMatch ? missionsMatch[1] : '?' };
  });
  console.log('=== AFTER CHAT (Office worker status) ===');
  console.log(JSON.stringify(afterWorkers, null, 2));

  // === STEP 4: Compare — which workers changed? ===
  const changed = [];
  for (const [name, before] of Object.entries(beforeWorkers)) {
    const after = afterWorkers.workers[name];
    if (before !== after) changed.push(`${name}: ${before} → ${after}`);
  }
  console.log('=== STATUS CHANGES ===');
  console.log(changed.length > 0 ? changed.join('\n') : 'NO CHANGES DETECTED');

  // Save full office text for reference
  const officeFull = await page.evaluate(() => document.body.innerText);
  writeFileSync('/tmp/office_after_chat.txt', officeFull);

  await app.close();
  console.log('TEST_DONE');
}

main().catch(e => { console.error('TEST_FAIL', e); process.exit(1); });