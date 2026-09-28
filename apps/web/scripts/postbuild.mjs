#!/usr/bin/env node
// Post-build for one theme (run by scripts/build.mjs after `astro build`):
//   1. /.well-known/security.txt (SEC-157); a launch/public build (any stage but preview) fails on placeholders;
//   2. SEC-150a inline check: inline script/style/handler/style attribute not in the CSP -> fail;
//   3. security headers (SEC-150..156) as dist/<theme>/_headers + dist/<theme>/_headers.json;
//   4. CSP self-check (csp-check.mjs checkCsp): anything in the build blocked by its own _headers (incl.
//      WebAssembly-compiling code on a route without the SEC-150 exception, and the arena layout guard)
//      -> fail. ON by default for every caller; only tests that deliberately build a dist the gate must
//      reject turn it off (cspCheck set to false; a test guards that only apps/web/test/ does).
//   5. launch gate (host-gate.mjs): a launch/public build fails while any built text file still names a
//      placeholder `.invalid` host; previews keep it.
// Usage: node scripts/postbuild.mjs <clinical|cosmos> [--dist <dir>]   (default dist: apps/web/dist/<theme>)
import { mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  assertCloudflareLimits,
  hostRules,
  renderHostHeaders,
  resolveHost,
} from '../host-headers.mjs';
import { assertCspSafe, csp, resolveStage } from '../security-headers.mjs';
import { checkCsp, exceptionsInUse } from './csp-check.mjs';
import { assertNoPlaceholderHost } from './host-gate.mjs';
import { checkDist } from './inline-check.mjs';
import { assertPublicReady, buildDate, securityTxt } from './security-txt.mjs';

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const brand = JSON.parse(readFileSync(join(WEB, '../../packages/content/brand.json'), 'utf8'));

function* walk(dir) {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) yield* walk(p);
    else yield p;
  }
}

/** URL paths of every emitted file outside /_assets/ (pages as "/x/"), excluding the header files. */
export function sitePaths(dist) {
  const out = [];
  for (const f of walk(dist)) {
    const rel = relative(dist, f).split(sep).join('/');
    if (rel.startsWith('_assets/') || rel === '_headers' || rel === '_headers.json') continue;
    if (rel === 'index.html') out.push('/');
    else if (rel.endsWith('/index.html')) out.push(`/${rel.slice(0, -'index.html'.length)}`);
    else out.push(`/${rel}`);
  }
  return out.sort();
}

export function postbuild(
  theme,
  {
    dist = join(WEB, 'dist', theme),
    stage = resolveStage(),
    host = resolveHost(),
    detect = exceptionsInUse,
    cspCheck = true,
    site = brand,
  } = {},
) {
  // Turning the step-4 CSP check off is refused outside `node --test` (which sets NODE_TEST_CONTEXT),
  // however the false value is passed; checked before anything is written.
  if (cspCheck !== true) {
    if (cspCheck !== false) throw new TypeError('postbuild: cspCheck must be a boolean');
    if (!process.env.NODE_TEST_CONTEXT)
      throw new Error('postbuild: the CSP check can only be turned off under node --test');
  }

  // 1. security.txt
  const txt = securityTxt({ brand: site, theme, date: buildDate() });
  assertPublicReady(txt, { stage, brand: site });
  mkdirSync(join(dist, '.well-known'), { recursive: true });
  writeFileSync(join(dist, '.well-known/security.txt'), txt);

  // 2. SEC-150a
  const problems = checkDist(dist);
  if (problems.length)
    throw new Error(
      `SEC-150a: inline code not covered by the CSP in dist/${theme}:\n  ${problems.join('\n  ')}`,
    );

  // 3. headers
  assertCspSafe(csp());
  // SITE_HOST picks the path layout (host-headers.mjs); header values are the same for every host.
  // SEC-150 route exceptions (csp-exceptions.json) switch on only when the route is built AND reaches a
  // .wasm (csp-check.mjs exceptionsInUse); a detection error keeps the strict baseline. Netlify fails
  // while one is active.
  const paths = sitePaths(dist);
  const active = detect(dist, {
    onError: (err) =>
      console.error(
        `[postbuild] SEC-150 exception detection failed, baseline CSP kept: ${err.message}`,
      ),
  });
  for (const e of active) assertCspSafe(csp({ route: e.route }), { route: e.route });
  const rules = hostRules(host, { stage, paths, active });
  const text = renderHostHeaders(host, rules, { stage });
  if (host === 'cloudflare') assertCloudflareLimits(text);
  writeFileSync(join(dist, '_headers'), text);
  writeFileSync(
    join(dist, '_headers.json'),
    JSON.stringify(
      {
        generatedBy: 'apps/web/security-headers.mjs',
        stage,
        host,
        // SEC-150 exceptions in use (csp-check.mjs exceptionsInUse); CI keys the netlify expected-fail on this
        activeExceptions: active.map((e) => e.route),
        note: 'Rules in order; a host must merge all matching rules (path "/*" matches everything, "/_assets/*" every hashed asset).',
        rules,
      },
      null,
      2,
    ) + '\n',
  );

  // 4. CSP self-check against the headers just written (default on; opt-out validated at the top)
  if (cspCheck) {
    const blocked = checkCsp(dist);
    const where =
      resolve(dist) === join(WEB, 'dist', theme) ? '' : `\n  (checked ${resolve(dist)})`;
    if (blocked.length)
      throw new Error(
        `CSP check: dist/${theme} contains resources its own policy blocks:\n  ${blocked.join('\n  ')}${where}`,
      );
  }

  // 5. launch gate: no placeholder (.invalid) host in any built text file of a launch/public build
  assertNoPlaceholderHost(dist, { stage });
  return { rules, txt, active };
}

const isMain = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  const [theme, ...rest] = process.argv.slice(2);
  const di = rest.indexOf('--dist');
  const dist = di >= 0 ? rest[di + 1] : undefined;
  if (
    !['clinical', 'cosmos'].includes(theme) ||
    (di >= 0 && !dist) ||
    rest.length !== (di >= 0 ? 2 : 0)
  ) {
    console.error('usage: node scripts/postbuild.mjs <clinical|cosmos> [--dist <dir>]');
    process.exit(2);
  }
  try {
    const { rules } = postbuild(theme, dist ? { dist: resolve(dist) } : {});
    console.error(
      `[postbuild] dist/${theme}: security.txt, inline check clean, _headers (${rules.length} rules, SITE_STAGE=${resolveStage()}, SITE_HOST=${resolveHost()})`,
    );
  } catch (e) {
    console.error(`[postbuild] FAILED: ${e.message}`);
    process.exit(1);
  }
}
