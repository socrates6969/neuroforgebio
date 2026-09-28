// Helpers for the local dist tests (node --test). Run `pnpm --filter @nf/web build` first.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

export const WEB = resolve(dirname(fileURLToPath(import.meta.url)), '..');
export const REPO = resolve(WEB, '../..');
export const DIST = { clinical: join(WEB, 'dist/clinical'), cosmos: join(WEB, 'dist/cosmos') };
export const THEMES_DIR = join(REPO, 'packages/themes');

export function requireDist(theme) {
  const d = DIST[theme];
  if (!existsSync(join(d, 'index.html'))) {
    throw new Error(`${d} is missing: run "pnpm --filter @nf/web build" before the dist tests`);
  }
  return d;
}

export function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) yield* walk(p);
    else yield p;
  }
}

export const files = (dir, ext) => [...walk(dir)].filter((f) => f.endsWith(ext));
export const read = (f) => readFileSync(f, 'utf8');
/** URL path of a built HTML file: dist/x/platform/index.html -> /platform/ */
export function urlPath(distDir, file) {
  const rel = relative(distDir, file).split(sep).join('/');
  if (rel === 'index.html') return '/';
  if (rel.endsWith('/index.html')) return `/${rel.slice(0, -'index.html'.length)}`;
  return `/${rel}`;
}

/** Visible text of an HTML document (scripts, styles, svg text and tags removed, whitespace collapsed). */
export function visibleText(html) {
  return html
    .replace(/<script\b[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style\b[\s\S]*?<\/style>/gi, ' ')
    .replace(/<head\b[\s\S]*?<\/head>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Attribute values of tags, e.g. attrs(html, 'script', 'src'). */
export function attrs(html, tag, attr) {
  const out = [];
  const re = new RegExp(`<${tag}\\b[^>]*>`, 'gi');
  for (const m of html.matchAll(re)) {
    const a = m[0].match(new RegExp(`\\s${attr}\\s*=\\s*("([^"]*)"|'([^']*)'|([^\\s>]+))`, 'i'));
    if (a) out.push({ tag: m[0], value: a[2] ?? a[3] ?? a[4] });
  }
  return out;
}

export const brand = JSON.parse(read(join(REPO, 'packages/content/brand.json')));
export const canonicalOrigin = `https://${brand.domain}`;

/** Text of a built JS module plus everything it imports statically (the code that runs up front). */
export function moduleClosureText(distDir, urlPath) {
  const seen = new Set();
  const stack = [join(distDir, urlPath)];
  const out = [];
  while (stack.length) {
    const f = stack.pop();
    if (seen.has(f) || !existsSync(f)) continue;
    seen.add(f);
    const src = readFileSync(f, 'utf8');
    out.push(src);
    for (const m of src.matchAll(
      /(?:^|[;\s}])(?:import|export)\s*(?:[\w$*{},\s]+from\s*)?["']([^"']+\.js)["']/g,
    ))
      stack.push(m[1].startsWith('/') ? join(distDir, m[1]) : resolve(dirname(f), m[1]));
  }
  return out.join('\n');
}

/**
 * Form controls (<input>, <select>, <button>) in an HTML page that have no accessible name: none of
 * aria-label, aria-labelledby, an enclosing <label>, a <label for=id>, or (buttons) text content.
 * Returns the opening tags of the unnamed ones. Hidden inputs are ignored.
 */
export function unnamedControls(html) {
  const out = [];
  const labelFor = new Set([...html.matchAll(/<label\b[^>]*\sfor="([^"]+)"/g)].map((m) => m[1]));
  for (const m of html.matchAll(/<(input|select|button)\b[^>]*>/gi)) {
    const tag = m[0];
    if (/\stype="hidden"/i.test(tag)) continue;
    if (/\saria-label(ledby)?="[^"]+"/i.test(tag)) continue;
    const id = /\sid="([^"]+)"/.exec(tag)?.[1];
    if (id && labelFor.has(id)) continue;
    const before = html.slice(0, m.index);
    const open = before.lastIndexOf('<label');
    if (open >= 0 && before.lastIndexOf('</label>') < open) continue;
    if (m[1].toLowerCase() === 'button') {
      const end = html.indexOf('</button>', m.index);
      if (visibleText(html.slice(m.index, end))) continue;
    }
    out.push(tag);
  }
  return out;
}

/**
 * Inline <script> blocks (no src) that break the page rules: only `type="application/ld+json"` is
 * allowed inline, and its body must be valid JSON that cannot close or open a script element.
 * Returns a list of problems (empty = fine).
 */
export function inlineScriptProblems(html) {
  const problems = [];
  for (const m of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi)) {
    const [, attrsText, body] = m;
    if (/\ssrc\s*=/i.test(` ${attrsText}`)) continue;
    const type = /\stype\s*=\s*["']?([^"'\s>]+)/i.exec(` ${attrsText}`)?.[1];
    if (type !== 'application/ld+json') {
      problems.push(`inline script${type ? ` type=${type}` : ''}`);
      continue;
    }
    if (/\son[a-z]+\s*=/i.test(` ${attrsText}`)) problems.push('ld+json with an event handler');
    if (/<\/?script/i.test(body)) problems.push('ld+json containing a script tag');
    try {
      JSON.parse(body);
    } catch {
      problems.push('ld+json that is not valid JSON');
    }
  }
  return problems;
}
