import { test, expect, _electron as electron } from '@playwright/test';

test('AIC-ADE desktop app launches and renders correctly', async () => {
  const app = await electron.launch({
    args: ['.'],
    cwd: __dirname + '/..',
    env: { ...process.env, AIC_IDE_DEV: '0' },
  });
  
  const win = await app.firstWindow({ timeout: 120000 });
  await win.waitForLoadState('domcontentloaded', { timeout: 60000 });
  
  // Critical check: React #root exists
  const hasReactRoot = await win.evaluate(() => !!document.querySelector('#root'));
  expect(hasReactRoot).toBe(true);
  
  // Body must have substantial content (not blank page)
  const bodyText = await win.evaluate(() => document.body?.innerText || '');
  expect(bodyText.length).toBeGreaterThan(50);
  
  // App title should be present
  const title = await win.title();
  expect(title.length).toBeGreaterThan(0);
  
  // Wait for full hydration and verify interactive elements appear
  await win.waitForTimeout(8000);
  
  const buttonCount = await win.locator('button').count();
  console.log(`✅ Electron success: root=${hasReactRoot}, content=${bodyText.length}chars, buttons=${buttonCount}`);
  
  await app.close();
});
