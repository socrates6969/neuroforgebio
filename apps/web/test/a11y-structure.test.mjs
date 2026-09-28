// Regression tests for the manual checks in docs/web/a11y-checklist.md rows not already owned by
// swarm-web-engine's apps/web/test/a11y-checklist.test.mjs (rows 2, 3-4, 5, 7 - web-queen ruling,
// 2026-09-27): heading order and one h1 (part of row 1's spirit but not one of their rows), every
// form control has a label, and every <a> has non-empty accessible text. Assertion-only, no fixes
// here even when a page currently fails - see docs/web/a11y-t14.md for the exact list.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { files, read, requireDist, unnamedControls, urlPath, visibleText } from './_dist.mjs';

const THEMES = ['clinical', 'cosmos'];
// /gallery renders every @nf/ui component in isolation as a demo (its own <h1> plus each demo's
// own, e.g. Hero's <h1>) - apps/web/test/html.test.mjs already exempts it from "one <h1>" by name
// for the same reason; heading *order* within it is equally not a real document outline, so it's
// excluded from both checks here, not just the count.
const NOT_A_DOCUMENT = (url) => url.startsWith('/gallery');

function headingLevels(html) {
  const body = html.replace(/<head\b[\s\S]*?<\/head>/gi, ' ');
  return [...body.matchAll(/<h([1-6])\b/gi)].map((m) => Number(m[1]));
}

/** <a> elements with no accessible text: no visible text content, no aria-label/aria-labelledby,
 * and (for an image-only link) no alt on a contained <img>. aria-hidden links are skipped - they
 * are intentionally removed from the accessibility tree, not a labelling bug. */
function unnamedLinks(html) {
  const out = [];
  for (const m of html.matchAll(/<a\b[^>]*>/gi)) {
    const tag = m[0];
    if (/\saria-hidden="true"/i.test(tag)) continue;
    if (/\saria-label="[^\s"][^"]*"/i.test(tag)) continue;
    if (/\saria-labelledby="[^\s"][^"]*"/i.test(tag)) continue;
    const start = m.index + tag.length;
    const end = html.indexOf('</a>', start);
    if (end === -1) continue;
    const inner = html.slice(start, end);
    if (visibleText(inner)) continue;
    const imgAlt = /<img\b[^>]*\salt="([^"]*)"/i.exec(inner)?.[1];
    if (imgAlt && imgAlt.trim()) continue;
    out.push(tag);
  }
  return out;
}

for (const theme of THEMES) {
  test(`${theme}: exactly one h1 per page, no heading-level skips`, () => {
    const dist = requireDist(theme);
    const problems = [];
    for (const f of files(dist, '.html')) {
      const url = urlPath(dist, f);
      if (NOT_A_DOCUMENT(url)) continue;
      const levels = headingLevels(read(f));
      const h1s = levels.filter((l) => l === 1).length;
      if (h1s !== 1) problems.push(`${url}: ${h1s} <h1> (expected exactly 1)`);
      for (let i = 1; i < levels.length; i++)
        if (levels[i] > levels[i - 1] + 1)
          problems.push(`${url}: heading skip h${levels[i - 1]} -> h${levels[i]} (position ${i})`);
    }
    assert.deepEqual(problems, []);
  });

  test(`${theme}: every form control has an accessible label`, () => {
    const dist = requireDist(theme);
    const problems = [];
    for (const f of files(dist, '.html')) {
      const bad = unnamedControls(read(f));
      if (bad.length) problems.push(`${urlPath(dist, f)}: ${bad.join(', ')}`);
    }
    assert.deepEqual(problems, []);
  });

  test(`${theme}: every <a> has non-empty accessible text`, () => {
    const dist = requireDist(theme);
    const problems = [];
    for (const f of files(dist, '.html')) {
      const bad = unnamedLinks(read(f));
      if (bad.length) problems.push(`${urlPath(dist, f)}: ${bad.join(', ')}`);
    }
    assert.deepEqual(problems, []);
  });
}

// Row 2 (CSS Grid min-width:0 guards) is swarm-web-engine's, in
// apps/web/test/a11y-checklist.test.mjs - dropped here per web-queen's ruling to avoid duplicating
// it under a different name.
