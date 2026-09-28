// Token-only style lint: fails on raw colours (hex, rgb/hsl/hwb/lab/lch/oklab/oklch) and on
// font-family names in component code. Only semantic tokens (var(--…)) are allowed.
// Usage: node packages/ui/scripts/style-lint.mjs <dir...>   (exit 1 on findings)
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, extname } from 'node:path';
import { fileURLToPath } from 'node:url';

const EXTS = new Set(['.astro', '.css', '.ts', '.mjs', '.js']);
const COLOR_FN = /\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(/i;
const HEX = /(^|[\s:,(='"])#(?:[0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})(?![0-9a-z_-])/i;
const FONT_FAMILY = /font-family\s*:\s*([^;}\n]+)/gi;
const FONT_SHORTHAND = /(?:^|[\s;{])font\s*:\s*([^;}\n]+)/gi;
const cut = (v) => v.replace(/["`>].*$/, '');
const NAMED_COLOR_PROP =
  /(?:^|[\s;{])(?:color|background(?:-color)?|border(?:-[a-z]+)?-color|fill|stroke|outline-color)\s*:\s*(white|black|red|blue|green|gray|grey|navy|teal|purple|orange|yellow|pink|silver)\b/gi;
const SVG_ATTR_COLOR =
  /\b(?:fill|stroke|stop-color|color)\s*=\s*["'](#[0-9a-f]{3,8}|rgba?\(|hsla?\(|white|black)/gi;

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    if (name === 'node_modules' || name === 'dist' || name.startsWith('.')) continue;
    const p = join(dir, name);
    const s = statSync(p);
    if (s.isDirectory()) yield* walk(p);
    else if (EXTS.has(extname(name))) yield p;
  }
}

const okFontValue = (v) => {
  const t = v.trim();
  return (
    /^(inherit|initial|unset|revert)$/i.test(t) ||
    /^var\(--[\w-]+(?:\s*,\s*var\(--[\w-]+\))*\)$/.test(t)
  );
};

export function lintText(text) {
  const out = [];
  const lines = text.split(/\r?\n/);
  lines.forEach((line, i) => {
    const n = i + 1;
    // strip line comments in TS/JS and the URL fragments in href/id attributes
    const code = line.replace(/\bhref\s*=\s*["'][^"']*["']/g, '').replace(/\/\/.*$/, '');
    if (COLOR_FN.test(code)) out.push({ line: n, rule: 'raw-colour-function' });
    if (HEX.test(code)) out.push({ line: n, rule: 'raw-hex-colour' });
    for (const m of code.matchAll(FONT_FAMILY))
      if (!okFontValue(cut(m[1]))) out.push({ line: n, rule: 'font-family-name' });
    for (const m of code.matchAll(FONT_SHORTHAND))
      if (!/^[^'"]*var\(--font-[\w-]+\)\s*$|^\s*(inherit|initial|unset)\s*$/.test(cut(m[1])))
        out.push({ line: n, rule: 'font-shorthand-without-token' });
    for (const _ of code.matchAll(NAMED_COLOR_PROP)) out.push({ line: n, rule: 'named-colour' });
    for (const _ of code.matchAll(SVG_ATTR_COLOR))
      out.push({ line: n, rule: 'svg-attribute-colour' });
  });
  return out;
}

export function lintDirs(dirs) {
  const findings = [];
  for (const d of dirs)
    for (const f of walk(d))
      for (const r of lintText(readFileSync(f, 'utf8'))) findings.push({ file: f, ...r });
  return findings;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const findings = lintDirs(process.argv.slice(2));
  for (const f of findings) console.log(`${f.file}:${f.line}: ${f.rule}`);
  if (findings.length) process.exit(1);
  console.error('style-lint: clean');
}
