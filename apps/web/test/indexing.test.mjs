// APP-L8 / P6: preview builds (SITE_STAGE=preview, the default) must not be indexable: robots.txt
// `Disallow: /` and an `X-Robots-Tag: noindex` header on every response. Launch and public builds carry
// neither; single pages opt in to a robots meta with Base's `noindex` prop in every stage. (No per-page
// preview meta: that needs a Base.astro edit, and the home page is frozen by owner directive.)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { ROBOTS_NOINDEX, isIndexable, robotsTxt } from '../indexing.mjs';
import { headerRules, headersForPath, parseHeadersFile } from '../security-headers.mjs';
import { WEB, canonicalOrigin, read, requireDist } from './_dist.mjs';

const THEMES = ['clinical', 'cosmos'];
const META_NOINDEX = /<meta name="robots" content="noindex/;

test('only preview is non-indexable', () => {
  assert.equal(isIndexable('preview'), false);
  assert.equal(isIndexable(undefined), false, 'default stage is preview');
  assert.equal(isIndexable('launch'), true);
  assert.equal(isIndexable('public'), true);
  assert.match(ROBOTS_NOINDEX, /^noindex/);
});

test('robots.txt: preview disallows everything and lists no sitemap; launch/public are crawlable', () => {
  for (const theme of THEMES) {
    const p = robotsTxt({ stage: 'preview', theme, canonicalOrigin });
    assert.match(p, /^User-agent: \*$/m);
    assert.match(p, /^Disallow: \/$/m);
    assert.doesNotMatch(p, /^Allow:|^Sitemap:/m);
    for (const stage of ['launch', 'public']) {
      const t = robotsTxt({ stage, theme, canonicalOrigin });
      assert.doesNotMatch(t, /^Disallow: \/$/m, `${stage} ${theme}`);
      assert.match(t, /^Allow: \/$/m);
      if (theme === 'clinical') assert.match(t, /^Sitemap: https:\/\/.+\/sitemap\.xml$/m);
      else assert.doesNotMatch(t, /^Sitemap:/m);
    }
  }
});

test('X-Robots-Tag on every path in preview only', () => {
  const paths = ['/', '/security/', '/.well-known/security.txt'];
  const preview = headerRules({ stage: 'preview', paths });
  for (const p of [...paths, '/_assets/x.js'])
    assert.equal(headersForPath(preview, p)['X-Robots-Tag'], ROBOTS_NOINDEX, p);
  for (const stage of ['launch', 'public'])
    for (const p of paths)
      assert.equal(headersForPath(headerRules({ stage, paths }), p)['X-Robots-Tag'], undefined);
});

test('built dists follow their stage (robots.txt, _headers, _headers.json)', () => {
  for (const t of THEMES) {
    const dist = requireDist(t);
    const json = JSON.parse(read(join(dist, '_headers.json')));
    const stage = json.stage;
    const robots = read(join(dist, 'robots.txt'));
    assert.equal(robots, robotsTxt({ stage, theme: t, canonicalOrigin }), `${t} robots.txt`);
    const fromFile = headersForPath(parseHeadersFile(read(join(dist, '_headers'))), '/');
    const fromJson = headersForPath(json.rules, '/');
    if (!isIndexable(stage)) {
      assert.match(robots, /^Disallow: \/$/m);
      assert.equal(fromFile['X-Robots-Tag'], ROBOTS_NOINDEX, `${t} _headers`);
      assert.equal(fromJson['X-Robots-Tag'], ROBOTS_NOINDEX, `${t} _headers.json`);
    } else {
      assert.doesNotMatch(robots, /^Disallow: \/$/m);
      assert.equal(fromFile['X-Robots-Tag'], undefined);
      assert.equal(fromJson['X-Robots-Tag'], undefined);
      assert.doesNotMatch(read(join(dist, 'index.html')), META_NOINDEX);
    }
  }
});

test(
  'a SITE_STAGE=launch astro build has no noindex meta on indexable pages and a crawlable robots.txt',
  { skip: process.env.NF_WEB_REBUILD_TEST === '1' ? false : 'set NF_WEB_REBUILD_TEST=1 (slow)' },
  () => {
    const out = mkdtempSync(join(tmpdir(), 'nf-web-launch-'));
    try {
      const require = createRequire(join(WEB, 'package.json'));
      const astro = join(dirname(require.resolve('astro/package.json')), 'astro.js');
      const r = spawnSync(process.execPath, [astro, 'build'], {
        cwd: WEB,
        stdio: 'inherit',
        env: {
          ...process.env,
          THEME: 'clinical',
          SITE_STAGE: 'launch',
          NF_WEB_OUT_DIR: out,
          ASTRO_TELEMETRY_DISABLED: '1',
        },
      });
      assert.equal(r.status, 0, 'astro build');
      const robots = read(join(out, 'robots.txt'));
      assert.doesNotMatch(robots, /^Disallow: \/$/m);
      assert.match(robots, /^Sitemap: /m);
      for (const p of ['index.html', 'security/index.html', 'platform/index.html'])
        assert.doesNotMatch(read(join(out, p)), META_NOINDEX, p);
      assert.match(read(join(out, 'gallery/index.html')), META_NOINDEX, 'gallery stays noindex');
    } finally {
      rmSync(out, { recursive: true, force: true });
    }
  },
);
