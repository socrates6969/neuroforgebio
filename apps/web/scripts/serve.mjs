#!/usr/bin/env node
// Tiny zero-dependency static server for CI e2e/Lighthouse runs (never used for deployment).
// It applies the build's own dist/<theme>/_headers (either SITE_HOST layout, host-headers.mjs) the way
// Netlify / Cloudflare Pages would, so Playwright sees the real CSP, COOP/COEP/CORP and cache headers.
// One local deviation: served over plain http on loopback, `upgrade-insecure-requests` is dropped
// (it would upgrade same-origin subresources to https://127.0.0.1, which has no TLS listener).
// Pass --keep-upgrade to send it anyway.
// Usage: node scripts/serve.mjs <distDir> <port> [--keep-upgrade]
import { createServer } from 'node:http';
import { existsSync, readFileSync, statSync } from 'node:fs';
import { extname, join, normalize, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { hostHeadersForPath, parseHostHeaders } from '../host-headers.mjs';

export const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript',
  '.css': 'text/css',
  '.svg': 'image/svg+xml',
  '.xml': 'application/xml',
  '.txt': 'text/plain; charset=utf-8',
  '.json': 'application/json',
  '.woff2': 'font/woff2',
  '.wasm': 'application/wasm',
  '.woff': 'font/woff',
  '.png': 'image/png',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
};

/** Loads dist/_headers; throws if the build did not emit it (run scripts/postbuild.mjs). */
export function loadRules(root) {
  const f = join(root, '_headers');
  if (!existsSync(f)) throw new Error(`${f} missing: build with scripts/build.mjs first`);
  return parseHostHeaders(readFileSync(f, 'utf8'));
}

/** Response headers for a URL path, with the loopback-http deviation described above. */
export function responseHeaders(rules, urlPath, { keepUpgrade = false } = {}) {
  const h = hostHeadersForPath(rules, urlPath);
  if (!keepUpgrade && h['Content-Security-Policy'])
    h['Content-Security-Policy'] = h['Content-Security-Policy']
      .split(';')
      .map((d) => d.trim())
      .filter((d) => d && d !== 'upgrade-insecure-requests')
      .join('; ');
  return h;
}

export function createStaticServer(root, opts = {}) {
  const rules = loadRules(root);
  return createServer((req, res) => {
    const url = new URL(req.url ?? '/', 'http://localhost');
    const p = normalize(decodeURIComponent(url.pathname)).replace(/^([/\\])+/, '');
    let f = join(root, p);
    if (!f.startsWith(root)) {
      res.writeHead(403).end();
      return;
    }
    if (existsSync(f) && statSync(f).isDirectory()) f = join(f, 'index.html');
    else if (!existsSync(f) && existsSync(`${f}.html`)) f = `${f}.html`;
    const ok = existsSync(f) && statSync(f).isFile() && !/[\\/]_headers(\.json)?$/.test(f);
    const file = ok ? f : join(root, '404.html');
    res.writeHead(ok ? 200 : 404, {
      'Content-Type': TYPES[extname(file)] ?? 'application/octet-stream',
      ...responseHeaders(rules, ok ? url.pathname : '/404.html', opts),
    });
    res.end(readFileSync(file));
  });
}

const isMain = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  const args = process.argv.slice(2);
  const [dirArg, portArg] = args.filter((a) => !a.startsWith('--'));
  const root = resolve(dirArg ?? 'dist/clinical');
  const port = Number(portArg ?? 4321);
  createStaticServer(root, { keepUpgrade: args.includes('--keep-upgrade') }).listen(
    port,
    '127.0.0.1',
    () => console.log(`serving ${root} on http://127.0.0.1:${port} with its _headers`),
  );
}
