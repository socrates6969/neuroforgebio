// Website security headers in a real browser. Runs locally too (bci-queen slot) and in CI (see
// playwright.config.ts).
// scripts/serve.mjs serves each dist with its own _headers (security-headers.mjs), so this checks
// SEC-150 (zero CSP violations), SEC-154 (crossOriginIsolated; cosmos hero under COEP) and
// SEC-155 (every request same-origin) on every page of both builds, EN and NO.
import { expect, test, type Page } from '@playwright/test';
import { PAGES, collectErrors, themeOf } from './util';

/** Records CSP violations (securitypolicyviolation events + console reports) from the first byte. */
async function watchCsp(page: Page) {
  const logs: string[] = [];
  page.on('console', (m) => {
    if (/Content Security Policy|Refused to (load|execute|apply)/i.test(m.text()))
      logs.push(m.text());
  });
  await page.addInitScript(() => {
    const w = window as unknown as { __csp: string[] };
    w.__csp = [];
    document.addEventListener('securitypolicyviolation', (e) =>
      w.__csp.push(`${e.violatedDirective} ${e.blockedURI}`),
    );
  });
  return async () => [
    ...logs,
    ...(await page.evaluate(() => (window as unknown as { __csp: string[] }).__csp)),
  ];
}

test('headers are applied by the test server (sanity)', async ({ page }) => {
  const res = await page.goto('/');
  const h = res!.headers();
  expect(h['content-security-policy']).toMatch(/^default-src 'none'; script-src 'self';/);
  expect(h['cross-origin-embedder-policy']).toBe('require-corp');
  expect(h['cross-origin-opener-policy']).toBe('same-origin');
  expect(h['permissions-policy']).toContain('usb=()');
});

for (const path of PAGES) {
  test(`SEC-150/155: zero CSP violations and only same-origin requests on ${path}`, async ({
    page,
    baseURL,
  }) => {
    const origin = new URL(baseURL!).origin;
    const foreign: string[] = [];
    page.on('request', (r) => {
      const u = new URL(r.url());
      if (u.protocol.startsWith('http') && u.origin !== origin) foreign.push(r.url());
    });
    const violations = await watchCsp(page);
    const errors = collectErrors(page);
    await page.goto(path, { waitUntil: 'networkidle' });
    // scroll through the page so lazy islands (cosmos three.js hero, figures) load too
    await page.evaluate(async () => {
      for (let y = 0; y < document.body.scrollHeight; y += 600) {
        window.scrollTo(0, y);
        await new Promise((r) => setTimeout(r, 50));
      }
    });
    await page.waitForLoadState('networkidle');
    expect(await violations()).toEqual([]);
    expect(foreign).toEqual([]);
    expect(errors.filter((e) => !(path === '/404.html' && e.includes('404')))).toEqual([]);
  });
}

test('SEC-154: crossOriginIsolated === true on / (COOP same-origin + COEP require-corp)', async ({
  page,
}) => {
  await page.goto('/');
  expect(await page.evaluate(() => window.crossOriginIsolated)).toBe(true);
});

test('SEC-154: cosmos hero renders under COEP, with WebGL and with the fallback', async ({
  page,
  browser,
}, info) => {
  test.skip(themeOf(info) !== 'cosmos', 'the WebGL hero is cosmos-only');
  const HERO = '.hero .stage [role="img"]';
  // WebGL path: the lazily imported, self-hosted three.js chunk loads and draws a canvas
  const violations = await watchCsp(page);
  const errors = collectErrors(page);
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/', { waitUntil: 'networkidle' });
  await expect(page.locator(HERO)).toBeVisible();
  const hasWebGL = await page.evaluate(() => {
    const c = document.createElement('canvas');
    return !!(c.getContext('webgl2') || c.getContext('webgl'));
  });
  if (hasWebGL) await expect(page.locator(`${HERO} canvas`)).toHaveCount(1, { timeout: 15_000 });
  expect(await violations()).toEqual([]);
  expect(errors).toEqual([]);

  // Fallback path: WebGL unavailable -> SVG fallback stays, no errors
  const ctx = await browser.newContext({ baseURL: info.project.use.baseURL });
  const p2 = await ctx.newPage();
  await p2.addInitScript(() => {
    const orig = HTMLCanvasElement.prototype.getContext;
    // @ts-expect-error test override
    HTMLCanvasElement.prototype.getContext = function (type: string, ...rest: unknown[]) {
      if (/webgl/i.test(type)) return null;
      return orig.call(this, type, ...rest);
    };
  });
  const errors2 = collectErrors(p2);
  await p2.goto('/', { waitUntil: 'networkidle' });
  await expect(p2.locator(HERO)).toBeVisible();
  await expect(p2.locator(`${HERO} svg`).first()).toBeVisible();
  expect(errors2).toEqual([]);
  await ctx.close();
});

test('no cookies and no web storage after visiting every page', async ({ page, context }) => {
  for (const p of PAGES) await page.goto(p, { waitUntil: 'networkidle' });
  expect(await context.cookies()).toEqual([]);
  const storage = await page.evaluate(() => ({
    local: window.localStorage.length,
    session: window.sessionStorage.length,
  }));
  expect(storage).toEqual({ local: 0, session: 0 });
});
