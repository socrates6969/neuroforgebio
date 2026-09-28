// CI-ONLY (see playwright.config.ts): never run locally on the 3 GB dev machine.
//
// EXC-150-1 condition 7 (ADR 0014) browser tests for the REAL Decoder Arena state -- a wasm
// bundle actually built and committed at apps/web/src/assets/arena/pkg/ (a CI-built, security-
// reviewed artifact; see tools/arena-core/README.md). Every test below skips itself via
// arenaPkgAvailable() (the exact same function astro.config.mjs and index.astro use to decide
// real-vs-stub at build time), so this file can never drift from what the build actually shipped.
// It's fully inert today (pkg/ doesn't exist) and activates with no other change once an
// owner-dispatched arena-wasm.yml run lands a real one.
//
// Three checks, per condition 7 (web-e2e, 2026-09-27): every OTHER route's zero-CSP-violation
// baseline is already covered by security.spec.ts's SEC-150/155 loop over PAGES, so this file
// only needs the arena-specific positive case and the two checks that show the exception is
// exactly as narrow as claimed:
//   (a) /arena decodes under its own (real, served) CSP -- a full run completes, no violations.
//   (b) eval('1') on /arena still raises a CSP violation -- 'wasm-unsafe-eval' allows compiling
//       WebAssembly only, never general eval/Function, so the exception must not leak into that.
//   (c) with the token stripped from /arena's response (simulating the exception's absence), the
//       wasm compile visibly fails, reporting a script-src violation -- proves the exception is
//       load-bearing, not a no-op.
import { expect, test, type Page } from '@playwright/test';
import { collectErrors } from './util';
// Same functions scripts/build.mjs, astro.config.mjs and the dist-level node tests already use;
// safe to reuse here since e2e specs run from this checkout, against a dist built from it.
import { csp } from '../security-headers.mjs';
import { arenaPkgAvailable } from '../src/lib/arena-pkg.mjs';

const REAL_PKG = arenaPkgAvailable();
const SKIP_REASON = 'apps/web/src/assets/arena/pkg/ is absent (stub state)';

interface CspEvent {
  violatedDirective: string;
  blockedURI: string;
}

/** Records CSP violations from the first byte: console messages AND the securitypolicyviolation
 * DOM event (structured, so tests can assert on the exact violated directive rather than
 * pattern-matching free-text console output). Same technique as security.spec.ts's watchCsp.
 * TODO(web-e2e): move a shared version into util.ts and drop this local copy once that lands. */
function watchCsp(page: Page) {
  const consoleMessages: string[] = [];
  page.on('console', (m) => {
    if (/Content Security Policy|Refused to (load|execute|apply)|EvalError/i.test(m.text()))
      consoleMessages.push(m.text());
  });
  page.addInitScript(() => {
    const w = window as unknown as { __csp: CspEvent[] };
    w.__csp = [];
    document.addEventListener('securitypolicyviolation', (e) =>
      w.__csp.push({ violatedDirective: e.violatedDirective, blockedURI: e.blockedURI }),
    );
  });
  return async () => ({
    console: consoleMessages,
    events: await page.evaluate(() => (window as unknown as { __csp: CspEvent[] }).__csp ?? []),
  });
}

test('(a) /arena decodes under its own served CSP: a run completes, zero CSP violations', async ({
  page,
}) => {
  test.skip(!REAL_PKG, SKIP_REASON);
  const violations = watchCsp(page);
  const errors = collectErrors(page);
  await page.goto('/arena/', { waitUntil: 'networkidle' });

  const run = page.locator('[data-arena-run]');
  await expect(run).toBeEnabled({ timeout: 15_000 });
  await run.click();
  await expect(page.locator('[data-arena-card] .arena-nums')).toBeVisible({ timeout: 15_000 });
  // The card must show a real number, not the pre-run placeholder.
  await expect(page.locator('[data-arena-card] .big')).not.toHaveText('–');
  const { console: consoleLogs, events } = await violations();
  expect(consoleLogs).toEqual([]);
  expect(events).toEqual([]);
  expect(errors).toEqual([]);
});

test("(b) eval('1') on /arena still raises a CSP violation (the exception is wasm-only)", async ({
  page,
}) => {
  test.skip(!REAL_PKG, SKIP_REASON);
  const violations = watchCsp(page);
  await page.goto('/arena/', { waitUntil: 'networkidle' });

  const result = await page.evaluate(() => {
    try {
      // eslint-disable-next-line no-eval
      return { ran: true, value: (0, eval)('1') };
    } catch (e) {
      return { ran: false, message: (e as Error).message };
    }
  });
  expect(result.ran, `eval('1') must be blocked by CSP, got: ${JSON.stringify(result)}`).toBe(
    false,
  );
  const { console: consoleLogs, events } = await violations();
  expect(
    events.some((e) => e.violatedDirective === 'script-src') || consoleLogs.length > 0,
    `expected a script-src CSP violation, got events=${JSON.stringify(events)} console=${JSON.stringify(consoleLogs)}`,
  ).toBe(true);
});

test('(c) stripping the /arena exception token from the response makes the wasm compile fail, reporting script-src', async ({
  page,
}) => {
  test.skip(!REAL_PKG, SKIP_REASON);
  // Rewrite the response's CSP down to the baseline (security-headers.mjs's csp() with no route
  // arg -- no exception tokens, what every non-excepted page gets), so the same real wasm bundle
  // is served but without the permission to compile it.
  const baseline = csp();
  await page.route('**/arena/', async (route) => {
    const response = await route.fetch();
    await route.fulfill({
      response,
      headers: { ...response.headers(), 'content-security-policy': baseline },
    });
  });
  const violations = watchCsp(page);
  await page.goto('/arena/', { waitUntil: 'networkidle' });
  // The evaluator's own init() catches a failed wasm compile and shows this status text
  // (arena.ts's `el.dataset.wasmError`) rather than leaving the page in a "loading" state.
  const status = page.locator('[data-arena-status]');
  await expect(status).toBeVisible({ timeout: 15_000 });
  await expect(status).not.toHaveText('Loading the evaluator…');
  const { events } = await violations();
  expect(
    events.some((e) => e.violatedDirective === 'script-src'),
    `expected a script-src violation from the blocked wasm compile, got: ${JSON.stringify(events)}`,
  ).toBe(true);
});
