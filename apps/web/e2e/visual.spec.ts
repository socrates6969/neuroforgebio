// Visual snapshots 360/768/1440 px x 2 themes + no horizontal scroll. Runs locally too (bci-queen
// slot) and in CI.
// First CI run: `playwright test --update-snapshots` and commit e2e/__snapshots__ after review.
import { expect, test } from '@playwright/test';
import { PAGES, WIDTHS } from './util';

for (const width of WIDTHS) {
  for (const path of PAGES) {
    test(`visual ${path} @${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.goto(path);
      await page.evaluate(() => document.fonts.ready);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow, 'horizontal scroll').toBeLessThanOrEqual(0);
      const name = `${path.replace(/[^a-z0-9]+/gi, '_').replace(/^_|_$/g, '') || 'home'}-${width}.png`;
      await expect(page).toHaveScreenshot(name, { fullPage: true, mask: [page.locator('canvas')] });
    });
  }
}
