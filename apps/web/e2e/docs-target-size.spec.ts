// /docs side-nav target size (WCAG 2.5.8, web-a11y T11): each side-nav link's clickable box is at
// least 24px tall, at a narrow (320px) and a wide (1280px) viewport, both themes. Assertions only,
// no visual baseline -- this is a layout measurement, not a pixel pin. Runs locally too (bci-queen
// slot) and in CI. Currently failing (2026-09-27): DocsShell.astro's `.side a` has no padding and no
// `display: block`, so its box is just the 15px text line -- fixed by web-a11y's pending side-nav
// change (see their T11 note); this test documents the gap and will pass once that lands.
import { expect, test } from '@playwright/test';

const WIDTHS = [320, 1280] as const;
const MIN_TARGET = 24;

for (const width of WIDTHS) {
  test(`side-nav links are >= ${MIN_TARGET}px tall @${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/docs/');
    const links = page.locator('nav.side a');
    const count = await links.count();
    expect(count).toBeGreaterThan(0);
    const heights: number[] = [];
    for (let i = 0; i < count; i++) {
      const box = await links.nth(i).boundingBox();
      heights.push(box?.height ?? 0);
    }
    const short = heights.map((h, i) => ({ h, i })).filter(({ h }) => h < MIN_TARGET);
    expect(short, `link(s) under ${MIN_TARGET}px: ${JSON.stringify(short)}`).toEqual([]);
  });
}
