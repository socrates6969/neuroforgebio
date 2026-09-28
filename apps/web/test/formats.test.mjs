// Regression: the hero formats line rendered "Designed forBIDS" (no space between the lead
// and the first format). Checks the text as a browser joins it: tags removed, no spaces added.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { join } from 'node:path';
import { read, requireDist, REPO } from './_dist.mjs';

const home = JSON.parse(read(join(REPO, 'packages/content/content/home.json')));
const { lead, items } = home.formats;

for (const theme of ['clinical', 'cosmos']) {
  test(`${theme}: hero formats line has a space after "${lead}"`, () => {
    const html = read(join(requireDist(theme), 'index.html'));
    const m = html.match(/<p class="formats"[^>]*>([\s\S]*?)<\/p>/);
    assert.ok(m, 'formats line not found on the home page');
    const text = m[1]
      .replace(/<span class="nf-visually-hidden"[^>]*>[\s\S]*?<\/span>/g, '')
      .replace(/<[^>]+>/g, '')
      .replace(/\s+/g, ' ')
      .trim();
    assert.ok(text.startsWith(`${lead} ${items[0]}`), `rendered as: ${text.slice(0, 60)}`);
  });
}
