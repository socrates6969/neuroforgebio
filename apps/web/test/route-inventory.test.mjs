// Route inventory (swarm-web-engine coverage gap, 2026-09-27): every built HTML page, both themes,
// must appear in apps/web/e2e/util.ts's PAGES list (or the explicit allowlist below), so a new page
// can't ship without a11y/hero/keyboard/security/visual e2e coverage. This does NOT re-check titles,
// descriptions, canonicals or sitemap membership -- that's test/seo-integrity.test.mjs's job.
//
// PAGES is read as text, not imported: e2e/util.ts is TypeScript, and apps/web/scripts/test.mjs runs
// plain `node --test` with no --experimental-strip-types flag (the project's pinned Node is 22, per
// .nvmrc/engines, where type-stripping needs that flag explicitly). Parsing the array out avoids
// depending on a Node version where bare-.ts import happens to work.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { join } from 'node:path';
import { files, read, requireDist, urlPath } from './_dist.mjs';

const THEMES = ['clinical', 'cosmos'];
const WEB = join(import.meta.dirname, '..');

/** Non-page routes: not HTML documents, or otherwise not something e2e (axe/CSP/keyboard) covers. */
const EXCLUDED_ROUTES = new Set([
  // Nothing yet -- every built HTML page is expected to be in PAGES. Add here (with a reason) only
  // for a route that's genuinely not an e2e concern (e.g. a future preview-only or fixture page).
]);

/** Extracts the PAGES string array from e2e/util.ts by parsing the source text (see header comment). */
function readPages() {
  const src = read(join(WEB, 'e2e/util.ts'));
  const m = src.match(/export const PAGES = \[([\s\S]*?)\];/);
  assert.ok(m, 'e2e/util.ts: could not find "export const PAGES = [...]"');
  return [...m[1].matchAll(/'([^']*)'/g)].map((x) => x[1]);
}

test('every built HTML page is in e2e/util.ts PAGES (or EXCLUDED_ROUTES, with a reason)', () => {
  const pages = new Set(readPages());
  for (const theme of THEMES) {
    const dist = requireDist(theme);
    const built = files(dist, '.html').map((f) => urlPath(dist, f));
    const missing = built.filter((p) => !pages.has(p) && !EXCLUDED_ROUTES.has(p));
    assert.deepEqual(
      missing,
      [],
      `${theme}: built but not in e2e PAGES (add to apps/web/e2e/util.ts, or to ` +
        `EXCLUDED_ROUTES here with a reason): ${missing.join(', ')}`,
    );
  }
});

test('PAGES has no dead entries (every listed route is actually built)', () => {
  const pages = readPages();
  for (const theme of THEMES) {
    const dist = requireDist(theme);
    const built = new Set(files(dist, '.html').map((f) => urlPath(dist, f)));
    const dead = pages.filter((p) => !built.has(p));
    assert.deepEqual(dead, [], `${theme}: in e2e PAGES but not built: ${dead.join(', ')}`);
  }
});

test('EXCLUDED_ROUTES has no stale entries (route was built, or removed from the site)', () => {
  if (EXCLUDED_ROUTES.size === 0) return;
  const dist = requireDist('clinical');
  const built = new Set(files(dist, '.html').map((f) => urlPath(dist, f)));
  for (const route of EXCLUDED_ROUTES)
    assert.ok(built.has(route), `EXCLUDED_ROUTES has "${route}", which is no longer built`);
});
