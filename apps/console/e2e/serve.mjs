#!/usr/bin/env node
// Local/CI server for the built console: serves dist/ with the headers from dist/_headers, mounts the
// mock IdP under /mock-idp and proxies /v1/* to the platform API (so everything is one origin and the
// CSP stays 'self'). Loopback http only: HSTS and upgrade-insecure-requests are dropped here.
// Usage: node e2e/serve.mjs  (env: PORT=4173, NF_E2E_API=http://127.0.0.1:8710, NF_E2E_TENANT)
import { createReadStream, existsSync, readFileSync, statSync } from 'node:fs';
import { request as httpRequest, createServer } from 'node:http';
import { dirname, extname, join, normalize, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createMockIdp } from './mock-idp.mjs';

const CONSOLE = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const DIST = join(CONSOLE, 'dist');
const PORT = Number(process.env.PORT || 4173);
const ORIGIN = `http://127.0.0.1:${PORT}`;
const API = new URL(process.env.NF_E2E_API || 'http://127.0.0.1:8710');
const TENANT = process.env.NF_E2E_TENANT || '5e2e0000-0000-4000-8000-000000000001';

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.woff2': 'font/woff2',
  '.woff': 'font/woff',
  '.json': 'application/json',
  '.svg': 'image/svg+xml',
};

function headerRules() {
  const rules = [];
  let cur = null;
  for (const line of readFileSync(join(DIST, '_headers'), 'utf8').split(/\r?\n/)) {
    if (!line.trim() || line.startsWith('#')) continue;
    if (/^\S/.test(line)) rules.push((cur = { path: line.trim(), headers: {} }));
    else {
      const i = line.indexOf(':');
      cur.headers[line.slice(0, i).trim()] = line.slice(i + 1).trim();
    }
  }
  return rules;
}

const RULES = headerRules();

function headersFor(path) {
  const out = {};
  for (const r of RULES) {
    const hit = r.path.endsWith('*') ? path.startsWith(r.path.slice(0, -1)) : r.path === path;
    if (hit) Object.assign(out, r.headers);
  }
  delete out['Strict-Transport-Security'];
  if (out['Content-Security-Policy'])
    out['Content-Security-Policy'] = out['Content-Security-Policy'].replace(
      '; upgrade-insecure-requests',
      '',
    );
  return out;
}

const idp = createMockIdp({
  issuer: `${ORIGIN}/mock-idp`,
  redirectUris: [`${ORIGIN}/`],
  tenant: TENANT,
});

function proxy(req, res) {
  const up = httpRequest(
    {
      hostname: API.hostname,
      port: API.port,
      path: req.url,
      method: req.method,
      headers: { ...req.headers, host: API.host },
    },
    (r) => {
      res.writeHead(r.statusCode ?? 502, r.headers);
      r.pipe(res);
    },
  );
  up.on('error', () => {
    res.writeHead(502, { 'content-type': 'application/problem+json' });
    res.end(JSON.stringify({ title: 'Bad Gateway', status: 502 }));
  });
  req.pipe(up);
}

const server = createServer(async (req, res) => {
  const path = new URL(req.url, ORIGIN).pathname;
  if (path.startsWith('/v1/')) return proxy(req, res);
  if (path.startsWith('/mock-idp/')) {
    const handled = await idp.handle(req, res, path.slice('/mock-idp'.length));
    if (handled !== false) return;
    res.writeHead(404);
    return res.end();
  }
  let file = normalize(join(DIST, decodeURIComponent(path)));
  if (!file.startsWith(DIST)) {
    res.writeHead(400);
    return res.end();
  }
  if (!existsSync(file) || statSync(file).isDirectory()) file = join(DIST, 'index.html');
  const served = file === join(DIST, 'index.html') ? '/index.html' : path;
  res.writeHead(200, {
    ...headersFor(served),
    'content-type': TYPES[extname(file)] ?? 'application/octet-stream',
  });
  createReadStream(file).pipe(res);
});

server.listen(PORT, '127.0.0.1', () => console.log(`console e2e server on ${ORIGIN}`));
