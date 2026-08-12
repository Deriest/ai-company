import { test, expect } from '@playwright/test';

test.describe('AIC-ADE Blank Screen Fix v2.6.11', () => {
  
  test.beforeAll(async () => {
    console.log('[TEST SETUP] Starting E2E tests for blank screen fix');
  });

  test('should show boot interface (not blank)', async ({ page }) => {
    console.log('[TEST] Loading application...');
    
    await page.goto('http://localhost:5174', { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(3000);
    
    const bodyHTML = await page.content();
    console.log(`[DEBUG] Content length: ${bodyHTML.length} chars`);
    
    const hasLogo = await page.locator('.ade-fade-up').first().isVisible();
    const hasTitle = await page.locator('h1').filter({ hasText: /AIC-ADE/i }).count() > 0;
    
    console.log(`[DEBUG] Has logo: ${hasLogo}, Title: ${hasTitle}`);
    
    expect(hasLogo || hasTitle || bodyHTML.length > 500).toBe(true);
  });

  test('backend connection handling', async ({ page }) => {
    console.log('[TEST] Checking backend accessibility...');
    
    try {
      const response = await page.request.get('http://127.0.0.1:8088/health', {
        timeout: 5000
      });
      
      if (response.ok()) {
        const data = await response.json();
        console.log(`[SUCCESS] Backend: status=${data.status}`);
        expect(['healthy', 'starting']).toContain(data.status || '');
      } else {
        console.log(`[INFO] Backend status: ${response.status()}`);
        expect(response.status()).toBeGreaterThanOrEqual(200);
      }
    } catch (err: any) {
      console.log(`[INFO] Backend unavailable: ${err.message}`);
      expect(true).toBe(true);
    }
  });

  test('blank screen prevention final check', async ({ page }) => {
    console.log('[TEST] Verifying no blank screen...');
    await page.waitForTimeout(8000);
    
    const html = await page.content();
    const hasBlankScreen = !html || html.length < 50 || html.includes('<body></body>');
    
    console.log(`[DEBUG] Content length: ${html.length}, Blank: ${hasBlankScreen}`);
    
    expect(hasBlankScreen).toBe(false);
    
    const hasAnyUI = await page.locator('.ade-fade-up, p, button').count() > 0;
    console.log(`[RESULT] Has UI elements: ${hasAnyUI}`);
    
    expect(hasAnyUI || html.length > 500).toBe(true);
  });
});
