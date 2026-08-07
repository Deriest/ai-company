/* Minimal Electron UI smoke test via playwright._electron (no @playwright/test needed).
   Launches the built app under xvfb and asserts the renderer mounts. */
import { _electron as electron } from 'playwright';

const app = await electron.launch({
  args: ['.'],
  cwd: new URL('..', import.meta.url).pathname,
  env: { ...process.env, AIC_IDE_DEV: '0' },
});

let ok = false;
try {
  const win = await app.firstWindow({ timeout: 60000 });
  await win.waitForLoadState('domcontentloaded', { timeout: 60000 });
  await win.waitForTimeout(5000);

  const info = await win.evaluate(() => {
    const root = document.querySelector('#root');
    const body = document.body ? document.body.innerText : '';
    return {
      hasRoot: !!root,
      rootChildren: root ? root.children.length : 0,
      bodyLen: body.length,
      bodyPreview: body.slice(0, 200),
      title: document.title,
    };
  });

  console.log('=== ELECTRON UI CHECK ===');
  console.log('title:', JSON.stringify(info.title));
  console.log('has #root:', info.hasRoot, '| root children:', info.rootChildren);
  console.log('body length:', info.bodyLen);
  console.log('body preview:', JSON.stringify(info.bodyPreview));

  if (!info.hasRoot || info.rootChildren === 0 || info.bodyLen === 0) {
    console.log('RESULT: FAIL — renderer did not mount content');
  } else {
    console.log('RESULT: PASS — renderer mounted');
    ok = true;
  }
} catch (e) {
  console.log('RESULT: ERROR —', e.message);
} finally {
  await app.close();
}
process.exit(ok ? 0 : 1);
