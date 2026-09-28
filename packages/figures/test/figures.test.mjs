import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, copyFileSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { loadManifest, verifyManifest, readResult, ManifestError } from '../src/manifest.ts';
import { extract, ExtractError } from '../src/extract.ts';
import { renderSvg, tableRows, niceTicks } from '../src/svg.ts';
import { stepIndex } from '../src/keys.ts';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, '../../..');
const manifestPath = join(here, '../manifests/somatosensory-closed-loop.figures.json');
// Renderer coverage for kinds that are not in the published manifest (line, scatter).
const fixturePath = join(here, 'fixtures/unpublished.figures.json');
const allFigures = () => [
  ...loadManifest(manifestPath).figures,
  ...loadManifest(fixturePath).figures,
];

function copyPinnedTree() {
  const m = loadManifest(manifestPath);
  const tmp = mkdtempSync(join(tmpdir(), 'nf-fig-'));
  for (const f of m.figures)
    for (const p of [f.result, f.staticSvg, f.script]) {
      if (!p) continue;
      mkdirSync(dirname(join(tmp, p.path)), { recursive: true });
      copyFileSync(join(repoRoot, p.path), join(tmp, p.path));
    }
  return { m, tmp };
}

test('manifest verifies against the repository files', () => {
  verifyManifest(loadManifest(manifestPath), repoRoot);
});

test('every figure is "preliminary"; nothing is labelled verified', () => {
  const raw = readFileSync(manifestPath, 'utf8');
  assert.doesNotMatch(raw, /verified/i);
  for (const f of loadManifest(manifestPath).figures) assert.equal(f.status, 'preliminary');
});

test('changing one byte of a result file (temp copy) fails verification', () => {
  const { m, tmp } = copyPinnedTree();
  try {
    verifyManifest(m, tmp); // the untouched copy passes
    const target = join(tmp, m.figures[0].result.path);
    const buf = readFileSync(target);
    const i = buf.indexOf(0x35) >= 0 ? buf.indexOf(0x35) : 10; // first "5" digit
    buf[i] = buf[i] === 0x36 ? 0x37 : 0x36;
    writeFileSync(target, buf);
    assert.throws(() => verifyManifest(m, tmp), ManifestError);
    const cli = spawnSync(
      process.execPath,
      [join(here, '../scripts/verify.mjs'), manifestPath, tmp],
      { encoding: 'utf8' },
    );
    assert.equal(cli.status, 1, cli.stderr);
    assert.match(cli.stderr, /SHA-256 mismatch/);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test('extracts only existing numeric fields; a missing field throws', () => {
  const figures = allFigures();
  for (const f of figures) {
    const d = extract(f.plot, readResult(f, repoRoot));
    const svg = renderSvg(d, { ariaLabel: f.id });
    assert.match(svg, /^<svg [^>]*role="img"[^>]*aria-label="/);
    assert.ok((svg.match(/data-readout=/g) ?? []).length > 0);
    assert.doesNotMatch(svg, /#[0-9a-f]{3,8}\b|rgb\(|font-family/i);
    assert.ok(tableRows(d).rows.length > 0);
  }
  const line = figures.find((x) => x.plot.kind === 'line');
  const bad = structuredClone(line.plot);
  bad.series[0].path = ['R_curves', 'does-not-exist'];
  assert.throws(() => extract(bad, readResult(line, repoRoot)), ExtractError);
});

test('line figure plots the stored values unchanged', () => {
  const f = allFigures().find((x) => x.plot.kind === 'line');
  const json = readResult(f, repoRoot);
  const d = extract(f.plot, json);
  assert.deepEqual(d.x, json.R_curves.deltas);
  assert.deepEqual(d.series[0].y, json.R_curves['0.5']);
});

test('ticks and keyboard stepping', () => {
  assert.deepEqual(niceTicks(0, 10, 5), [0, 2, 4, 6, 8, 10]);
  assert.equal(stepIndex(-1, 'ArrowRight', 5), 0);
  assert.equal(stepIndex(4, 'ArrowRight', 5), 4);
  assert.equal(stepIndex(2, 'ArrowLeft', 5), 1);
  assert.equal(stepIndex(2, 'End', 5), 4);
  assert.equal(stepIndex(2, 'Home', 5), 0);
  assert.equal(stepIndex(2, 'a', 5), null);
});
