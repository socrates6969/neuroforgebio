// Neural Playground (/playground): replay loads under the strict CSP, draws, and every control works
// from the keyboard; reduced motion means no autoplay. Runs locally too (bci-queen slot) and in CI,
// like the rest of e2e.
import { expect, test } from '@playwright/test';
import { collectErrors } from './util';

const R2 = '[data-pg-r2="test"]';

test('replay loads, draws and responds to keyboard-only controls', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto('/playground/');
  const play = page.locator('[data-pg-play]');
  await expect(play).toBeEnabled();
  await expect(page.locator('[data-pg-status]')).toBeHidden();

  // every canvas has drawn something
  const painted = await page.$$eval('[data-pg-canvas]', (cs) =>
    (cs as HTMLCanvasElement[]).map((c) => {
      const d = c.getContext('2d')!.getImageData(0, 0, c.width, c.height).data;
      for (let i = 3; i < d.length; i += 4) if (d[i] !== 0) return true;
      return false;
    }),
  );
  expect(painted).toEqual([true, true, true, true]);

  const full = await page.locator(R2).textContent();
  const neurons = page.locator('[data-pg-neurons]');
  await neurons.focus();
  await page.keyboard.press('Home');
  await expect(neurons).toHaveAttribute('aria-valuetext', /^8 /);
  await expect(page.locator(R2)).not.toHaveText(full ?? '');

  const kalman = page.locator('input[name="pg-decoder"][value="kalman"]');
  await page.locator('input[name="pg-decoder"][value="ridge"]').focus();
  await page.keyboard.press('ArrowDown');
  await expect(kalman).toBeChecked();

  await play.focus();
  const label = await play.textContent();
  await page.keyboard.press('Enter');
  await expect(play).not.toHaveText(label ?? '');

  await page.locator('[data-pg-trial]').selectOption('3');
  await expect(page.locator('[data-pg-r2="trial"]')).not.toHaveText('–');
  expect(errors).toEqual([]);
});

test('reduced motion: no autoplay, whole trial shown', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/playground/');
  const play = page.locator('[data-pg-play]');
  await expect(play).toBeEnabled();
  await expect(play).toHaveText('Play');
  const scrub = page.locator('[data-pg-scrub]');
  await expect(scrub).toHaveValue((await scrub.getAttribute('max')) ?? '');
});

test('reduced motion switched on mid-replay stops it', async ({ page }) => {
  await page.goto('/playground/');
  const play = page.locator('[data-pg-play]');
  await expect(play).toBeEnabled();
  // the replay autoplays once the demo scrolls into view (no click: it would race the autoplay)
  await page.locator('[data-pg-canvas="path"]').scrollIntoViewIfNeeded();
  await expect(play).toHaveText('Pause');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(play).toHaveText('Play');
});
