// Performance budgets for inner pages (docs/web/perf-baseline.md, docs/hive/PERF-AUDIT.md).
// Budgets live in tools/web/perf-budgets.json: each inner page's measured value +10% (floor +1 KB
// or +1), and "*" (the theme's largest inner page +10%) for pages added later. The homepage is not
// budgeted here: it is pinned by homepage.test.mjs and must not change (WEB-PLAN rule 1).
// After a deliberate, reviewed size change: node tools/web/perf-audit.mjs --write-budgets
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, extname, join } from 'node:path';
import { BUDGETS_FILE, METRICS, auditTheme, isHome } from '../../../tools/web/perf-audit.mjs';
import { files, read, requireDist } from './_dist.mjs';

const budgets = JSON.parse(readFileSync(BUDGETS_FILE, 'utf8'));
// Measured, named raises on top of the generated budgets (lead ruling: only by the measured bytes
// of the addition, reason documented; see the file's "rule").
const adjustments = JSON.parse(
  readFileSync(join(dirname(BUDGETS_FILE), 'perf-budget-adjustments.json'), 'utf8'),
);
// Hard rules rather than budgets. The stills in neuro-media/stills-manifest.json are 2560 px JPEGs
// of 100-324 KB, so the image a current browser fetches must be AVIF/WebP and at most 200 KB. A JPEG
// or PNG may ship only as the <img> fallback inside a <picture> whose <source> is AVIF/WebP (for
// browsers without AVIF); the audit counts the source, which is what current browsers fetch.
const IMAGE_MAX_BYTES = 200 * 1024;
const IMAGE_FORMATS = new Set(['avif', 'webp', 'svg', 'ico']);
// Known exceptions, each with its owner and the fix; remove the entry when the fix lands. Empty
// since nfb-playground fa11103: the /interface and /playground stills load only in <noscript> or by
// script (not page weight), and <Picture> serves AVIF first.
const IMAGE_FORMAT_EXCEPTIONS = {};

for (const theme of ['clinical', 'cosmos']) {
  test(`${theme}: every inner page is within its performance budget`, () => {
    requireDist(theme);
    const inner = auditTheme(theme).filter((p) => !isHome(p));
    assert.ok(inner.length >= 20, `expected the inner pages, found ${inner.length}`);
    const over = [];
    for (const p of inner) {
      const b = budgets[theme][p.path] ?? budgets[theme]['*'];
      const adj = adjustments[theme]?.[p.path] ?? {};
      for (const [k, fn] of Object.entries(METRICS)) {
        const limit = b[k] + (adj[k]?.add ?? 0);
        if (fn(p) > limit) over.push(`${p.path} ${k} ${fn(p)} > ${limit}`);
      }
      for (const f of p.images.formats)
        if (!IMAGE_FORMATS.has(f) && !IMAGE_FORMAT_EXCEPTIONS[p.path]?.has(f))
          over.push(`${p.path} ships a .${f} image (use AVIF or WebP)`);
      for (const fb of p.images.pictureFallbacks)
        if (!IMAGE_FORMATS.has(fb.format) && !fb.modernSource)
          over.push(
            `${p.path} <picture> falls back to .${fb.format} without an AVIF/WebP <source>`,
          );
      if (p.images.largest > IMAGE_MAX_BYTES)
        over.push(`${p.path} has an image of ${p.images.largest} bytes > ${IMAGE_MAX_BYTES}`);
      // <noscript> images reach only JS-off visitors (old browsers too, so JPEG is fine) but still
      // must not be heavy.
      if (p.images.noscript.largest > IMAGE_MAX_BYTES)
        over.push(`${p.path} has a <noscript> image of ${p.images.noscript.largest} bytes`);
    }
    assert.deepEqual(over, []);
  });

  test(`${theme}: fonts are self-hosted woff2 with font-display: swap`, () => {
    const dist = requireDist(theme);
    for (const css of files(dist, '.css')) {
      for (const face of read(css).match(/@font-face\s*{[^}]*}/g) ?? []) {
        assert.match(face, /font-display:\s*swap/, `${css}: @font-face without font-display: swap`);
        const first = face.match(/src:[^;]*?url\(\s*["']?([^"')]+)/);
        assert.ok(first && extname(first[1]) === '.woff2', `${css}: first font src is not woff2`);
        assert.ok(!/^(?:https?:)?\/\//.test(first[1]), `${css}: remote font ${first[1]}`);
        assert.ok(existsSync(join(dist, first[1])), `${css}: ${first[1]} missing`);
      }
    }
  });

  test(`${theme}: pages load no third-party resources`, () => {
    const dist = requireDist(theme);
    const remote = [];
    for (const f of files(dist, '.html')) {
      const html = readFileSync(f, 'utf8');
      for (const m of html.matchAll(
        /<(script|link|img|source|iframe|video|audio)\b[^>]*\s(?:src|href|poster)=["']((?:https?:)?\/\/[^"']+)["'][^>]*>/gi,
      )) {
        // canonical / alternate links name our own origin and are not fetched
        if (m[1] === 'link' && /rel=["']?(?:canonical|alternate)/i.test(m[0])) continue;
        remote.push(`${f.slice(dist.length)}: ${m[2]}`);
      }
    }
    assert.deepEqual(remote, []);
  });
}

test('budget adjustments are measured and documented', () => {
  for (const theme of ['clinical', 'cosmos'])
    for (const [page, metrics] of Object.entries(adjustments[theme] ?? {}))
      for (const [k, a] of Object.entries(metrics)) {
        assert.ok(k in METRICS, `${theme} ${page}: unknown metric ${k}`);
        assert.ok(
          Number.isInteger(a.add) && a.add > 0,
          `${theme} ${page} ${k}: add must be > 0 bytes`,
        );
        assert.ok(
          a.reason?.length > 10 && /^[0-9a-f]{7,40}$/.test(a.measuredAt ?? ''),
          `${theme} ${page} ${k}: needs a reason and the measured commit (measuredAt)`,
        );
      }
});
