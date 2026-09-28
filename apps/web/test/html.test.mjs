// Cheap static HTML checks that catch common axe failures before CI: unique ids, ARIA
// references that resolve, one <h1> and one <main> per page, lang set, images labelled.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { relative } from 'node:path';
import { files, read, requireDist } from './_dist.mjs';

for (const theme of ['clinical', 'cosmos']) {
  test(`${theme}: ids unique, ARIA refs resolve, one h1/main, lang, labelled images`, () => {
    const dist = requireDist(theme);
    const problems = [];
    for (const f of files(dist, '.html')) {
      const html = read(f);
      const rel = relative(dist, f);
      const ids = [...html.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1]);
      const dup = [...new Set(ids.filter((x, i) => ids.indexOf(x) !== i))];
      if (dup.length) problems.push(`${rel}: duplicate ids ${dup.join(', ')}`);
      const refs = [
        ...html.matchAll(/\saria-(?:labelledby|describedby|controls)="([^"]+)"/g),
      ].flatMap((m) => m[1].split(/\s+/));
      const missing = [...new Set(refs.filter((r) => !ids.includes(r)))];
      if (missing.length) problems.push(`${rel}: dangling ARIA refs ${missing.join(', ')}`);
      // the component gallery shows the Hero (its own h1) under the gallery h1 on purpose
      if (!rel.startsWith('gallery') && (html.match(/<h1\b/g) ?? []).length !== 1)
        problems.push(`${rel}: expected exactly one <h1>`);
      if ((html.match(/<main\b/g) ?? []).length !== 1)
        problems.push(`${rel}: expected exactly one <main>`);
      // BCP 47: English at /, Norwegian bokmål ("nb") under /no/
      const lang = /^no[\\/]/.test(rel) ? 'nb' : 'en';
      if (!new RegExp(`<html[^>]*\\slang="${lang}"`).test(html))
        problems.push(`${rel}: <html lang="${lang}"> missing`);
      for (const m of html.matchAll(/<img\b[^>]*>/g))
        if (!/\salt=/.test(m[0])) problems.push(`${rel}: <img> without alt`);
      for (const m of html.matchAll(/<(?:p|div|span)\b[^>]*\saria-label=/g))
        if (!/\srole=/.test(m[0]))
          problems.push(
            `${rel}: aria-label on a generic element without role: ${m[0].slice(0, 80)}`,
          );
    }
    assert.deepEqual(problems, []);
  });
}
