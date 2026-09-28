// Zero-dependency helpers for the theme tests: read the contract and the token files.
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
export const THEMES = ['clinical', 'cosmos'];
export const read = (p) => readFileSync(join(ROOT, p), 'utf8');

/** String entries of `export const NAME = [ ... ] as const` in contract.ts. */
export function contractList(name) {
  const src = read('contract.ts');
  const m = src.match(new RegExp(`export const ${name} = \\[([\\s\\S]*?)\\] as const`));
  if (!m) throw new Error(`contract.ts: ${name} not found`);
  return [...m[1].matchAll(/'([^']+)'/g)].map((x) => x[1]);
}

export const stripComments = (css) => css.replace(/\/\*[\s\S]*?\*\//g, '');

/**
 * Top-level rule blocks of a CSS file: [{ selector, body, media }], where `media` is the enclosing
 * @media prelude or null. Only one level of @media nesting is supported (all the token files need).
 */
export function blocks(css) {
  const src = stripComments(css).replace(/@import[^;]*;/g, '');
  const out = [];
  let i = 0;
  const walk = (end, media) => {
    while (i < end) {
      const open = src.indexOf('{', i);
      if (open === -1 || open >= end) break;
      const prelude = src.slice(i, open).trim();
      let depth = 1;
      let j = open + 1;
      while (depth && j < src.length) {
        if (src[j] === '{') depth++;
        else if (src[j] === '}') depth--;
        j++;
      }
      const body = src.slice(open + 1, j - 1);
      if (prelude.startsWith('@media')) {
        const save = i;
        i = open + 1;
        walk(j - 1, prelude);
        i = save;
      } else out.push({ selector: prelude, body, media });
      i = j;
    }
  };
  walk(src.length, null);
  return out;
}

/** Custom property declarations in a block body, in order. */
export function decls(body) {
  return [...body.matchAll(/(--[\w-]+)\s*:\s*([^;]+);?/g)].map((m) => ({
    name: m[1],
    value: m[2].trim(),
  }));
}

/** Base (non-@media) token map of a theme, with var() references resolved. */
export function tokenMap(theme) {
  const map = new Map();
  for (const b of blocks(read(`${theme}/tokens.css`)))
    if (!b.media) for (const d of decls(b.body)) map.set(d.name, d.value);
  const resolveVal = (v, seen = new Set()) =>
    v.replace(/var\(\s*(--[\w-]+)\s*(?:,[^)]*)?\)/g, (_, n) => {
      if (seen.has(n)) throw new Error(`${theme}: var() cycle at ${n}`);
      if (!map.has(n)) throw new Error(`${theme}: var(${n}) is not defined`);
      return resolveVal(map.get(n), new Set([...seen, n]));
    });
  const out = new Map();
  for (const [k, v] of map) out.set(k, resolveVal(v));
  return out;
}

// ---------- colour maths (WCAG 2.x) ----------

/** Parse #rgb, #rrggbb, #rrggbbaa, rgb(), rgba() into { r, g, b, a } (0-255, alpha 0-1). */
export function parseColor(s) {
  s = s.trim().toLowerCase();
  let m = s.match(/^#([0-9a-f]{3,8})$/);
  if (m) {
    let h = m[1];
    if (h.length === 3 || h.length === 4) h = [...h].map((c) => c + c).join('');
    const n = (k) => parseInt(h.slice(k, k + 2), 16);
    return { r: n(0), g: n(2), b: n(4), a: h.length === 8 ? n(6) / 255 : 1 };
  }
  m = s.match(/^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?\s*\)$/);
  if (m) {
    let a = m[4] === undefined ? 1 : parseFloat(m[4]);
    if (m[4]?.endsWith('%')) a /= 100;
    return { r: +m[1], g: +m[2], b: +m[3], a };
  }
  throw new Error(`unsupported colour: ${s}`);
}

/** All colour literals inside a value (e.g. the stops of a gradient). */
export const colorsIn = (v) =>
  [...v.matchAll(/#[0-9a-f]{3,8}\b|rgba?\([^)]*\)/gi)].map((m) => parseColor(m[0]));

/** Source-over compositing of `top` onto an opaque `bottom`. */
export function over(top, bottom) {
  const a = top.a;
  return {
    r: top.r * a + bottom.r * (1 - a),
    g: top.g * a + bottom.g * (1 - a),
    b: top.b * a + bottom.b * (1 - a),
    a: 1,
  };
}

const lin = (c) => {
  c /= 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
};
export const luminance = ({ r, g, b }) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);

export function contrast(fg, bg) {
  const [x, y] = [luminance(fg), luminance(bg)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
}
