#!/usr/bin/env node
// Homepage snapshot (owner directive 2026-09-27: no homepage edits). The built / must keep main's CSS
// and markup even when inner-page styles move Vite's shared CSS chunk boundaries (/ links chunks
// named api/gallery/security/_page_ that other pages also feed). The snapshot per theme is:
//   css:  every stylesheet index.html links, concatenated in <link> order (with its @imports inlined
//         where they appear), so a changed boundary alone is not a change but any changed rule or
//         cascade order is;
//   html: index.html with the stylesheet <link>s replaced by one marker (covered by css).
// Both are normalised: /_assets/<name>.<8-char hash>.<ext> -> /_assets/<name>.<ext>, and each
// data-astro-cid-<hash> -> cid<N> numbered by first appearance across css+html, so component
// scoping must still pair up exactly.
// Usage: node scripts/home-baseline.mjs --owner-approved [clinical|cosmos ...]
//   Rewrites test/fixtures/home-{css,html}.<theme>.txt. Run ONLY after the owner approves a homepage
//   change, and commit the fixture diff with that approval. Without the flag it only reports.
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), '..');
export const THEMES = ['clinical', 'cosmos'];
export const FIXTURES = join(WEB, 'test', 'fixtures');
export const fixturePath = (kind, theme) => join(FIXTURES, `home-${kind}.${theme}.txt`);

// Brand strings become {brand.*} tokens: the name may appear only in brand.json (content
// brand-token test), and a brand change flows from there by design. Longest first, so a host is
// replaced before the name inside it.
const brand = JSON.parse(readFileSync(join(WEB, '../../packages/content/brand.json'), 'utf8'));
const esc = (x) => x.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const BRAND = [
  ['secondaryHost', brand.secondaryHost],
  ['domain', brand.domain],
  ['legalName', brand.legalName],
  ['name', brand.name],
  ['codeIdentifiers.pythonImport', brand.codeIdentifiers.pythonImport],
  ['name.firstWord', brand.name.split(' ')[0]],
]
  .filter(([, v]) => v)
  .sort((a, b) => b[1].length - a[1].length);
const unbrand = (x) =>
  BRAND.reduce((t, [k, v]) => t.replace(new RegExp(esc(v), 'gi'), `{brand.${k}}`), x);

const HASHED = /(\/_assets\/[^"'()\s,]+?)\.[A-Za-z0-9_-]{8}\.([a-z0-9]+)\b/g;
const LINK_SHEET = /<link\b[^>]*\brel=["']?stylesheet\b[^>]*>/gi;

function cssWithImports(dist, file, seen = new Set()) {
  if (seen.has(file)) return '';
  seen.add(file);
  return readFileSync(file, 'utf8').replace(
    /@import\s+(?:url\()?["']?(\/[^"')\s;]+)["']?\)?[^;]*;/g,
    (m, u) => (existsSync(join(dist, u)) ? cssWithImports(dist, join(dist, u), seen) : m),
  );
}

export function homeSnapshot(dist) {
  const index = join(dist, 'index.html');
  if (!existsSync(index)) throw new Error(`${index} missing: build first`);
  const html = readFileSync(index, 'utf8');
  const sheets = [...html.matchAll(LINK_SHEET)].map(
    (m) => (m[0].match(/\bhref=["']([^"']+)["']/i) ?? [])[1],
  );
  const css = sheets
    .map((href) => {
      const f = join(dist, href.split(/[?#]/)[0]);
      if (!existsSync(f)) throw new Error(`index.html links ${href}, which is missing`);
      return cssWithImports(dist, f);
    })
    .join('\n');
  let first = true;
  const page = html.replace(LINK_SHEET, () => {
    const marker = first ? '<!-- stylesheets: see home-css -->' : '';
    first = false;
    return marker;
  });
  const cids = new Map();
  const norm = (s) =>
    unbrand(s)
      .replace(HASHED, '$1.$2')
      .replace(/data-astro-cid-([a-z0-9]+)/g, (_, h) => {
        if (!cids.has(h)) cids.set(h, cids.size);
        return `data-astro-cid-cid${cids.get(h)}`;
      });
  // css first so cid numbering follows the cascade; one line per rule block keeps diffs readable
  const cssOut = norm(css).replace(/}(?!\s*\n)/g, '}\n');
  const htmlOut = norm(page).replace(/>(?=<)/g, '>\n');
  return {
    css: cssOut.endsWith('\n') ? cssOut : cssOut + '\n',
    html: htmlOut.endsWith('\n') ? htmlOut : htmlOut + '\n',
  };
}

/**
 * Ids that depend on build order, not on the home page: Button.astro numbers its disabled-CTA note
 * from a build-wide counter (btn-note-<N>), so any page rendered before / shifts N. Renumbered by
 * first appearance, like the cids, so the pairing (aria-describedby -> id) still has to match.
 * Applied to both sides at compare time: existing baselines stay valid without regeneration.
 */
export function normaliseBuildIds(s) {
  const seen = new Map();
  return s.replace(/\bbtn-note-(\d+)\b/g, (_, n) => {
    if (!seen.has(n)) seen.set(n, seen.size);
    return `btn-note-#${seen.get(n)}`;
  });
}

/** aria-describedby targets on a page with no element of that id (raw built HTML). */
export function danglingDescribedBy(html) {
  const ids = new Set([...html.matchAll(/\sid=["']([^"']+)["']/g)].map((m) => m[1]));
  return [...html.matchAll(/\saria-describedby=["']([^"']+)["']/g)]
    .flatMap((m) => m[1].split(/\s+/))
    .filter((id) => id && !ids.has(id));
}

/** First differing line (1-based) with a little context, or null when equal. */
export function firstDiff(expected, actual) {
  expected = normaliseBuildIds(expected);
  actual = normaliseBuildIds(actual);
  if (expected === actual) return null;
  const a = expected.split('\n');
  const b = actual.split('\n');
  let i = 0;
  while (i < a.length && i < b.length && a[i] === b[i]) i++;
  const cut = (s) =>
    s === undefined ? '(end of file)' : s.length > 200 ? s.slice(0, 200) + '...' : s;
  return `line ${i + 1}:\n  baseline: ${cut(a[i])}\n  built:    ${cut(b[i])}`;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2);
  const write = args.includes('--owner-approved');
  const themes = args.filter((a) => !a.startsWith('--'));
  let changed = 0;
  for (const t of themes.length ? themes : THEMES) {
    if (!THEMES.includes(t)) throw new Error(`unknown theme ${t}`);
    const snap = homeSnapshot(join(WEB, 'dist', t));
    for (const kind of ['css', 'html']) {
      const p = fixturePath(kind, t);
      const d = existsSync(p) ? firstDiff(readFileSync(p, 'utf8'), snap[kind]) : 'no baseline yet';
      if (!d) {
        console.log(`${t} ${kind}: matches baseline`);
        continue;
      }
      changed++;
      if (write) {
        mkdirSync(FIXTURES, { recursive: true });
        writeFileSync(p, snap[kind]);
        console.log(`${t} ${kind}: baseline rewritten (${d.split('\n')[0]})`);
      } else console.log(`${t} ${kind}: DIFFERS from baseline, ${d}`);
    }
  }
  if (changed && !write)
    console.log(
      '\nNot rewritten. Only after the owner approves a homepage change: --owner-approved',
    );
  process.exit(changed && !write ? 1 : 0);
}
