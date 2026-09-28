// WCAG 2.x AA contrast for every text/background token pair in both themes (BUILD-GUIDE 1.1,
// BLUEPRINT §2.7). Translucent tokens (cosmos glass surfaces, status fills) are composited over
// the surface they sit on, which is itself composited over --color-bg.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { THEMES, colorsIn, contrast, over, parseColor, tokenMap } from './_tokens.mjs';

const TEXT = 4.5; // AA, normal-size text
const UI = 3; // AA, non-text UI (focus ring, accent marks) per WCAG 1.4.11

for (const theme of THEMES) {
  const t = tokenMap(theme);
  const col = (name) => parseColor(t.get(name));
  const bg = col('--color-bg');
  assert.equal(bg.a, 1, `${theme}: --color-bg must be opaque`);
  /** Opaque backdrops text can sit on: the page, a card surface, a tinted panel. */
  const backdrops = {
    bg,
    surface: over(col('--color-surface'), bg),
    'surface-2': over(col('--color-surface-2'), bg),
  };

  const pairs = [];
  const onAll = (fgName, fg, min) => {
    for (const [bn, b] of Object.entries(backdrops))
      pairs.push({ what: `${fgName} on ${bn}`, fg: over(fg, b), bg: b, min });
  };
  for (const n of ['--color-ink', '--color-muted', '--color-accent-ink']) onAll(n, col(n), TEXT);
  // emphasis paint may be a colour or a gradient: every stop must pass on its own
  colorsIn(t.get('--emphasis-paint')).forEach((c, i) =>
    onAll(`--emphasis-paint stop ${i}`, c, TEXT),
  );
  // primary button (accent) and its hover state (accent-ink)
  for (const b of ['--color-accent', '--color-accent-ink']) {
    const fill = over(col(b), bg);
    pairs.push({
      what: `--color-on-accent on ${b}`,
      fg: over(col('--color-on-accent'), fill),
      bg: fill,
      min: TEXT,
    });
  }
  // inverted blocks (code samples, skip link): bg-coloured text on ink
  const ink = over(col('--color-ink'), bg);
  pairs.push({ what: '--color-bg on --color-ink', fg: bg, bg: ink, min: TEXT });
  // status pills on every backdrop
  for (const s of ['designed', 'planned', 'roadmap'])
    for (const [bn, b] of Object.entries(backdrops)) {
      const fill = over(col(`--color-status-${s}-bg`), b);
      pairs.push({
        what: `status-${s}-ink on status-${s}-bg over ${bn}`,
        fg: over(col(`--color-status-${s}-ink`), fill),
        bg: fill,
        min: TEXT,
      });
    }
  // non-text: focus ring and accent marks against the page and cards
  for (const n of ['--color-focus', '--color-accent'])
    for (const bn of ['bg', 'surface'])
      pairs.push({
        what: `${n} (UI) on ${bn}`,
        fg: over(col(n), backdrops[bn]),
        bg: backdrops[bn],
        min: UI,
      });

  test(`${theme}: WCAG AA contrast for ${pairs.length} token pairs`, () => {
    const fails = pairs
      .map((p) => ({ ...p, ratio: contrast(p.fg, p.bg) }))
      .filter((p) => p.ratio < p.min)
      .map((p) => `${p.what}: ${p.ratio.toFixed(2)} < ${p.min}`);
    assert.deepEqual(fails, []);
  });
}

test('contrast maths matches known WCAG values', () => {
  const r = (a, b) => contrast(parseColor(a), parseColor(b));
  assert.equal(r('#000000', '#ffffff').toFixed(2), '21.00');
  assert.equal(r('#777777', '#ffffff').toFixed(2), '4.48');
  assert.equal(r('#ffffff', '#ffffff').toFixed(2), '1.00');
  const half = over(parseColor('rgba(255,255,255,.5)'), parseColor('#000000'));
  assert.equal(Math.round(half.r), 128);
});
