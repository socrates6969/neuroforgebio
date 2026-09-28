// SEC-150a post-build check: every inline <script> (no src), inline <style>, inline event handler
// (on*="...") and style="..." attribute in dist/**/*.html must be covered by a sha256 hash in the CSP,
// or the build fails. Handlers and style attributes need 'unsafe-hashes' (banned), so they always fail.
// Non-executable script types (application/ld+json, importmap is NOT exempt) are data, not code.
// Usage: node scripts/inline-check.mjs <distDir...>
import { createHash } from 'node:crypto';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { INLINE_SCRIPT_HASHES, INLINE_STYLE_HASHES } from '../security-headers.mjs';

function* walk(dir) {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) yield* walk(p);
    else if (n.endsWith('.html')) yield p;
  }
}

export const sha256 = (s) => `sha256-${createHash('sha256').update(s, 'utf8').digest('base64')}`;

const DATA_TYPES = /^(application\/(ld\+)?json|text\/plain)$/i;

/** Inline code in one HTML document: [{kind, hash?, snippet}]. */
export function scanHtml(html) {
  const found = [];
  const noComments = html.replace(/<!--[\s\S]*?-->/g, '');
  for (const m of noComments.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi)) {
    const attrs = m[1];
    if (/\ssrc\s*=/i.test(attrs)) {
      if (m[2].trim()) found.push({ kind: 'script-src-with-body', snippet: m[2].slice(0, 60) });
      continue;
    }
    const type = /\stype\s*=\s*["']?([^"'\s>]+)/i.exec(attrs)?.[1];
    if (type && DATA_TYPES.test(type)) continue;
    found.push({ kind: 'inline-script', hash: sha256(m[2]), snippet: m[2].trim().slice(0, 60) });
  }
  for (const m of noComments.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style\s*>/gi))
    found.push({ kind: 'inline-style', hash: sha256(m[1]), snippet: m[1].trim().slice(0, 60) });
  // attributes: look only inside tags, outside <script>/<style> bodies
  const tagsOnly = noComments
    .replace(/<script\b[^>]*>[\s\S]*?<\/script\s*>/gi, '<script>')
    .replace(/<style\b[^>]*>[\s\S]*?<\/style\s*>/gi, '<style>');
  for (const t of tagsOnly.matchAll(/<[a-zA-Z][^>]*>/g)) {
    const tag = t[0];
    for (const a of tag.matchAll(/\s(on[a-z]+)\s*=/gi))
      found.push({ kind: 'event-handler', snippet: `${a[1]} in ${tag.slice(0, 60)}` });
    if (/\sstyle\s*=/i.test(tag))
      found.push({ kind: 'style-attribute', snippet: tag.slice(0, 80) });
    if (/\shref\s*=\s*["']?\s*javascript:/i.test(tag))
      found.push({ kind: 'javascript-url', snippet: tag.slice(0, 80) });
  }
  return found;
}

/** Problems for a dist dir: inline code that the CSP does not allow. */
export function checkDist(
  dist,
  { scriptHashes = INLINE_SCRIPT_HASHES, styleHashes = INLINE_STYLE_HASHES } = {},
) {
  const problems = [];
  for (const f of walk(dist)) {
    for (const item of scanHtml(readFileSync(f, 'utf8'))) {
      if (item.kind === 'inline-script' && scriptHashes.includes(item.hash)) continue;
      if (item.kind === 'inline-style' && styleHashes.includes(item.hash)) continue;
      problems.push(
        `${relative(dist, f)}: ${item.kind}${item.hash ? ` (${item.hash})` : ''}: ${item.snippet}`,
      );
    }
  }
  return problems;
}

const isMain = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  let bad = 0;
  for (const d of process.argv.slice(2)) {
    const problems = checkDist(resolve(d));
    for (const p of problems) console.error(`${d}/${p}`);
    bad += problems.length;
  }
  if (bad) {
    console.error(
      `inline-check: ${bad} inline script/style/handler(s) not covered by the CSP (SEC-150a)`,
    );
    process.exit(1);
  }
  console.error('inline-check: no inline code outside the CSP');
}
