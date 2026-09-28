import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { lintText, lintDirs } from '../scripts/style-lint.mjs';

const root = (p) => fileURLToPath(new URL(p, import.meta.url));

test('lint catches raw colours and font names', () => {
  const bad = [
    '.a{color:#0B2540}',
    '.a{background:rgba(0,0,0,.5)}',
    '.a{color: hsl(10 20% 30%)}',
    ".a{font-family:'IBM Plex Sans',sans-serif}",
    '.a{font:500 12px Inter}',
    '.a{color:white}',
    '<path fill="#fff" />',
    '.a{border-color:oklch(50% .1 200)}',
  ];
  for (const s of bad) assert.ok(lintText(s).length > 0, `expected finding for ${s}`);
});

test('lint accepts token-only styles and fragment links', () => {
  const good = [
    '.a{color:var(--color-ink);background:var(--color-surface)}',
    '.a{font-family:var(--font-body)}',
    '.a{font:500 12px/1.4 var(--font-mono)}',
    '<a href="#main">skip</a>',
    '.a{fill:currentColor}',
    '.a{background:color-mix(in srgb, var(--color-accent) 10%, transparent)}',
  ];
  for (const s of good) assert.deepEqual(lintText(s), [], `unexpected finding for ${s}`);
});

test('packages/ui and packages/figures use semantic tokens only', () => {
  const findings = lintDirs([root('../src'), root('../../figures/src')]);
  assert.deepEqual(findings, []);
});
