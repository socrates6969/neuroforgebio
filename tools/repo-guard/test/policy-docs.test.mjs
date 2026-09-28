// Local acceptance tests for the document-level M0 SEC items (SEC-001, 002, 080, 084, 088) and the coverage table.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..');
const read = (p) => readFileSync(join(root, p), 'utf8');

test('SEC-001: SECURITY.md links the disclosure policy and the security contact; links resolve', () => {
  const s = read('SECURITY.md');
  assert.match(s, /\]\(docs\/security\/VULN-DISCLOSURE\.md\)/);
  assert.match(s, /security@<domain TBD>/);
  for (const [, target] of s.matchAll(/\]\(([^)#\s]+)(?:#[^)]*)?\)/g)) {
    if (/^[a-z]+:/i.test(target)) continue;
    assert.ok(existsSync(join(root, target)), `broken link in SECURITY.md: ${target}`);
  }
});

test('SEC-001: docs/security/VULN-DISCLOSURE.md is the unmodified input, placeholders intact', () => {
  const copy = read('docs/security/VULN-DISCLOSURE.md').split('\n').slice(1).join('\n');
  assert.equal(copy, read('docs/inputs/security/VULN-DISCLOSURE.md'));
  assert.match(copy, /security@<domain TBD>/);
});

test('SEC-002: PR template has the ADR + threat-model-delta and dependency-review checkboxes', () => {
  const t = read('.github/pull_request_template.md');
  assert.match(
    t,
    /- \[ \] Security-relevant: this PR links an ADR in `docs\/adr\/` that contains a \*\*threat-model delta\*\*/,
  );
  assert.match(
    t,
    /- \[ \] No new direct dependency, \*\*or\*\* every new direct dependency is listed below/,
  );
  assert.match(t, /SEC-084/);
});

test('SEC-084/088: CODEOWNERS covers every lockfile and manifest with the (marked) security role', () => {
  const c = read('.github/CODEOWNERS');
  assert.match(c, /PLACEHOLDER: `@PLACEHOLDER-ORG\/security-role` is NOT a real team/);
  for (const p of [
    '/pnpm-lock.yaml',
    '/uv.lock',
    '/Cargo.lock',
    'package.json',
    'pyproject.toml',
    'Cargo.toml',
    '/.github/',
    '/security/',
  ])
    assert.match(
      c,
      new RegExp(
        `^${p.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&')}\\s+@PLACEHOLDER-ORG/security-role`,
        'm',
      ),
      p,
    );
});

test('SEC-080: all three lockfiles are committed', () => {
  const tracked = execFileSync(
    'git',
    ['-C', root, 'ls-files', 'pnpm-lock.yaml', 'uv.lock', 'Cargo.lock'],
    {
      encoding: 'utf8',
    },
  );
  for (const f of ['pnpm-lock.yaml', 'uv.lock', 'Cargo.lock'])
    assert.match(tracked, new RegExp(`^${f.replace('.', '\\.')}$`, 'm'));
});

test('SEC-088: branch-protection doc lists the owner-gated settings and says nothing is applied', () => {
  const b = read('docs/security/branch-protection.md');
  assert.match(b, /\*\*NOT APPLIED\.\*\*/);
  for (const s of [
    'Require signed commits',
    'Block force pushes',
    'Require status checks',
    'Read repository contents',
    'Push protection',
    'required approvals **2**',
  ])
    assert.ok(b.includes(s), s);
});

test('SEC-COVERAGE.md has a row for every M0 SEC item and SEC-090/091', () => {
  const c = read('docs/security/SEC-COVERAGE.md');
  for (const id of [
    '001',
    '002',
    '080',
    '081',
    '082',
    '083',
    '084',
    '085',
    '086',
    '087',
    '088',
    '089',
    '090',
    '091',
  ])
    assert.match(c, new RegExp(`^\\| SEC-${id} \\|`, 'm'), `SEC-${id}`);
});
