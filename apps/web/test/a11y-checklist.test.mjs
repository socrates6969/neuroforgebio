// Automates the "review by eye" rows of docs/web/a11y-checklist.md that had no test yet: row 2
// (grid/flex reflow risk), rows 3-4 (aria-live shape), row 5 (title-only info) and row 7 (range
// aria-valuetext). Row 1 already has theme-tokens.test.mjs/style-lint.test.mjs; row 6 (content
// system vs. string literals) needs human judgement and isn't attempted here.
//
// Every checker lives in ./a11y-checklist-lib.mjs with its own heuristic and documented blind spots.
// They are static checks, not a browser: none of them can tell whether content *actually* overflows
// or what a real screen reader announces. apps/web/e2e/a11y.spec.ts (axe) and
// apps/web/e2e/visual.spec.ts (real layout at 360/768/1440px) stay the ground truth; this file
// catches the specific bug *shapes* docs/hive/A11Y-AUDIT.md already found once, before they recur.
//
// Row 2 reads each page's LINKED stylesheets: astro.config.mjs sets inlineStylesheets: 'never'
// (SEC-150a), so built pages carry no <style> blocks at all. Grid/flex containers come from
// component-scoped rules (Astro's data-astro-cid attribute) and from sheets that not every inner page
// links; unscoped rules from the site-wide bundle (packages/themes, `nf-*` utilities, shared with the
// frozen homepage) are excluded as containers -- attributing a shared utility rule to one page's
// layout needs a human. Escape/risk properties are read from all linked CSS.
//
// Row 2's rule is "real reflow risk", not "every container needs min-width:0". A container is a
// finding only when BOTH (a) one of its items has no escape -- the escapes are: every grid column
// track has a fixed minimum (minmax(0,1fr), 220px, ...), a rule matching the item sets
// min-width:0, or the item itself scrolls -- AND (b) that item holds something unbreakable-width:
// a <pre>, an overflow-x:auto/scroll box, or a run of 40+ characters with no break opportunity (a
// hash, a URL, or white-space:nowrap text). Flex column containers are skipped. Full heuristic
// and its limits: the row 2 comment in a11y-checklist-lib.mjs.
//
// The home page ("/") is excluded everywhere: this checklist is scoped to "new or changed pages" and
// the homepage is frozen (WEB-PLAN rule 1). Never edits anything: a real finding is reported to the
// page's owner, not fixed or weakened here.
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { files, read, requireDist, urlPath, WEB } from './_dist.mjs';
import {
  applyExceptions,
  countLiveRegions,
  duplicateLiveProblems,
  exceptionShapeProblems,
  gridFlexMinWidthProblems,
  innerHtmlIntoLiveProblems,
  liveStructureProblems,
  normalizeSelector,
  rangeProblems,
  resolvePageScripts,
  scriptSyncsValuetext,
  titleOnlyProblems,
} from './a11y-checklist-lib.mjs';

const THEMES = ['clinical', 'cosmos'];
const FIXTURES = join(import.meta.dirname, 'fixtures/a11y-checklist');
const fx = (name) => readFileSync(join(FIXTURES, name), 'utf8');
const styleBlocks = (html) =>
  [...html.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/gi)].map((m) => m[1]).join('\n');
const messages = (problems) => problems.map((p) => p.message);
const row2 = (name, html = fx(name)) => gridFlexMinWidthProblems(name, styleBlocks(html), html);

/**
 * Known, accepted exceptions: { row, route, selector, reason }. `row` is 2, 3, 4, 5 or 7; `route`
 * is the built page path ('/gallery/'); `selector` is exactly the string the finding reports (row 2:
 * the container's source selector, e.g. '.blocks'; rows 3/5/7: the element handle, e.g.
 * 'input[data-pg-scrub]'; row 4: '<visible> + <hidden>'); `reason` is one line on why it's fine.
 * Nothing in page markup can opt out -- exceptions live only here, reviewed like code. An entry that
 * no longer matches any real finding fails the "no stale entries" test below, so the list can
 * only shrink: a fixed item must be removed. Each entry also carries its reason as a `//` comment
 * above it. Adding one needs web-a11y's sign-off and web-queen's OK, and it must be listed as a
 * finding (page, selector, reason) so the fix can be routed. Empty: every finding is real.
 */
const A11Y_EXCEPTIONS = [];

/* ------------------------------------------------------------------------------- exceptions */

