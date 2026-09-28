#!/usr/bin/env node
// After `vite build`: emit dist/_headers (Netlify / Cloudflare Pages format) and dist/_headers.json from
// security-headers.mjs, then fail the build on any inline script/style/handler in dist/**/*.html
// (SEC-150a; the scanner is the website's scripts/inline-check.mjs, reused as is).
import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { scanHtml } from '../../web/scripts/inline-check.mjs';
import {
  connectOrigins,
  consoleConfig,
  globalHeaders,
  renderHeadersFile,
  resolveStage,
} from '../security-headers.mjs';

const DIST = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'dist');

function* html(dir) {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) yield* html(p);
    else if (n.endsWith('.html')) yield p;
  }
}

/** Inline code anywhere in the console build: the console CSP allows no hashes at all. */
export function inlineProblems(dist = DIST) {
  const out = [];
  for (const f of html(dist))
    for (const item of scanHtml(readFileSync(f, 'utf8')))
      out.push(`${relative(dist, f)}: ${item.kind}: ${item.snippet}`);
  return out;
}

const isMain = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  const stage = resolveStage();
  const config = consoleConfig();
  if (stage !== 'preview' && config.issuer.startsWith('/')) {
    console.error(
      `postbuild: NF_CONSOLE_STAGE=${stage} needs a real NF_CONSOLE_OIDC_ISSUER (not the dev IdP)`,
    );
    process.exit(1);
  }
  const connect = connectOrigins(config);
  writeFileSync(join(DIST, '_headers'), renderHeadersFile({ stage, connect }));
  writeFileSync(
    join(DIST, '_headers.json'),
    JSON.stringify({ stage, headers: globalHeaders({ stage, connect }) }, null, 2) + '\n',
  );
  const problems = inlineProblems();
  if (problems.length) {
    for (const p of problems) console.error(`console dist/${p}`);
    console.error(
      `postbuild: ${problems.length} inline script/style/handler(s); the console CSP allows none`,
    );
    process.exit(1);
  }
  console.error(`postbuild: _headers written (stage ${stage}); no inline code in dist`);
}
