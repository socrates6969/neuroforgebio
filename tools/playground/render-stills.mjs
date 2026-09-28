#!/usr/bin/env node
// Renders the /interface stills from a built, served site (record mode, fixed camera path, no captions).
// Uses the Playwright Chromium that apps/web already depends on; WebGL runs in SwiftShader, so no GPU
// is needed. Heavy-ish (one headless browser): run on demand, not in CI.
//   node apps/web/scripts/serve.mjs apps/web/dist/cosmos 4472 &
//   node tools/playground/render-stills.mjs http://127.0.0.1:4472 cosmos
// Writes marketing/stills/neural-interface/interface-<theme>-t<seconds>.jpg (2560x1440) and the page's
// fallback packages/themes/<theme>/stills/interface-still.jpg (1600x900, overview frame), and the
// /playground fallback packages/themes/<theme>/stills/playground-still.jpg (replay panels, t = 3.2 s).
import { createRequire } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const require = createRequire(join(ROOT, 'apps/web/package.json'));
const { chromium } = require('@playwright/test');

const [base = 'http://127.0.0.1:4472', theme = 'cosmos'] = process.argv.slice(2);
// overview, array close-up, neurons firing, decoder and outputs (seconds on the tour path)
const STILLS = [0.5, 6, 11, 21];

const browser = await chromium.launch({
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
});
async function render(width, height, scale, times, path) {
  const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: scale });
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(`${base}/interface/?record=1&captions=0`);
  await page.waitForFunction(() => window.__record?.ready, null, { timeout: 60_000 });
  for (const t of times) {
    await page.evaluate((s) => window.__seek(s), t);
    await page.screenshot({ path: path(t), type: 'jpeg', quality: 88 });
  }
  await page.close();
  if (errors.length) throw new Error(errors.join('\n'));
}
await render(1280, 720, 2, STILLS, (t) =>
  join(ROOT, `marketing/stills/neural-interface/interface-${theme}-t${t}.jpg`),
);
await render(1600, 900, 1, [0.5], () =>
  join(ROOT, `packages/themes/${theme}/stills/interface-still.jpg`),
);
// /playground fallback still: the three replay panels mid-reach (record timeline, t = 3.2 s), at
// 1x (about 1150 px wide, the stage never exceeds 1200 CSS px)
{
  const page = await browser.newPage({
    viewport: { width: 1280, height: 900 },
    deviceScaleFactor: 1,
  });
  await page.goto(`${base}/playground/?record=1`);
  await page.waitForFunction(() => window.__record?.ready, null, { timeout: 60_000 });
  await page.evaluate(() => window.__seek(3.2));
  await page.locator('.stage').screenshot({
    path: join(ROOT, `packages/themes/${theme}/stills/playground-still.jpg`),
    type: 'jpeg',
    quality: 80,
  });
  await page.close();
}
await browser.close();
console.log(`stills written for ${theme}`);
