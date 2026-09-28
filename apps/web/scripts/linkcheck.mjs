#!/usr/bin/env node
// Zero-dependency internal link checker over built dist folders.
// Checks <a href>, <link href>, <script src>, <img src> and #fragments for internal targets.
// Usage: node scripts/linkcheck.mjs <distDir...>   (exit 1 on any broken link)
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, resolve, sep, posix } from 'node:path';
import { fileURLToPath } from 'node:url';

function* walk(dir) {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) yield* walk(p);
    else yield p;
  }
}

const idCache = new Map();
function idsOf(file) {
  if (!idCache.has(file)) {
    const html = readFileSync(file, 'utf8');
    idCache.set(file, new Set([...html.matchAll(/\sid=["']([^"']+)["']/g)].map((m) => m[1])));
  }
  return idCache.get(file);
}

function targetFile(dist, urlPath) {
  const clean = decodeURIComponent(urlPath.replace(/^\//, ''));
  const base = join(dist, clean);
  const candidates = urlPath.endsWith('/')
    ? [join(base, 'index.html')]
    : [base, join(base, 'index.html'), `${base}.html`];
  return candidates.find((c) => existsSync(c) && statSync(c).isFile()) ?? null;
}

export function checkDist(dist) {
  const broken = [];
  let checked = 0;
  for (const file of walk(dist)) {
    if (!file.endsWith('.html')) continue;
    const html = readFileSync(file, 'utf8');
    const pageUrl =
      '/' +
      relative(dist, file)
        .split(sep)
        .join('/')
        .replace(/index\.html$/, '');
    const refs = [
      ...html.matchAll(/<(a|link|script|img|source|iframe)\b[^>]*?\s(href|src)=["']([^"']*)["']/gi),
    ].map((m) => ({ tag: m[1].toLowerCase(), url: m[3] }));
    for (const { tag, url } of refs) {
      if (!url || /^(mailto:|tel:|data:|javascript:)/i.test(url)) continue;
      if (/^(https?:)?\/\//i.test(url)) continue; // external: not checked (no network)
      checked++;
      const [pathPart, frag] = url.split('#');
      const resolved =
        pathPart === ''
          ? pageUrl
          : pathPart.startsWith('/')
            ? pathPart
            : posix.resolve(posix.dirname(pageUrl + 'x'), pathPart);
      const target = pathPart === '' ? file : targetFile(dist, resolved);
      if (!target) {
        broken.push(`${relative(dist, file)}: <${tag}> ${url} -> missing`);
        continue;
      }
      if (frag && target.endsWith('.html') && !idsOf(target).has(decodeURIComponent(frag))) {
        broken.push(`${relative(dist, file)}: <${tag}> ${url} -> no id "${frag}"`);
      }
    }
  }
  return { checked, broken };
}

const isMain = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
const dirs = isMain ? process.argv.slice(2) : [];
if (isMain) {
  let bad = 0;
  for (const d of dirs) {
    const dist = resolve(d);
    if (!existsSync(dist)) {
      console.error(`linkcheck: ${d} does not exist (build first)`);
      process.exit(2);
    }
    const { checked, broken } = checkDist(dist);
    for (const b of broken) console.log(`${d}/${b}`);
    console.error(`linkcheck: ${d}: ${checked} internal links, ${broken.length} broken`);
    bad += broken.length;
  }
  process.exit(bad ? 1 : 0);
}
