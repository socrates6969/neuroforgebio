#!/usr/bin/env node
// Offline page-weight audit of the built site (docs/hive/PERF-AUDIT.md). Per built HTML page:
// HTML, render-blocking CSS, initial JS (script src + modulepreload + static-import closure, as in
// js-size.mjs), lazy JS (dynamic import()), fonts the linked CSS can fetch, images, and the
// render-blocking resources in <head>. Font bytes are an upper bound: a browser fetches only the
// faces the page actually uses. Sizes are gzip -9 (what a host serves) unless named "raw".
// Data files the page's JS fetches (hashed /_assets/*.json|bin|wasm named in the initial or lazy JS)
// are counted separately. requests = HTML + stylesheets + initial JS + fonts + images.
// Usage: node tools/web/perf-audit.mjs [--json] [--pages] [--jsonld] [--write-budgets [--only=/p/,/q/]]
//        [--dist-root=<dir containing clinical/ and cosmos/>]
//        (reads apps/web/dist/{clinical,cosmos}; --write-budgets rewrites tools/web/perf-budgets.json)
import { existsSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname, extname, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';

const HERE = dirname(fileURLToPath(import.meta.url));
const WEB = resolve(HERE, '../../apps/web');
export const BUDGETS_FILE = join(HERE, 'perf-budgets.json');
export const THEMES = ['clinical', 'cosmos'];
// --dist-root=<dir> audits another checkout's build (e.g. a read-only worktree of a feature branch)
const distRoot = process.argv.find((a) => a.startsWith('--dist-root='))?.slice(12);
export const distOf = (theme) => join(distRoot ? resolve(distRoot) : join(WEB, 'dist'), theme);

function* walk(dir) {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) yield* walk(p);
    else yield p;
  }
}

