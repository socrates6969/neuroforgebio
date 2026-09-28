// Owner directive (2026-09-27): no homepage edits. homepage.test.mjs pins the home page's SOURCES;
// this pins what the build EMITS for /: its CSS in load order and its markup, per theme, against
// the committed baselines in test/fixtures (see scripts/home-baseline.mjs for the normalisation).
// / links shared CSS chunks that inner pages also feed, so an inner-page style change can alter
// the home page without touching a home source; this test catches that.
// Baselines change only with the owner's approval: node scripts/home-baseline.mjs --owner-approved
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import {
  THEMES,
  danglingDescribedBy,
  firstDiff,
  fixturePath,
  homeSnapshot,
} from '../scripts/home-baseline.mjs';
import { requireDist } from './_dist.mjs';

for (const theme of THEMES) {
  for (const kind of ['css', 'html']) {
    test(`${theme}: built home page ${kind} equals the approved baseline`, () => {
      const snap = homeSnapshot(requireDist(theme));
      const p = fixturePath(kind, theme);
      assert.ok(existsSync(p), `${p} missing`);
      const d = firstDiff(readFileSync(p, 'utf8'), snap[kind]);
      assert.equal(
        d,
        null,
        `the built / (${theme}) ${kind} changed at ${d}\n` +
          'The home page must not change (owner directive). If an inner-page style moved into a ' +
          'shared chunk, scope it so / is unaffected. Rewrite the baseline only with owner approval.',
      );
    });
  }
  // btn-note ids are renumbered when compared (build-order counter in Button.astro), so check
  // separately that every description on / still resolves in the real build.
  test(`${theme}: every aria-describedby on the built home page points to an existing id`, () => {
    const html = readFileSync(join(requireDist(theme), 'index.html'), 'utf8');
    assert.ok(/aria-describedby=/.test(html), 'expected aria-describedby on / (disabled CTAs)');
    assert.deepEqual(danglingDescribedBy(html), []);
  });
}

// The normaliser itself, on throwaway dists: chunk boundaries and hashes are not changes; rule
// order, rule content and component scoping are.
const made = [];
function fakeDist(sheets, body) {
  const d = mkdtempSync(join(tmpdir(), 'nf-home-'));
  made.push(d);
  mkdirSync(join(d, '_assets'));
  const links = Object.entries(sheets).map(([name, css]) => {
    writeFileSync(join(d, '_assets', name), css);
    return `<link rel="stylesheet" href="/_assets/${name}">`;
  });
  writeFileSync(
    join(d, 'index.html'),
    `<html><head>${links.join('')}</head><body>${body}</body></html>`,
  );
  return d;
}

test('home snapshot: a moved chunk boundary or new hash is not a change; order, rules, scoping are', (t) => {
  t.after(() => made.forEach((d) => rmSync(d, { recursive: true, force: true })));
  const body = '<p class="a" data-astro-cid-aaaa1111>x</p>';
  const base = homeSnapshot(
    fakeDist(
      {
        'x.AbCd1234.css': '.a[data-astro-cid-aaaa1111]{color:red}',
        'y.EfGh5678.css': '.b{margin:0}',
      },
      body,
    ),
  );
  const merged = homeSnapshot(
    fakeDist(
      { 'z.ZyXw9876.css': '.a[data-astro-cid-bbbb2222]{color:red}\n.b{margin:0}' },
      body.replace('aaaa1111', 'bbbb2222'),
    ),
  );
  assert.equal(firstDiff(base.css, merged.css), null);
  assert.equal(firstDiff(base.html, merged.html), null);
  const reordered = homeSnapshot(
    fakeDist(
      {
        'y.EfGh5678.css': '.b{margin:0}',
        'x.AbCd1234.css': '.a[data-astro-cid-aaaa1111]{color:red}',
      },
      body,
    ),
  );
  assert.notEqual(firstDiff(base.css, reordered.css), null, 'cascade order change must be caught');
  const edited = homeSnapshot(
    fakeDist(
      {
        'x.AbCd1234.css': '.a[data-astro-cid-aaaa1111]{color:blue}',
        'y.EfGh5678.css': '.b{margin:0}',
      },
      body,
    ),
  );
  assert.match(firstDiff(base.css, edited.css), /^line 1:/);
  // a rule re-scoped to another component (different cid than the element) must differ
  const rescoped = homeSnapshot(
    fakeDist(
      {
        'x.AbCd1234.css': '.a[data-astro-cid-cccc3333]{color:red}',
        'y.EfGh5678.css': '.b{margin:0}',
      },
      body,
    ),
  );
  assert.notEqual(firstDiff(base.html, rescoped.html), null);
});

test('btn-note ids: a build-order shift compares equal; a changed label or broken pairing does not', () => {
  const page = (n, label = 'Join early access', ref = n) =>
    `<button disabled aria-describedby="btn-note-${ref}">${label}</button>
` +
    `<small id="btn-note-${n}">Opens soon</small>
` +
    `<button disabled aria-describedby="btn-note-${n + 1}">More</button>
<small id="btn-note-${n + 1}">x</small>
`;
  assert.equal(firstDiff(page(34), page(35)), null, 'only the counter moved');
  assert.match(firstDiff(page(34), page(35, 'Join the list')), /^line 1:/, 'label change');
  // the first button now describes the second note: renumbering must not hide that
  assert.notEqual(firstDiff(page(34), page(35, 'Join early access', 36)), null, 'pairing change');
  assert.deepEqual(danglingDescribedBy(page(34, 'x', 99)), ['btn-note-99']);
  assert.deepEqual(danglingDescribedBy(page(34)), []);
});
