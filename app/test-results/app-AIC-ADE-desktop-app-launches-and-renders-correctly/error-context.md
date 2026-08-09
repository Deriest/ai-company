# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: app.spec.ts >> AIC-ADE desktop app launches and renders correctly
- Location: e2e/app.spec.ts:3:5

# Error details

```
Error: expect(received).toBeGreaterThan(expected)

Expected: > 50
Received:   8
```

# Test source

```ts
  1  | import { test, expect, _electron as electron } from '@playwright/test';
  2  | 
  3  | test('AIC-ADE desktop app launches and renders correctly', async () => {
  4  |   const app = await electron.launch({
  5  |     args: ['.'],
  6  |     cwd: __dirname + '/..',
  7  |     env: { ...process.env, AIC_IDE_DEV: '0' },
  8  |   });
  9  |   
  10 |   const win = await app.firstWindow({ timeout: 120000 });
  11 |   await win.waitForLoadState('domcontentloaded', { timeout: 60000 });
  12 |   
  13 |   // Critical check: React #root exists
  14 |   const hasReactRoot = await win.evaluate(() => !!document.querySelector('#root'));
  15 |   expect(hasReactRoot).toBe(true);
  16 |   
  17 |   // Body must have substantial content (not blank page)
  18 |   const bodyText = await win.evaluate(() => document.body?.innerText || '');
> 19 |   expect(bodyText.length).toBeGreaterThan(50);
     |                           ^ Error: expect(received).toBeGreaterThan(expected)
  20 |   
  21 |   // App title should be present
  22 |   const title = await win.title();
  23 |   expect(title.length).toBeGreaterThan(0);
  24 |   
  25 |   // Wait for full hydration and verify interactive elements appear
  26 |   await win.waitForTimeout(8000);
  27 |   
  28 |   const buttonCount = await win.locator('button').count();
  29 |   console.log(`✅ Electron success: root=${hasReactRoot}, content=${bodyText.length}chars, buttons=${buttonCount}`);
  30 |   
  31 |   await app.close();
  32 | });
  33 | 
```