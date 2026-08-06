import { _electron as electron } from 'playwright';

async function main() {
  const app = await electron.launch({
    args: ['.', '--no-sandbox', '--disable-gpu'],
    cwd: '/home/tvd/AI-Company/app',
    env: { ...process.env, DISPLAY: ':99', AIC_BASE_URL: 'http://127.0.0.1:8000' },
  });
  const page = await app.firstWindow();
  await page.setViewportSize({ width: 1500, height: 950 });
  
  // Navigate to Office
  await page.keyboard.down('Control'); await page.keyboard.press('1'); await page.keyboard.up('Control');
  await page.waitForTimeout(2000);
  
  // Capture initial state
  console.log('=== INITIAL STATE ===');
  let status = await page.evaluate(() => document.body.innerText);
  console.log(status.substring(0, 500));
  
  // Now send a task via API and watch the Office view change
  console.log('Sending task via API...');
  const fetch = (await import('node:fetch')).default;
  const tokenRes = await fetch('http://127.0.0.1:8000/auth/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({username:'admin', password:'admin123'})
  });
  const tokenData = await tokenRes.json();
  const token = tokenData.access_token;
  
  // Create conversation and task
  const conv = await fetch('http://127.0.0.1:8000/conversations', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({title:'Quick test'})
  });
  const convId = (await conv.json()).id;
  
  const stream = await fetch(`http://127.0.0.1:8000/api/conversations/${convId}/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({content:'Create task to build a calculator'})
  });
  const reader = stream.body.getReader();
  let text = '';
  while(true) {
    const {done,value} = await reader.read();
    if(done) break;
    text += new TextDecoder().decode(value);
  }
  console.log('Stream done:', text.match(/task_id":"[^"]*/)?.[0]);
  
  // Watch Office view for 30s
  for(let i=1;i<=6;i++) {
    await page.waitForTimeout(5000);
    status = await page.evaluate(() => {
      const t = document.body.innerText;
      const lines = t.split('\n');
      // Find active count
      const activeMatch = t.match(/(\d+)\s*active/i);
      const workingWorkers = [];
      for(const line of lines) {
        if(line.includes('WORKING')) workingWorkers.push(line.trim());
      }
      return { active: activeMatch ? activeMatch[1] : '?', working: workingWorkers.slice(0,3).join('; ') };
    });
    console.log(`Poll ${i}: active=${status.active}, WORKING=[${status.working}]`);
  }
  
  await app.close();
  console.log('TEST_DONE');
}
main().catch(e=>{console.error('FAIL',e.message); process.exit(1)});
