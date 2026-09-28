import { test } from 'node:test';
import assert from 'node:assert/strict';
import { checkDist } from '../scripts/linkcheck.mjs';
import { requireDist } from './_dist.mjs';

test('zero broken internal links in both builds', () => {
  for (const t of ['clinical', 'cosmos']) {
    const { checked, broken } = checkDist(requireDist(t));
    assert.ok(checked > 50, `${t}: only ${checked} links checked`);
    assert.deepEqual(broken, [], t);
  }
});

test('link checker detects a missing page and a missing fragment', async () => {
  const { mkdtempSync, writeFileSync, mkdirSync, rmSync } = await import('node:fs');
  const { tmpdir } = await import('node:os');
  const { join } = await import('node:path');
  const d = mkdtempSync(join(tmpdir(), 'nf-links-'));
  try {
    mkdirSync(join(d, 'a'));
    writeFileSync(
      join(d, 'index.html'),
      '<a href="/a/">ok</a><a href="/missing/">x</a><a href="/a/#nope">y</a><a href="#top">z</a><p id="top"></p>',
    );
    writeFileSync(join(d, 'a/index.html'), '<h1 id="t">a</h1>');
    const { broken } = checkDist(d);
    assert.equal(broken.length, 2, broken.join('\n'));
  } finally {
    rmSync(d, { recursive: true, force: true });
  }
});
