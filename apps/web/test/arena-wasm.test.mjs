// EXC-150-1 condition 4 (ADR 0014), last link of the chain:
//   CI build from pinned source == committed apps/web/src/assets/arena/pkg/  (arena-wasm CI gate)
//   committed pkg/ == security/arena-pkg.sha256                             (repo-guard, every lint)
//   committed pkg/'s .wasm == the .wasm actually served in dist             (this test, every web build)
// so the SHA-256 recorded in the arena SBOM component is the SHA-256 of the file the site serves.
//
// Scheme (lead + nfb-security, 2026-09-27): pkg/'s .wasm is imported with `?url` by
// apps/web/src/assets/arena/loader.mjs, so Vite itself content-hashes it into dist's /_assets/
// under a name of Vite's choosing -- this test never assumes a filename pattern, it compares
// file *content*. /arena may ship WITHOUT wasm ("decoder unavailable"): then pkg/ (and the
// manifest) are absent, astro.config.mjs aliases to the zero-wasm stub, and dist has no .wasm at
// all -- covered below as the normal case, not a failure.
//
// Manifest format (nfb-build-queen, repo-guard's parseSha256Sums): plain `sha256sum` output,
// one line per file, `<64 lowercase hex><space><space-or-*><filename>`, LF-terminated, sorted by
// name; lists exactly the 4 plain wasm-bindgen output names with no directory component.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { basename, join } from 'node:path';
import { existsSync, readFileSync } from 'node:fs';
import { files, requireDist, REPO } from './_dist.mjs';

const PKG_DIR = join(REPO, 'apps/web/src/assets/arena/pkg');
const PKG_WASM = join(PKG_DIR, 'arena_core_bg.wasm');
const MANIFEST = join(REPO, 'security/arena-pkg.sha256');
const sha = (p) => createHash('sha256').update(readFileSync(p)).digest('hex');

const SHA256SUMS_LINE = /^([0-9a-f]{64}) [ *]([^/\\]+)$/;
function parseSha256Sums(text) {
  const map = new Map();
  for (const line of text.split('\n')) {
    if (!line.trim()) continue;
    const m = SHA256SUMS_LINE.exec(line);
    assert.ok(m, `security/arena-pkg.sha256: unparsable line: ${JSON.stringify(line)}`);
    map.set(m[2], m[1]);
  }
  return map;
}

const pkgPresent = existsSync(PKG_WASM);
const manifestPresent = existsSync(MANIFEST);

test('pkg/ and its manifest are both present or both absent (repo-guard also enforces this)', () => {
  assert.equal(
    pkgPresent,
    manifestPresent,
    `apps/web/src/assets/arena/pkg/ present=${pkgPresent}, security/arena-pkg.sha256 present=${manifestPresent} -- must match`,
  );
});

if (pkgPresent && manifestPresent) {
  test('manifest lists the exact 4 plain wasm-bindgen names, and pkg/ matches every hash', () => {
    const manifest = parseSha256Sums(readFileSync(MANIFEST, 'utf8'));
    const expected = [
      'arena_core.d.ts',
      'arena_core.js',
      'arena_core_bg.wasm',
      'arena_core_bg.wasm.d.ts',
    ];
    assert.deepEqual(
      [...manifest.keys()].sort(),
      expected,
      'manifest must list exactly these 4 names',
    );
    for (const name of expected) {
      assert.equal(
        sha(join(PKG_DIR, name)),
        manifest.get(name),
        `pkg/${name} does not match the manifest`,
      );
    }
  });
}

for (const theme of ['clinical', 'cosmos']) {
  test(`${theme}: no unhashed arena_core.js / arena_core_bg.wasm, and nothing under dist/arena/pkg`, () => {
    const dist = requireDist(theme);
    assert.ok(
      !existsSync(join(dist, 'arena', 'pkg')),
      'pkg/ must never be served as a static passthrough',
    );
    const suspects = [...files(dist, '.js'), ...files(dist, '.wasm')].filter((f) =>
      /^arena_core(_bg)?\.(js|wasm)$/.test(basename(f)),
    );
    assert.deepEqual(
      suspects.map((f) => f.slice(dist.length)),
      [],
      'dist must only ever serve Vite-hashed names for these files, never the plain wasm-bindgen output name',
    );
  });

  test(`${theme}: /arena ships at most one .wasm, and it is byte-identical to pkg/'s`, (t) => {
    const dist = requireDist(theme);
    // Whole dist, not just _assets/: build.assets is '_assets' today (astro.config.mjs), but
    // this test's job is to catch ANY .wasm the build produces, including one that ends up
    // somewhere else after a config change -- it shouldn't stop noticing just because the
    // output moved.
    const served = files(dist, '.wasm');
    t.diagnostic(`${theme}: ${served.length} .wasm in dist; pkg/ present: ${pkgPresent}`);

    if (!pkgPresent) {
      assert.deepEqual(
        served,
        [],
        'dist serves a .wasm although apps/web/src/assets/arena/pkg/ has none (decoder unavailable state)',
      );
      return;
    }
    // Only the arena decoder may ship as WebAssembly (the CSP exception is for /arena/ only).
    assert.equal(served.length, 1, `expected exactly one .wasm in dist/_assets, got: ${served}`);
    assert.equal(
      sha(served[0]),
      sha(PKG_WASM),
      'served .wasm differs from the committed pkg/ build',
    );
    if (manifestPresent) {
      const manifest = parseSha256Sums(readFileSync(MANIFEST, 'utf8'));
      assert.equal(
        sha(served[0]),
        manifest.get('arena_core_bg.wasm'),
        'served .wasm differs from the SBOM-recorded manifest hash',
      );
    }
  });
}
