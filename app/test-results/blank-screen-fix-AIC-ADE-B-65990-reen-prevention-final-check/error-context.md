# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: blank-screen-fix.spec.ts >> AIC-ADE Blank Screen Fix v2.6.11 >> blank screen prevention final check
- Location: e2e/blank-screen-fix.spec.ts:48:7

# Error details

```
Error: expect(received).toBe(expected) // Object.is equality

Expected: false
Received: true
```

# Test source

```ts
  1  | import { test, expect } from '@playwright/test';
  2  | 
  3  | test.describe('AIC-ADE Blank Screen Fix v2.6.11', () => {
  4  |   
  5  |   test.beforeAll(async () => {
  6  |     console.log('[TEST SETUP] Starting E2E tests for blank screen fix');
  7  |   });
  8  | 
  9  |   test('should show boot interface (not blank)', async ({ page }) => {
  10 |     console.log('[TEST] Loading application...');
  11 |     
  12 |     await page.goto('http://localhost:5174', { waitUntil: 'networkidle', timeout: 30000 });
  13 |     await page.waitForTimeout(3000);
  14 |     
  15 |     const bodyHTML = await page.content();
  16 |     console.log(`[DEBUG] Content length: ${bodyHTML.length} chars`);
  17 |     
  18 |     const hasLogo = await page.locator('.ade-fade-up').first().isVisible();
  19 |     const hasTitle = await page.locator('h1').filter({ hasText: /AIC-ADE/i }).count() > 0;
  20 |     
  21 |     console.log(`[DEBUG] Has logo: ${hasLogo}, Title: ${hasTitle}`);
  22 |     
  23 |     expect(hasLogo || hasTitle || bodyHTML.length > 500).toBe(true);
  24 |   });
  25 | 
  26 |   test('backend connection handling', async ({ page }) => {
  27 |     console.log('[TEST] Checking backend accessibility...');
  28 |     
  29 |     try {
  30 |       const response = await page.request.get('http://127.0.0.1:8088/health', {
  31 |         timeout: 5000
  32 |       });
  33 |       
  34 |       if (response.ok()) {
  35 |         const data = await response.json();
  36 |         console.log(`[SUCCESS] Backend: status=${data.status}`);
  37 |         expect(['healthy', 'starting']).toContain(data.status || '');
  38 |       } else {
  39 |         console.log(`[INFO] Backend status: ${response.status()}`);
  40 |         expect(response.status()).toBeGreaterThanOrEqual(200);
  41 |       }
  42 |     } catch (err: any) {
  43 |       console.log(`[INFO] Backend unavailable: ${err.message}`);
  44 |       expect(true).toBe(true);
  45 |     }
  46 |   });
  47 | 
  48 |   test('blank screen prevention final check', async ({ page }) => {
  49 |     console.log('[TEST] Verifying no blank screen...');
  50 |     await page.waitForTimeout(8000);
  51 |     
  52 |     const html = await page.content();
  53 |     const hasBlankScreen = !html || html.length < 50 || html.includes('<body></body>');
  54 |     
  55 |     console.log(`[DEBUG] Content length: ${html.length}, Blank: ${hasBlankScreen}`);
  56 |     
> 57 |     expect(hasBlankScreen).toBe(false);
     |                            ^ Error: expect(received).toBe(expected) // Object.is equality
  58 |     
  59 |     const hasAnyUI = await page.locator('.ade-fade-up, p, button').count() > 0;
  60 |     console.log(`[RESULT] Has UI elements: ${hasAnyUI}`);
  61 |     
  62 |     expect(hasAnyUI || html.length > 500).toBe(true);
  63 |   });
  64 | });
  65 | 
```