test('exception helper: drops exact route+selector matches and reports unused entries', () => {
  const problems = [
    { row: 2, route: '/a/', selector: '.x', message: 'a' },
    { row: 5, route: '/b/', selector: 'span[title="y"]', message: 'b' },
    { row: 2, route: '/c/', selector: '.x', message: 'c' },
  ];
  const exceptions = [
    { row: 2, route: '/a/', selector: '.x', reason: 'r' },
    { row: 2, route: '/gone/', selector: '.x', reason: 'r' },
    { row: 7, route: '/b/', selector: 'span[title="y"]', reason: 'r' }, // right key, wrong row
  ];
  const used = new Set();
  assert.deepEqual(messages(applyExceptions(problems, exceptions, used)), ['b', 'c']);
  assert.deepEqual([...used], [0], 'only the first entry matched; the other two are stale');
  const bad = [
    { row: 6, route: 'x', selector: ' ', reason: '' },
    { row: 2, route: '/a/', selector: '.x', reason: 'r' },
    { row: 2, route: '/a/', selector: '.x', reason: 'r' },
  ];
  assert.equal(exceptionShapeProblems(bad).length, 5, exceptionShapeProblems(bad).join('\n'));
});

test('A11Y_EXCEPTIONS is well-formed and has no stale entry (each still matches a real finding)', () => {
  assert.deepEqual(exceptionShapeProblems(A11Y_EXCEPTIONS), []);
  if (A11Y_EXCEPTIONS.length === 0) return;
  const used = new Set();
  for (const theme of THEMES) applyExceptions(realResults(theme).all, A11Y_EXCEPTIONS, used);
  const stale = A11Y_EXCEPTIONS.filter((_, i) => !used.has(i));
  assert.deepEqual(stale, [], 'these entries match no finding in either theme: remove them');
});

/* ------------------------------------------------------------------------------ row 2 fixtures */

test('row 2: Astro scoped selectors (attribute strategy, as built) print as their source form', () => {
  // Verbatim from the real Astro 5.18.2 build (web-integration dist/clinical/_assets, 2026-09-27).
  assert.equal(
    normalizeSelector('.blocks[data-astro-cid-sahthylw]>section[data-astro-cid-sahthylw]'),
    '.blocks>section',
  );
  assert.equal(normalizeSelector('.docs[data-astro-cid-pvnjvmu4]'), '.docs');
  // The other scopedStyleStrategy's forms, in case the config ever changes.
  assert.equal(normalizeSelector('.docs:where([data-astro-cid-pvnjvmu4])'), '.docs');
  assert.equal(normalizeSelector(':where(.grid)[data-astro-cid-t3st0002]'), '.grid');
});

