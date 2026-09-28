// /arena in its current STUB state (apps/web/src/assets/arena/pkg/ absent -- the normal state
// today, see tools/arena-core/README.md): noindex is served while there's no real decoder, and the
// stub page itself raises no CSP violations. Assertions only, no visual baseline. Runs locally too
// (bci-queen slot) and in CI. Complements apps/web/e2e/arena-real.spec.ts (nfb-arena, condition 7),
// which covers the opposite state (a real pkg/) and self-skips until one exists -- this file is the
// mirror: it only makes sense while the stub is what's actually built, so it skips itself once a
// real pkg/ ships (arena-real.spec.ts takes over from there).
import { expect, test } from '@playwright/test';
import { collectErrors } from './util';

test('stub /arena is noindex while no wasm is built in', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto('/arena/', { waitUntil: 'networkidle' });
  const isStub = await page.locator('[data-arena-unavailable]').isVisible();
  test.skip(!isStub, 'a real pkg/ is built in -- arena-real.spec.ts covers this state instead');

  const robots = page.locator('meta[name="robots"]');
  await expect(robots).toHaveAttribute('content', /noindex/);
  expect(errors).toEqual([]);
});

test('stub /arena raises no console CSP violations', async ({ page }) => {
  const errors = collectErrors(page);
  const cspLogs: string[] = [];
  page.on('console', (m) => {
    if (/Content Security Policy|Refused to (load|execute|apply)/i.test(m.text()))
      cspLogs.push(m.text());
  });
  await page.goto('/arena/', { waitUntil: 'networkidle' });
  const isStub = await page.locator('[data-arena-unavailable]').isVisible();
  test.skip(!isStub, 'a real pkg/ is built in -- arena-real.spec.ts covers this state instead');

  expect(cspLogs).toEqual([]);
  expect(errors).toEqual([]);
});
