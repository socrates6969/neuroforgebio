// SEC-081/082/083: structural checks of the (never locally run) release workflow.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { lintWorkflow } from '../lib.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const yml = readFileSync(
  join(here, '..', '..', '..', '.github', 'workflows', 'release.yml'),
  'utf8',
);

/** Return the text of one job (from `  <name>:` to the next job at the same indent). */
function job(name) {
  const lines = yml.split(/\r?\n/);
  const start = lines.indexOf(`  ${name}:`);
  assert.ok(start >= 0, `job ${name} exists`);
  let end = start + 1;
  while (end < lines.length && !/^ {2}[\w-]+:\s*$/.test(lines[end]) && !/^\S/.test(lines[end]))
    end++;
  return lines.slice(start + 1, end).join('\n');
}

test('release workflow passes the workflow policy', () => {
  assert.deepEqual(lintWorkflow(yml), []);
});

test('SEC-081: keyless cosign signing of both bundles and a verify step with identity + issuer', () => {
  const sign = job('sign');
  assert.match(sign, /cosign sign-blob --yes --bundle/);
  assert.doesNotMatch(yml, /--key\b|COSIGN_PRIVATE_KEY|COSIGN_PASSWORD/, 'keyless only');
  const verify = job('verify');
  assert.match(verify, /cosign verify-blob --bundle/);
  assert.match(verify, /--certificate-identity "\$IDENTITY"/);
  assert.match(verify, /--certificate-oidc-issuer "\$ISSUER"/);
  assert.match(yml, /ISSUER: https:\/\/token\.actions\.githubusercontent\.com/);
  assert.match(verify, /tampered/);
  for (const t of ['clinical', 'cosmos'])
    assert.match(job('build'), new RegExp(`for t in clinical cosmos`), t);
});

test('SEC-082: SLSA provenance via attest-build-provenance, verified with gh attestation', () => {
  assert.match(job('sign'), /uses: actions\/attest-build-provenance@[0-9a-f]{40} # v/);
  assert.match(job('verify'), /gh attestation verify "\$f" --repo "\$REPO" --signer-workflow/);
});

test('SEC-083: one CycloneDX 1.6 SBOM per artefact with support properties', () => {
  const sbom = job('sbom');
  // APP-L5: cdxgen comes from the isolated CI-only package tools/sbom-cdxgen (own lockfile, no install
  // scripts, outside the workspace), never `npx -y` and never a root dependency
  assert.match(
    sbom,
    /pnpm install --dir tools\/sbom-cdxgen --ignore-workspace --frozen-lockfile --ignore-scripts/,
  );
  assert.match(sbom, /tools\/sbom-cdxgen\/node_modules\/\.bin\/cdxgen .*--spec-version 1\.6/);
  assert.match(sbom, /tools\/sbom-props\/cli\.mjs add/);
  assert.match(sbom, /for t in clinical cosmos/);
});

test('APP-L5: the SBOM scanner never shares a job with the bundles it could alter before signing', () => {
  const build = job('build');
  assert.doesNotMatch(build, /cdxgen/, 'no scanner in the packaging job');
  assert.match(build, /sha256sum \* > SHA256SUMS/, 'bundles hashed where they are packed');
  const sign = job('sign');
  assert.match(sign, /needs: \[build, sbom\]/);
  // nfb-security: the two artifacts land in separate directories, never the same one
  assert.match(sign, /name: release-unsigned\s+path: out\n/);
  assert.match(sign, /name: release-sbom\s+path: sbom-in\n/);
  // the bundles are checked against the BUILD artifact's SHA256SUMS, in its own directory only
  assert.match(sign, /\(cd out && sha256sum -c SHA256SUMS\)/);
  // only the two exact SBOM names are accepted from release-sbom; anything else fails
  assert.match(
    sign,
    /"nfb-site-clinical-\$VERSION\.cdx\.json" "nfb-site-cosmos-\$VERSION\.cdx\.json"/,
  );
  assert.match(sign, /if \[ "\$got" != "\$expected" \]; then/);
  assert.match(sign, /\[ ! -e "out\/\$f" \]/, 'an SBOM never overwrites a build file');
  const check = sign.indexOf('sha256sum -c SHA256SUMS');
  const allow = sign.indexOf('"$got" != "$expected"');
  const copy = sign.indexOf('cp "sbom-in/$f" "out/$f"');
  const signBlob = sign.indexOf('cosign sign-blob');
  assert.ok(
    check >= 0 && check < allow && allow < copy && copy < signBlob,
    'check, allowlist, copy, sign',
  );
});

test('id-token: write only in the sign job; build and sbom jobs have read-only contents', () => {
  assert.equal((yml.match(/id-token: write/g) || []).length, 1);
  assert.match(job('sign'), /id-token: write/);
  assert.doesNotMatch(job('build'), /write/);
  assert.doesNotMatch(job('sbom'), /write|secrets\./);
});
