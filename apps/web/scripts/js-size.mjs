#!/usr/bin/env node
// Measures gzip size of the JavaScript each page loads up front: <script src>, modulepreload and
// their static-import closure. Dynamic import() chunks (e.g. three.js, loaded after the hero is
// visible) are reported separately and are NOT part of the initial budget (BLUEPRINT §2.3).
// Usage: node scripts/js-size.mjs [--json] [--budget=60]   (reads apps/web/dist/{clinical,cosmos})
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';

const web = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const json = process.argv.includes('--json');
const budgetKb = Number(
  (process.argv.find((a) => a.startsWith('--budget=')) ?? '--budget=60').split('=')[1],
);

function* walk(dir) {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) yield* walk(p);
    else yield p;
  }
}
const gz = (f) => gzipSync(readFileSync(f), { level: 9 }).length;

function closure(dist, html) {
  const entries = [];
  for (const m of html.matchAll(/<script\b[^>]*\ssrc=["']([^"']+)["']/gi)) entries.push(m[1]);
  for (const m of html.matchAll(/<link\b[^>]*rel=["']?modulepreload[^>]*href=["']([^"']+)["']/gi))
    entries.push(m[1]);
  const inline = [...html.matchAll(/<script\b(?![^>]*\ssrc=)[^>]*>([\s\S]*?)<\/script>/gi)]
    .map((m) => m[1])
    .filter((s) => s.trim());
  const seen = new Set();
  const dyn = new Set();
  const stack = entries.filter((u) => u.startsWith('/')).map((u) => join(dist, u));
  // imports from inline module scripts count too
  for (const s of inline)
    for (const m of s.matchAll(/(?:import|from)\s*["']([^"']+\.js)["']/g))
      if (m[1].startsWith('/')) stack.push(join(dist, m[1]));
  while (stack.length) {
    const f = stack.pop();
    if (seen.has(f) || !existsSync(f)) continue;
    seen.add(f);
    const src = readFileSync(f, 'utf8');
    for (const m of src.matchAll(
      /(?:^|[;\s}])(?:import|export)\s*(?:[\w$*{},\s]+from\s*)?["']([^"']+\.js)["']/g,
    ))
      stack.push(m[1].startsWith('/') ? join(dist, m[1]) : resolve(dirname(f), m[1]));
    for (const m of src.matchAll(/import\(\s*["']([^"']+\.js)["']\s*\)/g))
      dyn.add(m[1].startsWith('/') ? join(dist, m[1]) : resolve(dirname(f), m[1]));
  }
  const inlineBytes = inline.reduce((n, s) => n + gzipSync(Buffer.from(s), { level: 9 }).length, 0);
  return {
    files: [...seen],
    lazy: [...dyn].filter((f) => !seen.has(f) && existsSync(f)),
    inlineBytes,
  };
}

const report = {};
for (const theme of ['clinical', 'cosmos']) {
  const dist = join(web, 'dist', theme);
  if (!existsSync(join(dist, 'index.html'))) {
    console.error(`js-size: ${dist} missing (build first)`);
    process.exit(2);
  }
  const pages = {};
  for (const f of walk(dist)) {
    if (!f.endsWith('.html')) continue;
    const c = closure(dist, readFileSync(f, 'utf8'));
    const initial = c.files.reduce((n, x) => n + gz(x), 0) + c.inlineBytes;
    const lazy = c.lazy.reduce((n, x) => n + gz(x), 0);
    pages['/' + relative(dist, f).split(sep).join('/')] = {
      initialGzipBytes: initial,
      lazyGzipBytes: lazy,
      files: c.files.map((x) => relative(dist, x).split(sep).join('/')),
    };
  }
  const home = pages['/index.html'];
  const max = Object.entries(pages).sort(
    (a, b) => b[1].initialGzipBytes - a[1].initialGzipBytes,
  )[0];
  report[theme] = {
    home: home.initialGzipBytes,
    homeLazy: home.lazyGzipBytes,
    maxPage: max[0],
    maxInitial: max[1].initialGzipBytes,
    pages,
  };
}

let over = false;
for (const [t, r] of Object.entries(report)) {
  const kb = (b) => (b / 1024).toFixed(2);
  if (r.home > budgetKb * 1024) over = true;
  if (!json)
    console.log(
      `${t}: home initial JS ${kb(r.home)} KB gzip (budget ${budgetKb} KB), lazy after hero ${kb(r.homeLazy)} KB; largest page ${r.maxPage} ${kb(r.maxInitial)} KB`,
    );
}
if (json) console.log(JSON.stringify(report, null, 2));
process.exit(over ? 1 : 0);