test('row 2: the gallery/PipelineSteps bug shape is caught (grid item holding a scrolling <pre>)', () => {
  const { problems, containers } = row2('row2-bad.html');
  assert.equal(containers, 2, 'examines .blocks and the component .code grid');
  assert.equal(problems.length, 1, messages(problems).join('\n'));
  assert.equal(problems[0].selector, '.blocks');
  assert.match(problems[0].message, /section#g-PipelineSteps.*<pre>/);
});

test('row 2: each accepted escape passes, and fails again once the escape is removed', () => {
  for (const [name, containersExpected, strip] of [
    // .blocks > section { min-width: 0 } -- the gallery.astro fix
    ['row2-good-combinator.html', 2, (css) => css.replace(/;min-width:0/g, '')],
    // .grid 220px 1fr + .main { min-width: 0 } -- PageBody/SecurityPage
    ['row2-good-domclass.html', 1, (css) => css.replace(/;min-width:0/g, '')],
    // .docs 220px minmax(0,1fr) -- DocsShell
    ['row2-good-selfmitigate.html', 1, (css) => css.replace('minmax(0,1fr)', '1fr')],
  ]) {
    const html = fx(name);
    const good = gridFlexMinWidthProblems(name, styleBlocks(html), html);
    assert.equal(good.containers, containersExpected, name);
    assert.deepEqual(messages(good.problems), [], name);
    const stripped = strip(styleBlocks(html));
    assert.notEqual(stripped, styleBlocks(html), `${name}: the escape to strip wasn't found`);
    const bad = gridFlexMinWidthProblems(name, stripped, html);
    assert.equal(bad.problems.length, 1, `${name} without its escape: ${messages(bad.problems)}`);
  }
});

test('row 2: each container instance is judged alone (a fixed twin cannot mask a broken one)', () => {
  const { problems, containers } = row2('row2-bad-two-instances.html');
  assert.equal(containers, 2);
  assert.equal(problems.length, 1, messages(problems).join('\n'));
  assert.equal(problems[0].selector, '.grid');
  assert.match(problems[0].message, /item <div\.risky>/);
});

test('row 2: containers with nothing unbreakable inside are not findings (no false positives)', () => {
  const { problems, containers } = row2('row2-good-norisk.html');
  assert.equal(containers, 4, '.cards, .row, .meta, .split examined; the column .stack skipped');
  assert.deepEqual(messages(problems), []);
});

test('row 2: a hash, a long nowrap label and a URL each count as unbreakable-width', () => {
  const { problems, containers } = row2('row2-bad-tokens.html');
  assert.equal(containers, 3);
  assert.deepEqual(
    problems.map((p) => p.selector),
    ['.facts', '.tags', '.links'],
    messages(problems).join('\n'),
  );
  for (const p of problems) assert.match(p.message, /40\+-character run/);
});

/* ------------------------------------------------------------------------- rows 3-4 fixtures */

test('row 3: a visible live region holding a table is caught; aria-live="off" is not live', () => {
  const bad = liveStructureProblems('row3-bad', fx('row3-bad-visible-structural.html'));
  assert.equal(bad.length, 1, messages(bad).join('\n'));
  assert.equal(bad[0].row, 3);
  const good = fx('row3-good.html');
  assert.equal(countLiveRegions(good), 1, 'the hidden status line counts, the off <output> not');
  assert.deepEqual(liveStructureProblems('row3-good', good), []);
  assert.deepEqual(duplicateLiveProblems('row3-good', good, []), []);
});

test('row 3b: a script that re-renders a live region via innerHTML is caught', () => {
  const bad = innerHtmlIntoLiveProblems('row3b-bad', fx('row3b-bad.html'), fx('row3b-bad.js'));
  assert.equal(bad.length, 1, messages(bad).join('\n'));
  assert.deepEqual(
    innerHtmlIntoLiveProblems('row3b-good', fx('row3b-good.html'), fx('row3b-good.js')),
    [],
  );
});

test('row 4: the /arena bug is caught from the script (one run updates both regions)', () => {
  const html = fx('row4-bad-arena.html');
  assert.equal(countLiveRegions(html), 2);
  const bad = duplicateLiveProblems('row4-bad', html, [fx('row4-bad-arena.ts')]);
  assert.equal(bad.length, 1, messages(bad).join('\n'));
  assert.equal(bad[0].selector, 'div[data-arena-card] + p[data-arena-live]');
  assert.match(bad[0].message, /same handler/);
});

test('row 4: without a resolvable script, the /arena markup is caught structurally', () => {
  const bad = duplicateLiveProblems('row4-bad', fx('row4-bad-arena.html'), []);
  assert.equal(bad.length, 1, messages(bad).join('\n'));
  assert.match(bad[0].message, /same <div\[data-arena\]>/);
});

test('row 4: live regions with different purposes pass (error summary + saved confirmation)', () => {
  const form = fx('row4-good-form.html');
  assert.equal(countLiveRegions(form), 2);
  assert.deepEqual(messages(duplicateLiveProblems('form', form, [fx('row4-good-form.js')])), []);
  // Non-vacuity: they share a <form>, so it's the script evidence that clears them.
  assert.equal(duplicateLiveProblems('form', form, []).length, 1);
  const separate = fx('row4-good-separate.html');
  assert.equal(countLiveRegions(separate), 2);
  assert.deepEqual(messages(duplicateLiveProblems('separate', separate, [])), []);
});

/* ------------------------------------------------------------------------------ row 5 fixtures */

test('row 5: title-only information is caught (the /docs/api span, an icon, an abbr)', () => {
  const bad = titleOnlyProblems('row5-bad', fx('row5-bad.html'));
  assert.deepEqual(
    bad.map((p) => p.selector),
    [
      'span[title="text/event-stream of run.state events, one per line"]',
      'span[title="Verified against the DANDI checksum"]',
      'abbr[title="World Health Organization"]',
    ],
    messages(bad).join('\n'),
  );
});

test('row 5: every allowed title= shape passes (img alt=title, iframe, labels, text elsewhere)', () => {
  const html = fx('row5-good.html');
  // Strip comments before finding <body>: the fixture's own header comment mentions "<body>" in
  // its prose (describing what follows), so a bare indexOf('<body') matches that text, not the
  // real tag, and pulls the comment's illustrative example (`<img title="X" alt="X">`) into the
  // count below.
  const withoutComments = html.replace(/<!--[\s\S]*?-->/g, (m) => ' '.repeat(m.length));
  const body = html.slice(withoutComments.indexOf('<body'));
  assert.equal((body.match(/\stitle="/g) ?? []).length, 8, 'fixture has 8 title attributes');
  assert.deepEqual(messages(titleOnlyProblems('row5-good', html)), []);
  const noAlt = html.replace('alt="Mean R² by decoder"', 'alt=""');
  assert.notEqual(noAlt, html);
  assert.equal(titleOnlyProblems('row5-good', noAlt).length, 1, 'img without the matching alt');
});

/* ------------------------------------------------------------------------------ row 7 fixtures */

test('row 7: only a range WITH a companion value display needs aria-valuetext', () => {
  const bare = rangeProblems('bare', fx('row7-bare-good.html'));
  assert.deepEqual([bare.ranges, bare.withCompanion, bare.problems.length], [1, 0, 0]);
  const output = rangeProblems('output', fx('row7-output-bad.html'));
  assert.deepEqual([output.ranges, output.withCompanion], [1, 1]);
  assert.equal(output.problems.length, 1, messages(output.problems).join('\n'));
  assert.match(output.problems[0].message, /<output for="gain">.*row 7a/);
  const nearby = rangeProblems('nearby', fx('row7a-bad.html'));
  assert.equal(nearby.problems.length, 1, 'the /arena bug: <output> in the same <label>');
  const good = rangeProblems('good', fx('row7a-good.html'));
  assert.deepEqual([good.withCompanion, good.problems.length], [1, 0]);
});

test('row 7: the /playground pattern passes (JS-only form, both ranges synced by the script)', () => {
  const r = rangeProblems('pg', fx('row7-playground-good.html'), [fx('row7-playground-good.ts')]);
  assert.deepEqual([r.ranges, r.withCompanion], [2, 2]);
  assert.deepEqual(messages(r.problems), []);
});

test('row 7: a readout found only through the script still requires aria-valuetext', () => {
  const html = fx('row7-script-companion-bad.html');
  const r = rangeProblems('speed', html, [fx('row7-script-companion-bad.ts')]);
  assert.deepEqual([r.ranges, r.withCompanion], [1, 1]);
  assert.equal(r.problems.length, 2, messages(r.problems).join('\n'));
  assert.match(r.problems[0].message, /row 7a/);
  assert.match(r.problems[1].message, /row 7b/);
  // Without the script there is no evidence of a companion: a bare range, which passes.
  assert.equal(rangeProblems('speed', html).withCompanion, 0);
});

test('row 7b: handler sync heuristic (inline write, one call level, and the bug)', () => {
  assert.equal(scriptSyncsValuetext(fx('row7b-bad.ts')), false, 'no aria-valuetext update');
  assert.equal(scriptSyncsValuetext(fx('row7b-bad.ts'), 'neurons'), false);
  assert.equal(scriptSyncsValuetext(fx('row7b-good-inline.ts')), true, 'arena.ts-style inline');
  assert.equal(scriptSyncsValuetext(fx('row7b-good-inline.ts'), 'units'), true);
  assert.equal(scriptSyncsValuetext(fx('row7b-good-inline.ts'), 'unitsOut'), false, 'wrong range');
  assert.equal(
    scriptSyncsValuetext(fx('row7b-good-indirect.ts')),
    true,
    'playground.ts-style this.settingsChanged() indirection',
  );
});

/* -------------------------------------------------------------------------------- real dist */

const stylesheetHrefs = (html) =>
  [...html.matchAll(/<link\b[^>]*>/gi)]
    .map((m) => m[0])
    .filter((tag) => /\srel\s*=\s*["']?stylesheet\b/i.test(tag))
    .map((tag) => /\shref\s*=\s*["']([^"']+)["']/i.exec(tag)?.[1])
    .filter(Boolean);

const realCache = new Map();

/** Every row's findings (before exceptions) over one theme's built inner pages, computed once. */
function realResults(theme) {
  if (realCache.has(theme)) return realCache.get(theme);
  const dist = requireDist(theme);
  const pages = files(dist, '.html')
    .map((f) => ({ f, route: urlPath(dist, f) }))
    .filter((p) => p.route !== '/')
    .map((p) => ({ ...p, html: read(p.f) }));
  // A stylesheet every inner page links is the site-wide bundle (see header).
  const linkCount = new Map();
  for (const p of pages)
    for (const href of new Set(stylesheetHrefs(p.html)))
      linkCount.set(href, (linkCount.get(href) ?? 0) + 1);
  const cssText = new Map();
  const r = {
    pages: pages.length,
    stylesheets: 0,
    containers: 0,
    liveRegions: 0,
    ranges: 0,
    withCompanion: 0,
    rows: { 2: [], 3: [], 4: [], 5: [], 7: [] },
  };
  for (const { f, route, html } of pages) {
    // A checker exception must be visible, not silently swallowed into a false pass.
    const guard = (row, fn) => {
      try {
        fn();
      } catch (err) {
        r.rows[row].push({
          row,
          route,
          selector: '(checker threw)',
          message: `${route}: row ${row} checker threw: ${err.stack ?? err}`,
        });
      }
    };
    guard(2, () => {
      const sheets = [];
      for (const href of stylesheetHrefs(html)) {
        const path = href.split(/[?#]/)[0];
        const file = path.startsWith('/') ? join(dist, path) : resolve(dirname(f), path);
        if (!existsSync(file)) {
          const message = `${route}: linked stylesheet ${href} is not in dist`;
          r.rows[2].push({ row: 2, route, selector: href, message });
          continue;
        }
        if (!cssText.has(file)) cssText.set(file, read(file));
        sheets.push({ text: cssText.get(file), siteWide: linkCount.get(href) === pages.length });
      }
      r.stylesheets += sheets.length;
      const { problems, containers } = gridFlexMinWidthProblems(route, sheets, html);
      r.containers += containers;
      r.rows[2].push(...problems);
    });
    const { scripts: scriptFiles } = resolvePageScripts(WEB, route);
    const scripts = scriptFiles.filter((s) => existsSync(s)).map((s) => read(s));
    guard(3, () => {
      r.liveRegions += countLiveRegions(html);
      r.rows[3].push(...liveStructureProblems(route, html));
      for (const s of scripts) r.rows[3].push(...innerHtmlIntoLiveProblems(route, html, s));
    });
    guard(4, () => r.rows[4].push(...duplicateLiveProblems(route, html, scripts)));
    guard(5, () => r.rows[5].push(...titleOnlyProblems(route, html)));
    guard(7, () => {
      const x = rangeProblems(route, html, scripts);
      r.ranges += x.ranges;
      r.withCompanion += x.withCompanion;
      r.rows[7].push(...x.problems);
    });
  }
  r.all = Object.values(r.rows).flat();
  realCache.set(theme, r);
  return r;
}

const unexcused = (problems) => messages(applyExceptions(problems, A11Y_EXCEPTIONS));

for (const theme of THEMES) {
  test(`${theme}: row 2 -- no page-local grid/flex container risks reflow (built dist)`, () => {
    const r = realResults(theme);
    assert.ok(r.pages > 0, 'expected inner pages');
    assert.ok(r.stylesheets > 0, 'expected linked stylesheets on inner pages');
    assert.ok(r.containers > 0, 'expected page-local grid/flex containers to examine');
    assert.deepEqual(unexcused(r.rows[2]), []);
  });

  test(`${theme}: rows 3-4 -- aria-live shape (built dist + the page's own source script)`, () => {
    const r = realResults(theme);
    assert.ok(r.pages > 0, 'expected inner pages');
    assert.ok(r.liveRegions > 0, 'expected at least one live region across inner pages');
    assert.deepEqual(unexcused([...r.rows[3], ...r.rows[4]]), []);
  });

  test(`${theme}: row 5 -- no title-only information (built dist)`, () => {
    // No positive title= count is asserted: the audit's fixes removed the last real ones, so an
    // already-clean site must pass. Visiting real pages is the anti-vacuous-pass guarantee here.
    const r = realResults(theme);
    assert.ok(r.pages > 0, 'expected inner pages');
    assert.deepEqual(unexcused(r.rows[5]), []);
  });

  test(`${theme}: row 7 -- ranges with a value readout carry and sync aria-valuetext`, () => {
    const r = realResults(theme);
    assert.ok(r.ranges > 0, 'expected at least one <input type="range"> across inner pages');
    assert.ok(r.withCompanion > 0, 'expected at least one range with a companion value display');
    assert.deepEqual(unexcused(r.rows[7]), []);
  });
}
