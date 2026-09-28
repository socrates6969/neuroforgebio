// Read-only verification script (nfb-site-rs, team-lead ruling 2026-09-27, corrected per web-headers'
// pointer to the CANONICAL layout): builds the canonical /arena/ fixture from
// apps/web/test/csp-static.test.mjs's hashedArena() (replicated here, read-only, since it isn't
// exported - bytes/paths copied verbatim from that file), then calls the REAL, unmodified
// `postbuild()` (apps/web/scripts/postbuild.mjs) on it for both hosts, so the outputs can be
// byte-diffed against the Rust port running on the same fixture.
//
// Not part of the Rust build or CI - a one-off input generator for tests/arena_fixture_parity.rs's
// NF_ARENA_FIXTURE_DIR. Committed here (web-queen, 2026-09-27) so anyone can reproduce the parity
// tests, not just the session that first wrote it.
//
// Usage: node tools/site-rs/scripts/arena-fixture-js.mjs <repo-root> <clinical-dist-dir> <out-dir>
// Then:  NF_ARENA_FIXTURE_DIR=<out-dir> cargo test -p site-rs -- --ignored
// Afterwards, delete the two kept-alive fixture dist dirs named in <out-dir>/*/dist-dir.txt.
import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const [, , repoRootArg, distArg, outArg] = process.argv;
if (!repoRootArg || !distArg || !outArg) {
  console.error(
    'usage: node tools/site-rs/scripts/arena-fixture-js.mjs <repo-root> <clinical-dist-dir> <out-dir>',
  );
  process.exit(2);
}
const repoRoot = resolve(repoRootArg);
const webDir = join(repoRoot, 'apps/web');

const { CSP_EXCEPTIONS } = await import(pathToFileURL(join(webDir, 'security-headers.mjs')));
const { postbuild, sitePaths } = await import(pathToFileURL(join(webDir, 'scripts/postbuild.mjs')));
const { exceptionsInUse } = await import(pathToFileURL(join(webDir, 'scripts/csp-check.mjs')));

const distSrc = resolve(distArg);
if (!existsSync(join(distSrc, 'index.html'))) {
  console.error(`${distSrc} is missing index.html - not a built dist`);
  process.exit(1);
}

/** apps/web/test/csp-static.test.mjs's hashedArena(), replicated verbatim (read-only import of the
 * bytes/paths it writes - the function itself isn't exported). */
function hashedArena(d, { from = 'arena' } = {}) {
  const wasm = '_assets/arena_core_bg.Ab12Cd34.wasm';
  writeFileSync(join(d, wasm), Buffer.from([0, 97, 115, 109, 1, 0, 0, 0]));
  writeFileSync(
    join(d, '_assets/arena_core.Ef56Gh78.js'),
    "export default async function __wbg_init(m){if(typeof m==='undefined'){m=new URL('arena_core_bg.Ab12Cd34.wasm',import.meta.url)}const {instance}=await WebAssembly.instantiateStreaming(fetch(m),{});return instance}",
  );
  writeFileSync(
    join(d, '_assets/arena.Ij90Kl12.js'),
    'const e=async()=>{const t=await import("./arena_core.Ef56Gh78.js");await t.default()};e();',
  );
  const tag = '<script type="module" src="/_assets/arena.Ij90Kl12.js"></script></body>';
  const base = readFileSync(join(d, 'security/index.html'), 'utf8');
  mkdirSync(join(d, 'arena'), { recursive: true });
  writeFileSync(
    join(d, 'arena/index.html'),
    from === 'arena' ? base.replace('</body>', tag) : base,
  );
  if (from !== 'arena') writeFileSync(join(d, 'security/index.html'), base.replace('</body>', tag));
  return wasm;
}

/** /arena/ built but with no wasm-reaching loader at all - must keep the baseline CSP. */
function stubArena(d) {
  mkdirSync(join(d, 'arena'), { recursive: true });
  writeFileSync(join(d, 'arena/index.html'), readFileSync(join(d, 'security/index.html'), 'utf8'));
}

function buildVariant(name, apply) {
  const d = mkdtempSync(join(tmpdir(), `nf-arena-${name}-`));
  cpSync(distSrc, d, { recursive: true });
  apply(d);
  const paths = sitePaths(d);
  const active = exceptionsInUse(d, {
    list: CSP_EXCEPTIONS,
    onError: (e) => console.error(`[${name}] exceptionsInUse error:`, e.message),
  });
  const variantOut = join(outArg, name);
  mkdirSync(variantOut, { recursive: true });
  writeFileSync(join(variantOut, 'paths.json'), JSON.stringify(paths, null, 2) + '\n');
  writeFileSync(join(variantOut, 'active.json'), JSON.stringify(active, null, 2) + '\n');
  // Kept alive (not deleted here) so a same-session Rust cross-check can run its own trigger against
  // the identical fixture files and compare to active.json (web-headers review item c). Delete
  // manually once that check has run - see dist-dir.txt.
  writeFileSync(join(variantOut, 'dist-dir.txt'), d + '\n');
  console.log(
    `[${name}] fixture dir: ${d}, paths: ${paths.length}, active: ${JSON.stringify(active.map((e) => e.route))}`,
  );

  for (const host of ['cloudflare', 'netlify']) {
    try {
      // postbuild() writes _headers/_headers.json into `d` itself; copy them out per host before
      // the next host's postbuild() overwrites them.
      const { active: postbuildActive } = postbuild('clinical', {
        dist: d,
        stage: 'preview',
        host,
      });
      writeFileSync(
        join(variantOut, `${host}._headers`),
        readFileSync(join(d, '_headers'), 'utf8'),
      );
      writeFileSync(
        join(variantOut, `${host}._headers.json`),
        readFileSync(join(d, '_headers.json'), 'utf8'),
      );
      console.log(
        `[${name}] ${host}: OK, active=${JSON.stringify(postbuildActive.map((e) => e.route))}`,
      );
    } catch (e) {
      writeFileSync(join(variantOut, `${host}.error.txt`), e.message + '\n');
      console.log(`[${name}] ${host}: ERROR - ${e.message}`);
    }
  }
}

mkdirSync(outArg, { recursive: true });
buildVariant('canonical-active', (d) => hashedArena(d));
buildVariant('stub-baseline', (d) => stubArena(d));
console.log('done:', outArg);
