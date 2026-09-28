// Fallbacks (T3): /interface without WebGL, and both demo pages with JavaScript off, show a still frame
// with a caption and the text explanation instead of empty canvases or dead controls. Runs locally
// too (bci-queen slot) and in CI.
import { expect, test } from '@playwright/test';
import { collectErrors } from './util';

test('/interface without WebGL: still, caption and message; no controls; no errors', async ({
  page,
}) => {
  // Make every WebGL context request fail, as on a browser or GPU without WebGL.
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (type: string, ...rest: unknown[]) {
      if (/webgl/i.test(type)) return null;
      return (original as (...a: unknown[]) => unknown).call(this, type, ...rest);
    } as typeof original;
  });
  const errors = collectErrors(page);
  await page.goto('/interface/');
  await expect(page.locator('[data-ix-nowebgl]')).toBeVisible();
  // the script inserts <picture data-ix-still>; both it and its <img> must have a visible box
  await expect(page.locator('[data-ix-still]')).toBeVisible();
  const img = page.locator('[data-ix-still] img');
  await expect(img).toBeVisible();
  // at least as strict as the old check: loaded, non-zero size, inside the stage
  await expect
    .poll(() => img.evaluate((i: HTMLImageElement) => i.complete && i.naturalWidth))
    .toBeGreaterThan(0);
  const box = (await img.boundingBox())!;
  const stage = (await page.locator('[data-ix-stage]').boundingBox())!;
  expect(box.width).toBeGreaterThan(0);
  expect(box.height).toBeGreaterThan(0);
  expect(box.x).toBeGreaterThanOrEqual(stage.x - 0.5);
  expect(box.y).toBeGreaterThanOrEqual(stage.y - 0.5);
  expect(box.x + box.width).toBeLessThanOrEqual(stage.x + stage.width + 0.5);
  expect(box.y + box.height).toBeLessThanOrEqual(stage.y + stage.height + 0.5);
  await expect(page.locator('[data-ix-still-caption]')).toBeVisible();
  await expect(page.locator('[data-ix-controls]')).toBeHidden();
  await expect(page.locator('[data-ix-stage] canvas')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test.describe('JavaScript off', () => {
  test.use({ javaScriptEnabled: false });

  test('/playground: still + caption + results tables; live panels hidden', async ({ page }) => {
    await page.goto('/playground/');
    await expect(page.locator('[data-pg-still] img')).toBeVisible();
    await expect(page.locator('[data-pg-still] figcaption')).toBeVisible();
    await expect(page.locator('.stage')).toBeHidden();
    await expect(page.locator('[data-pg-controls]')).toBeHidden();
    await expect(page.getByText(/needs JavaScript/)).toBeVisible();
    await expect(page.locator('[data-pg-table="posR2"]')).toBeAttached();
  });

  test('/interface: still + caption + explanation; controls hidden', async ({ page }) => {
    await page.goto('/interface/');
    await expect(page.locator('[data-ix-stage] img.still')).toBeVisible();
    // JS off: the <noscript> caption shows; the script-driven [data-ix-still-caption] copy stays hidden
    await expect(page.locator('p.still-cap:not([data-ix-still-caption])')).toBeVisible();
    await expect(page.locator('[data-ix-still-caption]')).toBeHidden();
    await expect(page.getByText(/needs JavaScript and WebGL/)).toBeVisible();
    await expect(page.locator('[data-ix-controls]')).toBeHidden();
    await expect(page.locator('#h-ix-notes')).toBeVisible();
  });
});

test('normal path: the fallback stills are never downloaded', async ({ page }) => {
  const stills: string[] = [];
  page.on('request', (r) => {
    if (/(playground|interface)-still-/.test(r.url())) stills.push(r.url());
  });
  await page.goto('/playground/');
  await expect(page.locator('[data-pg-play]')).toBeEnabled();
  await page.goto('/interface/');
  const play = page.locator('[data-ix-play]');
  const noGl = page.locator('[data-ix-nowebgl]');
  await expect(play.or(noGl.filter({ visible: true }))).toBeVisible();
  test.skip(await noGl.isVisible(), 'no WebGL here: the still is the intended fallback');
  expect(stills).toEqual([]);
});
