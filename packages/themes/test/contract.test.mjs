// Contract test (BUILD-GUIDE 1.1): every contract token is defined in both themes, no theme
// defines tokens outside the contract, tokens are scoped to [data-theme], fonts are self-hosted,
// slots respect the budget, and three.js stays out of clinical.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { ROOT, THEMES, blocks, contractList, decls, read, stripComments } from './_tokens.mjs';

const REQUIRED = contractList('REQUIRED_TOKENS');
const EXTENDED = contractList('EXTENDED_TOKENS');
const ALL = new Set([...REQUIRED, ...EXTENDED]);
const SLOTS = contractList('SLOT_NAMES');

test('contract lists the CONTRACTS.md §3.1 tokens', () => {
  for (const t of [
    '--color-bg',
    '--color-surface',
    '--color-ink',
    '--color-muted',
    '--color-accent',
    '--color-accent-ink',
    '--color-secondary',
    '--color-line',
    '--emphasis-paint',
    '--font-display',
    '--font-body',
    '--font-mono',
    '--radius-card',
    '--motion-duration',
    '--motion-ease',
    '--elevation-card',
  ])
    assert.ok(REQUIRED.includes(t), t);
  assert.equal(ALL.size, REQUIRED.length + EXTENDED.length, 'duplicate token in contract');
});

for (const theme of THEMES) {
  test(`${theme}: defines every contract token, and only contract tokens, under [data-theme]`, () => {
    const bs = blocks(read(`${theme}/tokens.css`));
    const selector = new RegExp(`^\\[data-theme=(['"])${theme}\\1\\]$`);
    const defined = new Set();
    for (const b of bs) {
      assert.match(b.selector, selector, `unscoped rule "${b.selector}"`);
      assert.doesNotMatch(
        b.body.replace(/(--[\w-]+)\s*:[^;]+;?/g, ''),
        /\S/,
        `${b.selector}: only custom properties allowed`,
      );
      for (const d of decls(b.body)) {
        assert.ok(ALL.has(d.name), `${d.name} is not in contract.ts`);
        if (!b.media) {
          assert.ok(!defined.has(d.name), `${d.name} defined twice`);
          defined.add(d.name);
        } else assert.ok(defined.has(d.name), `${d.name} overridden in @media before base`);
      }
    }
    const missing = [...ALL].filter((t) => !defined.has(t));
    assert.deepEqual(missing, []);
  });

  test(`${theme}: fonts come only from @fontsource packages (no remote CSS or url)`, () => {
    const css = stripComments(read(`${theme}/tokens.css`));
    const imports = [...css.matchAll(/@import\s+['"]([^'"]+)['"]/g)].map((m) => m[1]);
    assert.ok(imports.length > 0, 'expected self-hosted font imports');
    for (const i of imports) assert.match(i, /^@fontsource\/[\w-]+\/latin-\d{3}\.css$/, i);
    assert.doesNotMatch(css, /https?:|url\(/i);
    const pkg = JSON.parse(read('package.json'));
    for (const i of imports) {
      const name = i.split('/').slice(0, 2).join('/');
      assert.match(pkg.dependencies?.[name] ?? '', /^\d+\.\d+\.\d+$/, `${name} pinned exactly`);
    }
  });

  test(`${theme}: slot budget and names`, () => {
    const files = readdirSync(join(ROOT, theme, 'slots')).filter((f) => !f.startsWith('.'));
    assert.ok(files.length <= 4, `${files.length} slot files`);
    assert.deepEqual(files.map((f) => f.replace(/\.astro$/, '')).sort(), [...SLOTS].sort());
  });
}

test('the two themes load different font families (unused theme fonts never ship)', () => {
  const fam = (t) =>
    new Set([...read(`${t}/tokens.css`).matchAll(/@fontsource\/([\w-]+)\//g)].map((m) => m[1]));
  const c = fam('clinical');
  const k = fam('cosmos');
  assert.deepEqual(
    [...c].filter((f) => k.has(f)),
    [],
  );
});

function* walk(dir) {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) yield* walk(p);
    else yield p;
  }
}

test('clinical never imports three', () => {
  for (const f of walk(join(ROOT, 'clinical')))
    assert.doesNotMatch(read(f.slice(ROOT.length + 1)), /\bthree\b['"/]|from\s+['"]three/, f);
});

test('cosmos loads three only through a dynamic import() of the pinned npm package', () => {
  const pkg = JSON.parse(read('package.json'));
  assert.equal(pkg.dependencies.three, '0.160.0');
  for (const f of walk(join(ROOT, 'cosmos'))) {
    const s = read(f.slice(ROOT.length + 1));
    assert.doesNotMatch(s, /jsdelivr|unpkg|cdnjs|esm\.sh|skypack/i, f);
    assert.doesNotMatch(s, /^\s*import\s[^(]*['"]three['"]/m, `${f}: static three import`);
  }
  assert.match(read('cosmos/slots/HeroVisual.astro'), /import\(\s*['"]three['"]\s*\)/);
});

test('slots stay CSP-safe: no inline handlers, eval, Function or blob workers', () => {
  for (const theme of THEMES)
    for (const f of walk(join(ROOT, theme, 'slots'))) {
      const s = read(f.slice(ROOT.length + 1));
      assert.doesNotMatch(s, /\son[a-z]+=\s*["'{]/i, `${f}: inline event handler`);
      assert.doesNotMatch(s, /\beval\s*\(|new\s+Function\s*\(|new\s+Worker\s*\(|\bblob:/, f);
      assert.doesNotMatch(s, /<script\b[^>]*\bis:inline\b/, `${f}: is:inline script`);
      assert.doesNotMatch(s, /set:html/, `${f}: set:html`);
    }
});
