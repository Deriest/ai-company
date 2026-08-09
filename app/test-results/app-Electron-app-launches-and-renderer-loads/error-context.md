# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: app.spec.ts >> Electron app launches and renderer loads
- Location: e2e/app.spec.ts:3:5

# Error details

```
Error: electron.launch: Process failed to launch!
Call log:
  - <launching> /home/tvd/AI-Company/app/node_modules/electron/dist/electron -r /home/tvd/AI-Company/app/node_modules/playwright-core/lib/server/electron/loader.js --no-sandbox --inspect=0 --remote-debugging-port=0 .
  - <launched> pid=465849
  - [pid=465849][err] Debugger listening on ws://127.0.0.1:39829/dff94f40-8bbd-40dc-b5f1-91428ae89f92
  - [pid=465849][err] For help, see: https://nodejs.org/en/docs/inspector
  - <ws connecting> ws://127.0.0.1:39829/dff94f40-8bbd-40dc-b5f1-91428ae89f92
  - <ws connected> ws://127.0.0.1:39829/dff94f40-8bbd-40dc-b5f1-91428ae89f92
  - [pid=465849][err] Debugger attached.
  - [pid=465849][err] [465849:0809/110326.714880:ERROR:ozone_platform_x11.cc(246)] Missing X server or $DISPLAY
  - [pid=465849][err] [465849:0809/110326.714953:ERROR:env.cc(257)] The platform failed to initialize.  Exiting.
  - [pid=465849][err] Waiting for the debugger to disconnect...
  - <ws disconnecting> ws://127.0.0.1:39829/dff94f40-8bbd-40dc-b5f1-91428ae89f92
  - <ws disconnected> ws://127.0.0.1:39829/dff94f40-8bbd-40dc-b5f1-91428ae89f92 code=1005 reason=
  - [pid=465849] <kill>
  - [pid=465849] <will force kill>
  - [pid=465849] <process did exit: exitCode=null, signal=SIGSEGV>
  - [pid=465849] starting temporary directories cleanup
  - [pid=465849] finished temporary directories cleanup

```

# Test source

```ts
  1  | import { test, expect, _electron as electron } from '@playwright/test';
  2  | 
  3  | test('Electron app launches and renderer loads', async () => {
  4  |   // Launch the packaged Electron main (uses built dist-electron + dist).
> 5  |   const app = await electron.launch({
     |               ^ Error: electron.launch: Process failed to launch!
  6  |     args: ['.'],
  7  |     cwd: __dirname + '/..',
  8  |     env: { ...process.env, AIC_IDE_DEV: '0' },
  9  |   });
  10 | 
  11 |   try {
  12 |     // First window is the main renderer.
  13 |     const win = await app.firstWindow({ timeout: 60000 });
  14 |     await win.waitForLoadState('domcontentloaded', { timeout: 60000 });
  15 | 
  16 |     // Give the frontend a moment to mount React.
  17 |     await win.waitForTimeout(4000);
  18 | 
  19 |     // The renderer should have rendered the app shell (not a blank page).
  20 |     const title = await win.title();
  21 |     const bodyText = await win.evaluate(() => document.body ? document.body.innerText : '');
  22 |     const hasReactRoot = await win.evaluate(() => !!document.querySelector('#root'));
  23 | 
  24 |     console.log('window title:', JSON.stringify(title));
  25 |     console.log('body text length:', bodyText.length);
  26 |     console.log('has #root:', hasReactRoot);
  27 | 
  28 |     expect(hasReactRoot).toBeTruthy();
  29 |     // The app must render SOME content (loading screen, workspace, or auth).
  30 |     expect(bodyText.length).toBeGreaterThan(0);
  31 |   } finally {
  32 |     await app.close();
  33 |   }
  34 | });
  35 | 
```