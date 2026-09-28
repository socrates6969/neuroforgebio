// Hero visual behaviour: WebGL-disabled fallback, reduced motion, lazy three.js, no jsdelivr. Runs
// locally too (bci-queen slot) and in CI.
import { expect, test } from '@playwright/test';
import { PAGES, THIRD_PARTY, collectErrors, recordNetwork, themeOf } from './util';

const HERO = '.hero .stage [role="img"]';

test('no third-party requests on any page', async ({ page }) => {
  const net = recordNetwork(page);
  for (const p of PAGES) await page.goto(p, { waitUntil: 'networkidle' });
  expect(net.external).toEqual([]);
  expect(net.log.filter((r) => THIRD_PARTY.test(r.url))).toEqual([]);
});

test('WebGL disabled: fallback visible, no console errors, no three.js', async ({ page }) => {
  await page.addInitScript(() => {
    const orig = HTMLCanvasElement.prototype.getContext;
    // @ts-expect-error test override
    HTMLCanvasElement.prototype.getContext = function (type: string, ...rest: unknown[]) {
      if (/webgl/i.test(type)) return null;
      // @ts-expect-error passthrough
      return orig.call(this, type, ...rest);
    };
  });
  const errors = collectErrors(page);
  const net = recordNetwork(page);
  await page.goto('/', { waitUntil: 'networkidle' });
  await expect(page.locator(HERO)).toBeVisible();
  await expect(page.locator(HERO)).toHaveAttribute('aria-label', /.+/);
  expect(errors).toEqual([]);
  expect(net.log.filter((r) => r.three)).toEqual([]);
});

test('reduced motion: no three.js and no animation frames after load', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.addInitScript(() => {
    (window as unknown as { __raf: number }).__raf = 0;
    const raf = window.requestAnimationFrame.bind(window);
    window.requestAnimationFrame = (cb) => {
      (window as unknown as { __raf: number }).__raf++;
      return raf(cb);
    };
  });
  const net = recordNetwork(page);
  await page.goto('/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(500);
  const before = await page.evaluate(() => (window as unknown as { __raf: number }).__raf);
  await page.waitForTimeout(1500);
  const after = await page.evaluate(() => (window as unknown as { __raf: number }).__raf);
  expect(after - before, 'animation frames requested while reduced motion is on').toBe(0);
  expect(net.log.filter((r) => r.three)).toEqual([]);
});

test('three.js: never on clinical; on cosmos only after the hero is visible', async ({
  page,
}, info) => {
  const theme = themeOf(info);
  // Start scrolled away from the hero on a page without a hero: nothing may load three.
  const net = recordNetwork(page);
  await page.goto('/platform/', { waitUntil: 'networkidle' });
  expect(net.log.filter((r) => r.three)).toEqual([]);

  // Home: record when the hero first intersects the viewport and when three.js is requested.
  await page.setViewportSize({ width: 1280, height: 700 });
  await page.addInitScript(() => {
    (window as unknown as { __heroSeenAt: number | null }).__heroSeenAt = null;
    document.addEventListener('DOMContentLoaded', () => {
      const el = document.querySelector('.hero .stage');
      if (!el) return;
      new IntersectionObserver((es) => {
        if (
          es.some((e) => e.isIntersecting) &&
          (window as unknown as { __heroSeenAt: number | null }).__heroSeenAt === null
        ) {
          (window as unknown as { __heroSeenAt: number | null }).__heroSeenAt = performance.now();
        }
      }).observe(el);
    });
  });
  const net2 = recordNetwork(page);
  await page.goto('/', { waitUntil: 'networkidle' });
  const threeReqs = await page.evaluate(() =>
    performance
      .getEntriesByType('resource')
      .filter((e) => e.name.endsWith('.js'))
      .map((e) => ({ name: e.name, start: e.startTime })),
  );
  const seen = await page.evaluate(
    () => (window as unknown as { __heroSeenAt: number | null }).__heroSeenAt,
  );
  const threeUrls = new Set(net2.log.filter((r) => r.three).map((r) => r.url));
  if (theme === 'clinical') {
    expect([...threeUrls]).toEqual([]);
    return;
  }
  // cosmos: if three loaded, it started after the hero became visible
  for (const r of threeReqs.filter((x) => threeUrls.has(x.name))) {
    expect(seen, 'hero must have been visible before three.js was requested').not.toBeNull();
    expect(r.start).toBeGreaterThanOrEqual(seen as number);
  }
});

test('cosmos initial JS before the hero is visible stays within 60 KB gzip', async ({
  page,
}, info) => {
  test.skip(themeOf(info) !== 'cosmos', 'cosmos budget');
  await page.setViewportSize({ width: 1280, height: 700 });
  const net = recordNetwork(page);
  await page.goto('/platform/', { waitUntil: 'networkidle' });
  const sizes = await page.evaluate(() =>
    performance
      .getEntriesByType('resource')
      .filter((e) => e.name.endsWith('.js'))
      .map(
        (e) =>
          (e as PerformanceResourceTiming).transferSize ||
          (e as PerformanceResourceTiming).encodedBodySize,
      ),
  );
  const total = sizes.reduce((a, b) => a + b, 0);
  expect(total).toBeLessThanOrEqual(60 * 1024);
  expect(net.log.filter((r) => r.three)).toEqual([]);
});
