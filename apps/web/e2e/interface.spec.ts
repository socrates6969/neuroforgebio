// /interface: the 3D scene starts under the strict CSP (or falls back to the still image without
// WebGL), keyboard controls work, record mode is deterministic, reduced motion shows the still.
// Runs locally too (bci-queen slot) and in CI.
import { expect, test } from '@playwright/test';
import { collectErrors } from './util';

test('scene or still fallback; keyboard controls; electrode inspector', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto('/interface/');
  const play = page.locator('[data-ix-play]');
  const noGl = page.locator('[data-ix-nowebgl]');
  await expect(play.or(noGl.filter({ visible: true }))).toBeVisible();
  if (await noGl.isVisible()) {
    await expect(page.locator('[data-ix-still]')).toBeVisible();
    return;
  }
  await expect(play).toBeEnabled();
  await expect(page.locator('[data-ix-stage] canvas')).toHaveCount(1);
  await expect(page.locator('[data-ix-still]')).toBeHidden();

  await page.locator('[data-ix-inspect]').focus();
  await page.keyboard.press('ArrowDown');
  await expect(page.locator('[data-ix-inspect-empty]')).toBeHidden();
  await expect(page.locator('[data-ix-inspect-title]')).not.toHaveText('');

  const tissue = page.locator('[data-ix-layer="tissue"]');
  await tissue.focus();
  await page.keyboard.press('Space');
  await expect(tissue).not.toBeChecked();
  await expect(page.locator('[data-ix-label="cortex"]')).toBeHidden();

  const tour = page.locator('[data-ix-tour]');
  await tour.focus();
  await page.keyboard.press('Enter');
  await expect(tour).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('[data-ix-caption]')).not.toBeEmpty();
  expect(errors).toEqual([]);
});

test('record mode: fixed duration and deterministic frames', async ({ page }, testInfo) => {
  await page.goto('/interface/?record=1');
  const ok = await page
    .waitForFunction(() => window.__record?.ready, null, { timeout: 15_000 })
    .then(() => true)
    .catch(() => false);
  test.skip(!ok, 'no WebGL in this browser');
  const duration = await page.evaluate(() => window.__record!.duration);
  expect(duration).toBeGreaterThan(10);
  const shot = async (t: number) => {
    await page.evaluate((s) => window.__seek!(s), t);
    return page.locator('[data-ix-stage]').screenshot();
  };
  const a = await shot(7.5);
  await shot(2);
  const b = await shot(7.5);
  if (!a.equals(b)) {
    // keep both frames for diagnosis (clinical-only flake, web-e2e finding)
    await testInfo.attach('frame-a-7.5s.png', { body: a, contentType: 'image/png' });
    await testInfo.attach('frame-b-7.5s-after-reseek.png', { body: b, contentType: 'image/png' });
    const c = await shot(7.5);
    await testInfo.attach('frame-c-7.5s-third.png', { body: c, contentType: 'image/png' });
    testInfo.annotations.push({ type: 'b-equals-c', description: String(b.equals(c)) });
  }
  expect(a.equals(b)).toBe(true);
  await expect(page.locator('body > header')).toBeHidden();
});

test('reduced motion: still image first, scene on request', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/interface/');
  await expect(page.locator('[data-ix-still]')).toBeVisible();
  const show = page.locator('[data-ix-show]');
  if (await show.isVisible()) {
    await show.focus();
    await page.keyboard.press('Enter');
    // focus lands on the scene, not <body> (web-a11y T12)
    await expect(page.locator('[data-ix-stage]')).toBeFocused();
    await expect(page.locator('[data-ix-play]')).toHaveText('Play');
    await expect(page.locator('[data-ix-stage]')).toBeFocused();
  }
});

test('keyboard orbit on the focused scene; reduced motion mid-run pauses', async ({ page }) => {
  await page.goto('/interface/');
  const play = page.locator('[data-ix-play]');
  const noGl = page.locator('[data-ix-nowebgl]');
  await expect(play.or(noGl.filter({ visible: true }))).toBeVisible();
  test.skip(await noGl.isVisible(), 'no WebGL in this browser');
  await expect(play).toBeEnabled();
  const stage = page.locator('[data-ix-stage]');
  await stage.focus();
  await expect(stage).toBeFocused();
  await expect(stage).toHaveAttribute('role', 'group');
  await play.click(); // pause so frames only change on key presses
  const before = await stage.screenshot();
  await stage.focus();
  await page.keyboard.press('ArrowLeft');
  await page.keyboard.press('ArrowLeft');
  expect((await stage.screenshot()).equals(before)).toBe(false);
  await play.click();
  await expect(play).toHaveText('Pause');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(play).toHaveText('Play');
  await expect(page.locator('[data-ix-tour]')).toHaveAttribute('aria-pressed', 'false');
});

for (const width of [390, 500]) {
  test(`3D labels at ${width} px: none overlap or clip; captions still shown`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/interface/');
    const play = page.locator('[data-ix-play]');
    const noGl = page.locator('[data-ix-nowebgl]');
    await expect(play.or(noGl.filter({ visible: true }))).toBeVisible();
    test.skip(await noGl.isVisible(), 'no WebGL in this browser');
    await page.locator('[data-ix-tour]').click();
    await expect(page.locator('[data-ix-caption]')).not.toBeEmpty();
    const stage = (await page.locator('[data-ix-stage]').boundingBox())!;
    const boxes = await page.$$eval('[data-ix-label]:not(.is-off):not([hidden])', (els) =>
      els.map((e) => e.getBoundingClientRect().toJSON() as DOMRect),
    );
    for (const a of boxes) {
      expect(a.left).toBeGreaterThanOrEqual(stage.x - 0.5);
      expect(a.right).toBeLessThanOrEqual(stage.x + stage.width + 0.5);
      for (const b of boxes)
        if (a !== b)
          expect(
            a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top,
          ).toBe(true);
    }
  });
}
