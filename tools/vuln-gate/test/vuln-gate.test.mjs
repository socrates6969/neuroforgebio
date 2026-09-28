import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  cvss3Score,
  fromCargoAudit,
  fromPipAudit,
  fromPnpmAudit,
  gate,
  kevSet,
  validateVex,
} from '../lib.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, '..', '..', '..');
const cli = join(here, '..', 'cli.mjs');
const fx = (n) => join(here, 'fixtures', n);
const load = (n) => JSON.parse(readFileSync(fx(n), 'utf8'));
const run = (...a) => spawnSync(process.execPath, [cli, ...a], { encoding: 'utf8' });
const emptyDir = () => mkdtempSync(join(tmpdir(), 'vex-empty-'));

test('SEC-085: a fixture dependency with a high CVE + fix fails', () => {
  const dir = emptyDir();
  try {
    const r = run('--pnpm', fx('pnpm-audit-high.json'), '--kev', fx('kev.json'), '--vex', dir);
    assert.equal(r.status, 1);
    assert.match(
      r.stdout,
      /BLOCK: npm:fixture-lib@1\.0\.0 GHSA-fixt-ure0-0001 .*high severity with a fix available/,
    );
    assert.doesNotMatch(r.stdout, /fixture-moderate/, 'moderate is below the gate');
    assert.doesNotMatch(r.stdout, /fixture-nofix/, 'no fix available and not in KEV');
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('SEC-085: adding a VEX not_affected statement makes it pass', () => {
  const r = run(
    '--pnpm',
    fx('pnpm-audit-high.json'),
    '--kev',
    fx('kev.json'),
    '--vex',
    fx('vex-ok'),
  );
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.match(r.stdout, /VEX not_affected: npm:fixture-lib@1\.0\.0/);
});

test('SEC-085: a KEV-listed CVE fails even with low severity and no fix', () => {
  const dir = emptyDir();
  try {
    const r = run('--cargo', fx('cargo-audit-kev.json'), '--kev', fx('kev.json'), '--vex', dir);
    assert.equal(r.status, 1);
    assert.match(
      r.stdout,
      /BLOCK: cargo:fixture-crate@0\.4\.0 RUSTSEC-2099-0001 \(CVE-2099-0002\) \[listed in CISA KEV\]/,
    );
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('pip-audit findings have no severity and count as unknown (blocking when fixable)', () => {
  const f = fromPipAudit(load('pip-audit.json'));
  assert.equal(f.length, 1);
  assert.equal(f[0].severity, 'unknown');
  assert.equal(gate(f, kevSet(load('kev.json')), []).failures.length, 1);
});

test('an invalid VEX (not_affected without justification) fails and does not suppress', () => {
  const doc = JSON.parse(
    readFileSync(join(fx('vex-bad'), 'no-justification.openvex.json'), 'utf8'),
  );
  assert.match(validateVex(doc).join(), /justification/);
  const r = run(
    '--pnpm',
    fx('pnpm-audit-high.json'),
    '--kev',
    fx('kev.json'),
    '--vex',
    fx('vex-bad'),
  );
  assert.equal(r.status, 1);
  assert.match(r.stdout, /invalid VEX/);
  assert.match(r.stdout, /BLOCK: npm:fixture-lib/);
});

test('a VEX for another version or package does not suppress', () => {
  const findings = fromPnpmAudit(load('pnpm-audit-high.json'));
  const vex = JSON.parse(readFileSync(join(fx('vex-ok'), 'fixture-lib.openvex.json'), 'utf8'));
  vex.statements[0].products = [{ '@id': 'pkg:npm/fixture-lib@9.9.9' }];
  assert.equal(gate(findings, kevSet(load('kev.json')), [vex]).failures.length, 1);
  vex.statements[0].products = [{ '@id': 'pkg:npm/other-lib' }];
  assert.equal(gate(findings, kevSet(load('kev.json')), [vex]).failures.length, 1);
  vex.statements[0].products = [{ '@id': 'pkg:npm/fixture-lib' }];
  assert.equal(gate(findings, kevSet(load('kev.json')), [vex]).failures.length, 0);
});

test('missing KEV catalogue or empty audit output is an error, not a pass', () => {
  assert.equal(run('--pnpm', fx('pnpm-audit-high.json')).status, 2);
  const dir = emptyDir();
  try {
    const empty = join(dir, 'pnpm-audit.json');
    writeFileSync(empty, '');
    assert.equal(
      run('--pnpm', empty, '--kev', fx('kev.json'), '--vex', dir).status,
      2,
      'empty audit output',
    );
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('CVSS 3.1 base scores', () => {
  assert.equal(cvss3Score('CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H'), 9.8);
  assert.equal(cvss3Score('CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N'), 6.1);
  assert.equal(cvss3Score('CVSS:3.1/AV:L/AC:H/PR:H/UI:R/S:U/C:L/I:N/A:N'), 1.8);
  assert.equal(cvss3Score('CVSS:4.0/AV:N'), null);
  assert.equal(fromCargoAudit(load('cargo-audit-kev.json'))[0].severity, 'low');
});

test('every committed VEX document under security/vex is valid OpenVEX', () => {
  const dir = join(repoRoot, 'security', 'vex');
  for (const f of readdirSync(dir).filter((x) => x.endsWith('.json')))
    assert.deepEqual(validateVex(JSON.parse(readFileSync(join(dir, f), 'utf8'))), [], f);
});