const sizeCache = new Map();
function sizes(f) {
  if (!sizeCache.has(f)) {
    const b = readFileSync(f);
    sizeCache.set(f, { raw: b.length, gzip: gzipSync(b, { level: 9 }).length });
  }
  return sizeCache.get(f);
}
const sum = (fs, k) => fs.reduce((n, f) => n + sizes(f)[k], 0);
const local = (dist, from, u) => {
  const p = u.split(/[?#]/)[0];
  return p.startsWith('/') ? join(dist, p) : resolve(dirname(from), p);
};
const isLocal = (u) => !/^(?:[a-z]+:)?\/\//i.test(u) && !u.startsWith('data:');

const IMAGE_EXT = new Set(['.png', '.jpg', '.jpeg', '.gif', '.webp', '.avif', '.svg', '.ico']);
const FONT_EXT = new Set(['.woff2', '.woff', '.ttf', '.otf']);

function jsClosure(dist, page, html) {
  const entries = [];
  for (const m of html.matchAll(/<script\b[^>]*\ssrc=["']([^"']+)["']/gi)) entries.push(m[1]);
  for (const m of html.matchAll(/<link\b[^>]*rel=["']?modulepreload[^>]*href=["']([^"']+)["']/gi))
    entries.push(m[1]);
  const seen = new Set();
  const dyn = new Set();
  const stack = entries.filter(isLocal).map((u) => local(dist, page, u));
  while (stack.length) {
    const f = stack.pop();
    if (seen.has(f) || !existsSync(f)) continue;
    seen.add(f);
    const src = readFileSync(f, 'utf8');
    for (const m of src.matchAll(
      /(?:^|[;\s}])(?:import|export)\s*(?:[\w$*{},\s]+from\s*)?["']([^"']+\.js)["']/g,
    ))
      stack.push(local(dist, f, m[1]));
    for (const m of src.matchAll(/import\(\s*["']([^"']+\.js)["']\s*\)/g))
      dyn.add(local(dist, f, m[1]));
  }
  // lazy closure: everything reachable from the dynamic imports that is not already initial
  const lazy = new Set();
  const lstack = [...dyn];
  while (lstack.length) {
    const f = lstack.pop();
    if (seen.has(f) || lazy.has(f) || !existsSync(f)) continue;
    lazy.add(f);
    const src = readFileSync(f, 'utf8');
    for (const m of src.matchAll(/(?:from\s*|import\s*\(?\s*)["']([^"']+\.js)["']/g))
      lstack.push(local(dist, f, m[1]));
  }
  // data files named by the JS (import x from './d.json?url' becomes "/_assets/d.<hash>.json")
  const data = new Set();
  for (const f of [...seen, ...lazy])
    for (const m of readFileSync(f, 'utf8').matchAll(
      /["'`](\/_assets\/[^"'`]+\.(?:json|bin|wasm|csv|arrow))["'`]/g,
    ))
      if (existsSync(join(dist, m[1]))) data.add(join(dist, m[1]));
  return { initial: [...seen], lazy: [...lazy], data: [...data] };
}

/** CSS files a stylesheet pulls in (@import) and the url() assets it references. */
function cssDeps(dist, cssFile, out = { css: new Set(), urls: new Set() }) {
  if (out.css.has(cssFile) || !existsSync(cssFile)) return out;
  out.css.add(cssFile);
  let src = readFileSync(cssFile, 'utf8');
  for (const m of src.matchAll(/@import\s+(?:url\()?["']?([^"')\s;]+)/g))
    if (isLocal(m[1])) cssDeps(dist, local(dist, cssFile, m[1]), out);
  // @font-face: a browser fetches the first src it supports (woff2 everywhere current), not the
  // woff fallback after it, so only the first url() of each src counts.
  src = src.replace(/@font-face\s*{[^}]*}/g, (face) => {
    const first = face.match(/src:[^;]*?url\(\s*["']?([^"')]+)["']?\s*\)/);
    if (first && isLocal(first[1])) out.urls.add(local(dist, cssFile, first[1]));
    return '';
  });
  for (const m of src.matchAll(/url\(\s*["']?([^"')]+)["']?\s*\)/g))
    if (isLocal(m[1]) && !m[1].endsWith('.css')) out.urls.add(local(dist, cssFile, m[1]));
  return out;
}

export function auditPage(dist, file) {
  const html = readFileSync(file, 'utf8');
  const head = (html.match(/<head\b[\s\S]*?<\/head>/i) ?? [''])[0];
  const rel = relative(dist, file).split(sep).join('/');
  const path = rel === 'index.html' ? '/' : '/' + rel.replace(/index\.html$/, '');

  const sheets = [...html.matchAll(/<link\b[^>]*>/gi)]
    .map((m) => m[0])
    .filter((t) => /rel=["']?stylesheet/i.test(t))
    .map((t) => (t.match(/href=["']([^"']+)["']/i) ?? [])[1])
    .filter((u) => u && isLocal(u));
  const deps = { css: new Set(), urls: new Set() };
  for (const s of sheets) cssDeps(dist, local(dist, file, s), deps);
  const css = [...deps.css];
  const fonts = [...deps.urls].filter((f) => FONT_EXT.has(extname(f)) && existsSync(f));
  const cssImages = [...deps.urls].filter((f) => IMAGE_EXT.has(extname(f)) && existsSync(f));

  const imgUrls = new Set();
  const srcsetOf = (t) =>
    (t.match(/\ssrcset=["']([^"']+)["']/i)?.[1] ?? '')
      .split(',')
      .map((c) => c.trim().split(/\s+/))
      .filter(([u]) => u)
      .map(([u, d = '1x']) => ({ u, n: parseFloat(d) || 1 }));
  const srcOf = (t) => t.match(/\s(?:src|href|xlink:href)=["']([^"']+)["']/i)?.[1];
  // Every URL a tag names (for format checks) ...
  const allUrls = (t) => [srcOf(t), ...srcsetOf(t).map((c) => c.u)].filter(Boolean);
  // ... and the one it fetches: a browser picks ONE srcset candidate; count the largest (worst case:
  // wide viewport / high DPR). Astro's <Picture widths> emits several candidates per <source>.
  const tagUrls = (t) => {
    const set = srcsetOf(t).sort((a, b) => b.n - a.n);
    const u = set.length ? set[0].u : srcOf(t);
    return u ? [u] : [];
  };
  const resolveAll = (us) =>
    us
      .filter(isLocal)
      .map((u) => local(dist, file, u))
      .filter((f) => existsSync(f));
  // <picture>: a current browser fetches its first <source> (AVIF/WebP), not the <img> fallback, so
  // only that counts; the fallback is recorded with whether a modern source precedes it.
  const pictureFallbacks = [];
  // <noscript> content is not parsed (so its images are not fetched) while scripting is on; those
  // images serve only JS-off visitors and are reported apart from the page's weight.
  const noscriptUrls = [];
  const scripted = html.replace(/<noscript\b[\s\S]*?<\/noscript>/gi, (ns) => {
    for (const m of ns.matchAll(/<(?:img|source)\b[^>]*>/gi)) noscriptUrls.push(...tagUrls(m[0]));
    return '';
  });
  const noscript = [...new Set(resolveAll(noscriptUrls))];
  const rest = scripted.replace(/<picture\b[\s\S]*?<\/picture>/gi, (pic) => {
    const sources = [...pic.matchAll(/<source\b[^>]*>/gi)].map((m) => m[0]);
    const modern = sources.some((s) => /type=["']image\/(?:avif|webp)["']/i.test(s));
    const chosen = sources.length
      ? tagUrls(sources[0])
      : tagUrls((pic.match(/<img\b[^>]*>/i) ?? [''])[0]);
    for (const u of chosen) imgUrls.add(u);
    if (sources.length)
      for (const f of resolveAll(allUrls((pic.match(/<img\b[^>]*>/i) ?? [''])[0])))
        pictureFallbacks.push({ format: extname(f).slice(1).toLowerCase(), modernSource: modern });
    return '';
  });
  for (const m of rest.matchAll(/<(?:img|source|image)\b[^>]*>/gi))
    for (const u of tagUrls(m[0])) imgUrls.add(u);
  const images = resolveAll([...imgUrls]);
  const imgs = [...new Set([...images, ...cssImages])];

  const js = jsClosure(dist, file, html);
  const blockingScripts = [...head.matchAll(/<script\b[^>]*>/gi)]
    .map((m) => m[0])
    .filter((t) => /\ssrc=/i.test(t) && !/\s(?:async|defer)\b|type=["']?module/i.test(t));
  const fontDisplay = [
    ...new Set(
      css.flatMap((f) =>
        [...readFileSync(f, 'utf8').matchAll(/font-display:\s*(\w+)/g)].map((m) => m[1]),
      ),
    ),
  ];
  const inlineSvgBytes = [...html.matchAll(/<svg\b[\s\S]*?<\/svg>/gi)].reduce(
    (n, m) => n + m[0].length,
    0,
  );

  const r = {
    path,
    html: { raw: Buffer.byteLength(html), gzip: gzipSync(html, { level: 9 }).length },
    inlineSvgRaw: inlineSvgBytes,
    css: { files: css.length, raw: sum(css, 'raw'), gzip: sum(css, 'gzip') },
    jsInitial: {
      files: js.initial.length,
      raw: sum(js.initial, 'raw'),
      gzip: sum(js.initial, 'gzip'),
    },
    jsLazy: { files: js.lazy.length, gzip: sum(js.lazy, 'gzip') },
    data: { files: js.data.length, gzip: sum(js.data, 'gzip') },
    fonts: {
      files: fonts.length,
      bytes: sum(fonts, 'raw'),
      formats: [...new Set(fonts.map((f) => extname(f).slice(1)))],
    },
    fontDisplay,
    fontPreloads: [...head.matchAll(/<link\b[^>]*rel=["']?preload[^>]*as=["']?font/gi)].length,
    images: {
      files: imgs.length,
      bytes: sum(imgs, 'raw'),
      formats: [...new Set(imgs.map((f) => extname(f).slice(1).toLowerCase()))],
      largest: imgs.length ? Math.max(...imgs.map((f) => sizes(f).raw)) : 0,
      pictureFallbacks,
      noscript: {
        files: noscript.length,
        formats: [...new Set(noscript.map((f) => extname(f).slice(1).toLowerCase()))],
        largest: noscript.length ? Math.max(...noscript.map((f) => sizes(f).raw)) : 0,
      },
    },
    renderBlocking: { stylesheets: sheets.length, scripts: blockingScripts.length },
  };
  // transfer weight of what the page loads up front (fonts: upper bound, already compressed)
  r.totalGzip = r.html.gzip + r.css.gzip + r.jsInitial.gzip + r.fonts.bytes + r.images.bytes;
  r.requests = 1 + r.css.files + r.jsInitial.files + r.fonts.files + r.images.files;
  return r;
}

/**
 * What a page's JSON-LD blocks cost: raw bytes of the <script type="application/ld+json"> elements,
 * and how much gzip -9 of the page grows because of them. Used to size a budget adjustment to
 * exactly the structured data (tools/web/perf-budget-adjustments.json), not a blanket raise.
 */
export function jsonLdCost(html) {
  const blocks =
    html.match(/<script\b[^>]*type=["']application\/ld\+json["'][^>]*>[\s\S]*?<\/script>/gi) ?? [];
  const without = blocks.reduce((h, b) => h.replace(b, ''), html);
  return {
    blocks: blocks.length,
    raw: Buffer.byteLength(html) - Buffer.byteLength(without),
    gzip: gzipSync(html, { level: 9 }).length - gzipSync(without, { level: 9 }).length,
  };
}

export function auditTheme(theme) {
  const dist = distOf(theme);
  if (!existsSync(join(dist, 'index.html'))) throw new Error(`${dist} missing: build first`);
  return [...walk(dist)]
    .filter((f) => f.endsWith('.html'))
    .map((f) => auditPage(dist, f))
    .sort((a, b) => a.path.localeCompare(b.path));
}

/** Pages that render the homepage; excluded from the inner-page budgets (WEB-PLAN rule 1). */
export const isHome = (p) => p.path === '/';

const METRICS = {
  totalGzip: (p) => p.totalGzip,
  htmlGzip: (p) => p.html.gzip,
  htmlRaw: (p) => p.html.raw,
  cssGzip: (p) => p.css.gzip,
  jsInitialGzip: (p) => p.jsInitial.gzip,
  jsLazyGzip: (p) => p.jsLazy.gzip,
  dataGzip: (p) => p.data.gzip,
  fontBytes: (p) => p.fonts.bytes,
  imageBytes: (p) => p.images.bytes,
  largestImage: (p) => p.images.largest,
  requests: (p) => p.requests,
  renderBlockingStylesheets: (p) => p.renderBlocking.stylesheets,
  renderBlockingScripts: (p) => p.renderBlocking.scripts,
};
export { METRICS };

/**
 * Budget = today's value + 10%, rounded up, with a floor of +1 KB (byte metrics) or +1 (counts) so
 * a tiny page is not failed by a one-line edit. renderBlockingScripts is a rule (0), not a budget.
 * "*" is the budget for a page not yet in the file: the theme's largest inner page + 10%.
 */
export function budgetsFrom(pages) {
  const b = {};
  const one = (k, v) => {
    const isBytes = /Gzip|Bytes|Raw|Image/.test(k);
    return k === 'renderBlockingScripts'
      ? 0
      : Math.max(Math.ceil(v * 1.1), v + (isBytes ? 1024 : 1));
  };
  const top = {};
  for (const p of pages) {
    b[p.path] = {};
    for (const [k, fn] of Object.entries(METRICS)) {
      b[p.path][k] = one(k, fn(p));
      top[k] = Math.max(top[k] ?? 0, fn(p));
    }
  }
  b['*'] = Object.fromEntries(Object.entries(top).map(([k, v]) => [k, one(k, v)]));
  return b;
}

export function summarise(pages) {
  const out = {};
  for (const [k, fn] of Object.entries(METRICS)) {
    const vals = pages.map((p) => [fn(p), p.path]).sort((a, b) => b[0] - a[0]);
    const med = vals.map((v) => v[0]).sort((a, b) => a - b)[Math.floor(vals.length / 2)];
    out[k] = { max: vals[0][0], maxPage: vals[0][1], median: med };
  }
  return out;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const json = process.argv.includes('--json');
  const showPages = process.argv.includes('--pages');
  const measureJsonLd = process.argv.includes('--jsonld');
  const writeBudgets = process.argv.includes('--write-budgets');
  const report = {};
  for (const t of THEMES) {
    const pages = auditTheme(t);
    const inner = pages.filter((p) => !isHome(p));
    report[t] = {
      pageCount: pages.length,
      home: pages.find(isHome),
      inner: summarise(inner),
      pages,
    };
  }
  if (writeBudgets) {
    const out = {
      generated: new Date().toISOString().slice(0, 10),
      rule: 'inner pages; value +10% (floor +1 KB / +1); "*" = new pages',
    };
    // --only=/a/,/b/ rewrites just those pages' budgets and keeps the rest of the file (used when a
    // page's change lives on another branch and is measured with --dist-root)
    const only = process.argv
      .find((a) => a.startsWith('--only='))
      ?.slice(7)
      .split(',');
    const prev = only ? JSON.parse(readFileSync(BUDGETS_FILE, 'utf8')) : null;
    for (const t of THEMES) {
      const fresh = budgetsFrom(report[t].pages.filter((p) => !isHome(p)));
      if (!only) out[t] = fresh;
      else {
        out[t] = { ...prev[t] };
        for (const pg of only) {
          if (!fresh[pg]) throw new Error(`${t}: no built page ${pg}`);
          out[t][pg] = fresh[pg];
        }
      }
    }
    if (only) out.rule = prev.rule;
    writeFileSync(BUDGETS_FILE, JSON.stringify(out, null, 2) + '\n');
    console.error(`wrote ${BUDGETS_FILE}`);
  }
  if (measureJsonLd)
    for (const t of THEMES)
      for (const f of walk(distOf(t)))
        if (f.endsWith('.html')) {
          const c = jsonLdCost(readFileSync(f, 'utf8'));
          if (c.blocks)
            console.log(
              `jsonld ${t} ${auditPage(distOf(t), f).path}: ${c.blocks} block(s), raw ${c.raw} B, gzip +${c.gzip} B`,
            );
        }
  if (json) console.log(JSON.stringify(report, null, 2));
  else {
    const kb = (b) => (b / 1024).toFixed(1);
    for (const [t, r] of Object.entries(report)) {
      console.log(`\n== ${t}: ${r.pageCount} pages; inner-page max (median) ==`);
      for (const [k, v] of Object.entries(r.inner))
        console.log(
          `  ${k.padEnd(26)} ${/Bytes|Gzip|Raw|Image/.test(k) ? kb(v.max) + ' KB' : v.max}`.padEnd(
            44,
          ) +
            ` (median ${/Bytes|Gzip|Raw|Image/.test(k) ? kb(v.median) + ' KB' : v.median})  ${v.maxPage}`,
        );
      const h = r.home;
      console.log(
        `  home: total ${kb(h.totalGzip)} KB, fonts ${h.fonts.files} (${h.fonts.formats}), font-display ${h.fontDisplay}, images ${h.images.files} ${h.images.formats}`,
      );
      if (showPages)
        for (const p of r.pages)
          console.log(
            `  ${p.path.padEnd(48)} total ${kb(p.totalGzip).padStart(6)} html ${kb(p.html.gzip).padStart(5)} css ${kb(p.css.gzip).padStart(5)} js ${kb(p.jsInitial.gzip).padStart(5)}+${kb(p.jsLazy.gzip)} data ${kb(p.data.gzip)} font ${kb(p.fonts.bytes)}(${p.fonts.files}) img ${kb(p.images.bytes)}(${p.images.files}) svg-inline ${kb(p.inlineSvgRaw)} block ${p.renderBlocking.stylesheets}/${p.renderBlocking.scripts} req ${p.requests}`,
          );
    }
  }
}
