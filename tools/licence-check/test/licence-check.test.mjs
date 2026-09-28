import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { checkTree, licenceOf, spdxAllowed } from '../lib.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, '..', '..', '..');
const cli = join(here, '..', 'cli.mjs');
const policy = JSON.parse(readFileSync(join(repoRoot, 'security', 'licences.json'), 'utf8'));
const allowed = new Set(policy.allowed);

// node_modules is git-ignored, so the fixture tree is written at test time.
function fixtureRepo(pkgs, webDeps) {
  const root = mkdtempSync(join(tmpdir(), 'licence-check-'));
  const w = (p, obj) => {
    mkdirSync(dirname(join(root, p)), { recursive: true });
    writeFileSync(join(root, p), JSON.stringify(obj));
  };
  w('package.json', { name: 'root', private: true });
  w('apps/web/package.json', {
    name: '@nf/web',
    private: true,
    dependencies: webDeps,
    devDependencies: { 'dev-only-gpl': '1.0.0' },
  });
  w('packages/ui/package.json', { name: '@nf/ui', private: true });
  w('node_modules/dev-only-gpl/package.json', {
    name: 'dev-only-gpl',
    version: '1.0.0',
    license: 'GPL-3.0-only',
  });
  for (const [name, fields] of Object.entries(pkgs))
    w(`node_modules/${name}/package.json`, { name, version: '1.0.0', ...fields });
  return root;
}

test('SEC-084: a GPL fixture dependency fails', () => {
  const root = fixtureRepo(
    {
      'ok-lib': { license: 'MIT', dependencies: { 'gpl-lib': '1.0.0' } },
      'gpl-lib': { license: 'GPL-3.0-or-later' },
    },
    { 'ok-lib': '1.0.0' },
  );
  try {
    const r = spawnSync(
      process.execPath,
      [cli, '--root', root, '--policy', join(repoRoot, 'security', 'licences.json')],
      {
        encoding: 'utf8',
      },
    );
    assert.equal(r.status, 1);
    assert.match(
      r.stdout,
      /gpl-lib@1\.0\.0: licence not allowed \(GPL-3\.0-or-later\)\s+\[apps\/web > ok-lib > gpl-lib\]/,
    );
    assert.doesNotMatch(r.stdout, /dev-only-gpl/, 'devDependencies are not shipped');
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('permissive tree passes; build-only subtree is not walked; missing licence fails', () => {
  const root = fixtureRepo(
    {
      astro: { license: 'MIT', dependencies: { 'sharp-like': '1.0.0' } },
      'sharp-like': { license: 'LGPL-3.0-or-later' },
      dual: { license: '(MIT OR GPL-2.0-only)' },
    },
    { astro: '1.0.0', dual: '1.0.0' },
  );
  try {
    assert.deepEqual(checkTree(root, policy).problems, []);
    writeFileSync(
      join(root, 'node_modules', 'dual', 'package.json'),
      JSON.stringify({ name: 'dual', version: '1.0.0' }),
    );
    assert.deepEqual(
      checkTree(root, policy).problems.map((p) => p.detail),
      ['no licence field'],
    );
    const ex = {
      ...policy,
      exceptions: { 'dual@1.0.0': 'reviewed: licence in LICENSE file is MIT' },
    };
    assert.deepEqual(checkTree(root, ex).problems, []);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('SPDX expressions', () => {
  assert.ok(spdxAllowed('MIT', allowed));
  assert.ok(spdxAllowed('(MIT OR GPL-3.0-only)', allowed));
  assert.ok(spdxAllowed('MIT AND (Apache-2.0 OR GPL-2.0-only)', allowed));
  assert.ok(!spdxAllowed('MIT AND GPL-2.0-only', allowed));
  assert.ok(!spdxAllowed('GPL-2.0-only WITH Classpath-exception-2.0', allowed));
  assert.ok(!spdxAllowed('LGPL-2.1-or-later', allowed));
  assert.ok(!spdxAllowed('MPL-2.0', allowed));
  assert.ok(!spdxAllowed('SEE LICENSE IN LICENSE.md', allowed));
  assert.ok(!spdxAllowed('(MIT', allowed));
  assert.equal(licenceOf({ license: { type: 'MIT' } }), 'MIT');
  assert.equal(
    licenceOf({ licenses: [{ type: 'MIT' }, { type: 'Apache-2.0' }] }),
    'MIT OR Apache-2.0',
  );
  assert.equal(licenceOf({}), null);
});

test('docs/security/licences.md lists exactly the allowed licences', () => {
  const md = readFileSync(join(repoRoot, 'docs', 'security', 'licences.md'), 'utf8');
  const section = md.split(/^## /m).find((s) => s.startsWith('Allowed'));
  const ids = [...section.matchAll(/^\|\s*`([^`]+)`\s*\|/gm)].map((m) => m[1]);
  assert.deepEqual(ids.sort(), [...policy.allowed].sort());
  for (const b of policy.buildOnly) assert.match(md, new RegExp('`' + b + '`'));
});
