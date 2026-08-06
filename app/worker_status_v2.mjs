import { _electron as electron } from 'playwright';

async function main() {
  const app = await electron.launch({
    args: ['.', '--no-sandbox', '--disable-gpu'],
    cwd: '/home/tvd/AI-Company/app',
    env: { ...process.env, DISPLAY: ':99', AIC_BASE_URL: 'http://127.0.0.1:8000' },
  });
  const page = await app.firstWindow();
  await page.setViewportSize({ width: 1500, height: 950 });
  await page.waitForTimeout(7000);

  // Navigate to Office via Ctrl+1
  await page.keyboard.down('Control'); await page.keyboard.press('1'); await page.keyboard.up('Control');
  await page.waitForTimeout(3000);

  // Poll Office view 5 times (every 5s = 25s total) to catch status changes
  for (let poll = 1; poll <= 5; poll++) {
    const data = await page.evaluate(() => {
      const t = document.body.innerText;
      // Extract key info
      const activeMatch = t.match(/(\d+)\s*active/i);
      const missionsMatch = t.match(/(\d+)\s*Active Missions/i);
      
      // Find each worker status
      const workers = ['Hermes','Rex','Aria','Sage','Luna','Echo','Atlas','Hugo','Leo','Eve','Pulse','Nova','Nexus','Flint','Sentinel'];
      const statuses = {};
      for (const w of workers) {
        const idx = t.indexOf(w);
        if (idx >= 0) {
          const seg = t.slice(idx, idx + 100);
          const m = seg.match(/IDLE|WORKING|MEETING|COMPLETE/i);
          statuses[w] = m ? m[0].toUpperCase() : 'OFFLINE';
        }
      }
      return { active: activeMatch ? activeMatch[1] : '?', missions: missionsMatch ? missionsMatch[1] : '?', statuses };
    });
    
    // Find which workers are WORKING
    const working = Object.entries(data.statuses).filter(([_, s]) => s === 'WORKING').map(([n]) => n);
    const idle = Object.entries(data.statuses).filter(([_, s]) => s === 'IDLE').map(([n]) => n);
    
    console.log(`Poll ${poll}: active=${data.active} missions=${data.missions} | WORKING=[${working.join(',')}] | IDLE=[${idle.join(',')}]`);
    
    if (poll < 5) await page.waitForTimeout(5000);
  }

  await app.close();
  console.log('TEST_DONE');
}
main().catch(e => { console.error('FAIL', e.message); process.exit(1); });
