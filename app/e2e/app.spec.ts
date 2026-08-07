import { test, expect, _electron as electron } from '@playwright/test';

test('Electron app launches and renderer loads', async () => {
  // Launch the packaged Electron main (uses built dist-electron + dist).
  const app = await electron.launch({
    args: ['.'],
    cwd: __dirname + '/..',
    env: { ...process.env, AIC_IDE_DEV: '0' },
  });

  try {
    // First window is the main renderer.
    const win = await app.firstWindow({ timeout: 60000 });
    await win.waitForLoadState('domcontentloaded', { timeout: 60000 });

    // Give the frontend a moment to mount React.
    await win.waitForTimeout(4000);

    // The renderer should have rendered the app shell (not a blank page).
    const title = await win.title();
    const bodyText = await win.evaluate(() => document.body ? document.body.innerText : '');
    const hasReactRoot = await win.evaluate(() => !!document.querySelector('#root'));

    console.log('window title:', JSON.stringify(title));
    console.log('body text length:', bodyText.length);
    console.log('has #root:', hasReactRoot);

    expect(hasReactRoot).toBeTruthy();
    // The app must render SOME content (loading screen, workspace, or auth).
    expect(bodyText.length).toBeGreaterThan(0);
  } finally {
    await app.close();
  }
});
