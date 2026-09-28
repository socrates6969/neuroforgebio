import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { copyFileSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { addProps, checkBom, components, includeComponents } from '../lib.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const cli = join(here, '..', 'cli.mjs');
const fx = (n) => join(here, 'fixtures', n);
const load = (p) => JSON.parse(readFileSync(p, 'utf8'));
const run = (...a) => spawnSync(process.execPath, [cli, ...a], { encoding: 'utf8' });
const prop = (c, n) => (c.properties || []).find((p) => p.name === n)?.value;

test('raw SBOM without properties fails check', () => {
  const r = run('check', fx('sbom-1.6.cdx.json'));
  assert.equal(r.status, 1);
  assert.match(r.stdout, /missing nfb:supportLevel/);
  assert.match(r.stdout, /missing nfb:endOfSupport/);
});

test('add fills every component (nested included) with unknown, keeps existing values', () => {
  const bom = load(fx('sbom-1.6.cdx.json'));
  assert.equal(addProps(bom), 4);
  assert.deepEqual(checkBom(bom), []);
  const all = [...components(bom)].map(({ c }) => c);
  assert.equal(all.length, 4);
  const astro = all.find((c) => c.name === 'astro');
  assert.equal(prop(astro, 'nfb:supportLevel'), 'maintained');
  assert.equal(prop(astro, 'nfb:endOfSupport'), 'unknown');
  assert.equal(
    prop(
      all.find((c) => c.name === 'vite'),
      'nfb:supportLevel',
    ),
    'unknown',
  );
});

test('overrides by bare purl and by name', () => {
  const bom = load(fx('sbom-1.6.cdx.json'));
  addProps(bom, load(fx('overrides.json')).components);
  const all = [...components(bom)].map(({ c }) => c);
  assert.equal(
    prop(
      all.find((c) => c.name === 'three'),
      'nfb:supportLevel',
    ),
    'maintained',
  );
  assert.equal(
    prop(
      all.find((c) => c.name === 'vite'),
      'nfb:endOfSupport',
    ),
    '2027-06-30',
  );
});

test('CLI add -o writes a valid SBOM; check passes', () => {
  const dir = mkdtempSync(join(tmpdir(), 'sbom-props-'));
  try {
    const src = join(dir, 'in.json');
    copyFileSync(fx('sbom-1.6.cdx.json'), src);
    const out = join(dir, 'out.json');
    const r = run('add', src, '--overrides', fx('overrides.json'), '-o', out);
    assert.equal(r.status, 0, r.stdout + r.stderr);
    assert.equal(run('check', out).status, 0);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('spec < 1.6, bad values and non-CycloneDX fail', () => {
  const old = load(fx('sbom-1.5.cdx.json'));
  addProps(old);
  assert.match(checkBom(old).join('\n'), /specVersion 1\.5 < 1\.6/);
  const bom = load(fx('sbom-1.6.cdx.json'));
  addProps(bom);
  bom.components[0].properties[0].value = 'supported';
  bom.components[0].properties[1].value = '31.12.2027';
  const p = checkBom(bom).join('\n');
  assert.match(p, /"supported" not in/);
  assert.match(p, /not YYYY-MM-DD/);
  assert.match(checkBom({ bomFormat: 'SPDX', specVersion: '2.3' }).join('\n'), /not "CycloneDX"/);
  const v17 = load(fx('sbom-1.6.cdx.json'));
  v17.specVersion = '1.7';
  addProps(v17);
  assert.deepEqual(checkBom(v17), []);
});

// ---- M2-REVIEW MinIO decision (SEC-083): CI container images in the SBOM, MinIO unmaintained
const repo = join(here, '..', '..', '..');
const ciImages = () => load(join(repo, 'security', 'sbom-ci-images.json')).components;
const supportLevels = () => load(join(repo, 'security', 'support-levels.json')).components;

test('include adds components once (dedupe by purl / bom-ref) and rejects anonymous ones', () => {
  const bom = load(fx('sbom-1.6.cdx.json'));
  assert.equal(includeComponents(bom, ciImages()), 2);
  assert.equal(includeComponents(bom, ciImages()), 0);
  assert.throws(() => includeComponents(bom, [{ name: 'x' }]), /no purl or bom-ref/);
});

test('the repo SBOM marks bitnamilegacy/minio unmaintained and passes check', () => {
  const bom = load(fx('sbom-1.6.cdx.json'));
  includeComponents(bom, ciImages());
  addProps(bom, supportLevels());
  assert.deepEqual(checkBom(bom), []);
  const all = [...components(bom)].map(({ c }) => c);
  const minio = all.find((c) => c.name === 'bitnamilegacy/minio');
  assert.equal(prop(minio, 'nfb:supportLevel'), 'unmaintained');
  assert.equal(prop(minio, 'nfb:scope'), 'ci-only');
  const pg = all.find((c) => c.name === 'postgres');
  assert.equal(prop(pg, 'nfb:supportLevel'), 'maintained');
});

test('CLI add --include: the same result through the command CI runs', () => {
  const dir = mkdtempSync(join(tmpdir(), 'sbom-props-'));
  try {
    const src = join(dir, 'sbom.cdx.json');
    copyFileSync(fx('sbom-1.6.cdx.json'), src);
    const r = run(
      'add',
      src,
      '--overrides',
      join(repo, 'security', 'support-levels.json'),
      '--include',
      join(repo, 'security', 'sbom-ci-images.json'),
    );
    assert.equal(r.status, 0, r.stdout + r.stderr);
    const minio = load(src).components.find((c) => c.name === 'bitnamilegacy/minio');
    assert.equal(prop(minio, 'nfb:supportLevel'), 'unmaintained');
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('every image in docker-compose.ci.yml is in the SBOM include with the same digest', () => {
  const compose = readFileSync(join(repo, 'services', 'platform', 'docker-compose.ci.yml'), 'utf8');
  const images = [...compose.matchAll(/^\s*image:\s*([^\s@]+)@sha256:([0-9a-f]{64})\s*$/gm)];
  assert.ok(images.length >= 2, 'expected digest-pinned images');
  const listed = ciImages();
  for (const [, name, digest] of images) {
    const c = listed.find((x) => x.name === name || x.name === `library/${name}`);
    assert.ok(c, `${name} missing from security/sbom-ci-images.json`);
    assert.ok(c.purl.includes(`sha256%3A${digest}`), `${name}: digest differs from compose`);
  }
});

test('bitnamilegacy/minio appears in no compose file other than the CI one', () => {
  const r = spawnSync('git', ['ls-files', '*compose*.yml', '*compose*.yaml'], {
    cwd: repo,
    encoding: 'utf8',
  });
  assert.equal(r.status, 0, r.stderr);
  const files = r.stdout.split('\n').filter(Boolean);
  for (const f of files) {
    if (f === 'services/platform/docker-compose.ci.yml') continue;
    assert.ok(!readFileSync(join(repo, f), 'utf8').includes('bitnamilegacy/'), f);
  }
});
