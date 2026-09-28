// Owner directive (2026-09-27): no homepage edits. The home page's sources must be unchanged against
// the merge-base with main, and the built home page must not link the demo routes. Feature pages
// (/playground/, /interface/) are reached from their own links and the sitemap, never from /.
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { join } from 'node:path';
import { test } from 'node:test';
import { REPO, attrs, read, requireDist } from './_dist.mjs';

// Everything that renders on /: the page, its copy, the shared layout and chrome.
const HOME_SOURCES = [
  'apps/web/src/pages/index.astro',
  'apps/web/src/layouts/Base.astro',
  'packages/content/content/home.json',
  'packages/content/content/site.json',
  'packages/ui/src/components',
  'packages/themes/clinical/slots',
  'packages/themes/cosmos/slots',
];

const git = (...args) => spawnSync('git', ['-C', REPO, ...args], { encoding: 'utf8' });

function mainRef() {
  for (const ref of ['origin/main', 'main'])
    if (git('rev-parse', '--verify', '--quiet', ref).status === 0) return ref;
  return null;
}

test(
  'home page sources are unchanged against main',
  { skip: !mainRef() && 'no main ref in this checkout' },
  () => {
    const base = git('merge-base', 'HEAD', mainRef()).stdout.trim();
    assert.match(base, /^[0-9a-f]{40}$/, 'merge-base with main');
    // committed and working-tree changes both count
    const r = git('diff', '--name-only', base, '--', ...HOME_SOURCES);
    assert.equal(r.status, 0, r.stderr);
    assert.deepEqual(r.stdout.split('\n').filter(Boolean), [], 'home page files changed');
  },
);

test('built home page does not link the demo routes', () => {
  for (const t of ['clinical', 'cosmos']) {
    const html = read(join(requireDist(t), 'index.html'));
    const hrefs = attrs(html, 'a', 'href').map((a) => a.value);
    for (const route of ['/playground', '/interface'])
      assert.ok(!hrefs.some((h) => h.startsWith(route)), `${t}: / links ${route}`);
  }
});
