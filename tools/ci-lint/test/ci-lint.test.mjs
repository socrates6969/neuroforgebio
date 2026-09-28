import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { adHocRunner, checkRunLine, checkUses, lintWorkflow } from '../lib.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, '..', '..', '..');
const fixture = (name) => readFileSync(join(here, 'fixtures', name), 'utf8');
const rules = (yaml) => lintWorkflow(yaml).map((p) => p.rule);

test('good fixture passes', () => {
  assert.deepEqual(lintWorkflow(fixture('good.yml')), []);
});

test('SEC-089: a tag-pinned action fails', () => {
  const p = lintWorkflow(fixture('tag-pinned.yml'));
  assert.equal(p.length, 1);
  assert.equal(p[0].rule, 'action-pin');
  assert.match(p[0].detail, /actions\/checkout@v4/);
});

test('SEC-089: pull_request_target is banned', () => {
  assert.ok(rules(fixture('pull-request-target.yml')).includes('pull-request-target'));
});

test('SEC-089: missing or broad top-level permissions fail', () => {
  assert.deepEqual(rules('on: workflow_dispatch\njobs: {}\n'), ['permissions']);
  assert.deepEqual(rules('on: workflow_dispatch\npermissions: write-all\njobs: {}\n'), [
    'permissions',
  ]);
  assert.deepEqual(rules('on: workflow_dispatch\npermissions:\n  contents: write\njobs: {}\n'), [
    'permissions',
  ]);
  assert.deepEqual(rules('on: workflow_dispatch\npermissions:\n  contents: read\njobs: {}\n'), []);
});

test('SEC-080: unlocked installs fail', () => {
  const p = lintWorkflow(fixture('unlocked-install.yml'));
  const details = p.map((x) => x.detail).join('\n');
  assert.match(details, /pnpm install` without --frozen-lockfile/);
  assert.match(details, /uv sync` without --locked/);
  assert.match(details, /cargo build\/test\/\.\.\.` without --locked/);
  assert.match(details, /npm install/);
  assert.equal(p.filter((x) => x.rule === 'frozen-install').length, 5);
  assert.equal(p.filter((x) => x.rule === 'ad-hoc-runner').length, 1, 'the npx line');
});

test('uses/run unit checks', () => {
  const sha = 'a'.repeat(40);
  assert.equal(checkUses(`actions/checkout@${sha}`, '# v4.4.0'), null);
  assert.match(checkUses(`actions/checkout@${sha}`, ''), /comment/);
  assert.match(checkUses('actions/checkout@main', ''), /full commit SHA/);
  assert.match(checkUses(`actions/checkout@${sha.slice(0, 7)}`, '# v4'), /full commit SHA/);
  assert.equal(checkUses('./.github/actions/local', ''), null);
  assert.match(checkUses('docker://alpine:3.20', ''), /digest/);
  assert.deepEqual(checkRunLine('pnpm install --frozen-lockfile'), []);
  assert.deepEqual(checkRunLine('uv sync --locked --group readers'), []);
  assert.deepEqual(checkRunLine('cargo fmt --all -- --check'), []);
  assert.deepEqual(checkRunLine('cargo audit --json'), []);
  assert.deepEqual(checkRunLine('cargo test --workspace --locked'), []);
  assert.deepEqual(checkRunLine('uvx pip-audit@2.10.1 -r req.txt'), []);
  assert.equal(checkRunLine('uvx pip-audit -r req.txt').length, 1);
  assert.deepEqual(
    checkRunLine('pnpm --filter @nf/web exec playwright install --with-deps chromium'),
    [],
  );
});

test('every workflow in this repo passes', () => {
  const dir = join(repoRoot, '.github', 'workflows');
  for (const f of readdirSync(dir).filter((x) => /\.ya?ml$/.test(x)))
    assert.deepEqual(lintWorkflow(readFileSync(join(dir, f), 'utf8'), { file: f }), [], f);
});

test('APP-L3/P1: inputs.* / github.event.* / github.head_ref expressions inside run: fail', () => {
  const p = lintWorkflow(fixture('expr-injection.yml')).filter((x) => x.rule === 'run-expression');
  assert.deepEqual(
    p.map((x) => x.line),
    [13, 17, 21],
  );
  assert.match(p[0].detail, /inputs\.x/);
  assert.match(p[1].detail, /github\.event\.issue\.title/);
  assert.match(p[2].detail, /github\.head_ref/);
  assert.deepEqual(rules(fixture('expr-injection.yml')), [
    'run-expression',
    'run-expression',
    'run-expression',
  ]);
});

test('APP-L3/P1: repro-check passes inputs.seeds via env and validates it', () => {
  const yml = readFileSync(join(repoRoot, '.github', 'workflows', 'repro-check.yml'), 'utf8');
  assert.match(yml, /\n\s+SEEDS: \$\{\{ inputs\.seeds \}\}\n/);
  assert.match(yml, /"\$SEEDS" =~ \^\[0-9\]/);
  assert.doesNotMatch(yml, /run:[^\n]*\n?[^\n]*\$\{\{\s*inputs\./);
});

test('APP-L5/P3: any ad-hoc JS package runner fails, with or without -y (npx, pnpm dlx, ...)', () => {
  const all = lintWorkflow(fixture('ad-hoc-runners.yml'));
  const p = all.filter((x) => x.rule === 'ad-hoc-runner');
  assert.deepEqual(
    p.map((x) => x.line),
    [10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21],
  );
  assert.match(p[0].detail, /pnpm exec/);
  assert.match(p[3].detail, /^`npx`/, 'plain `npx pkg@x.y.z` (no -y) is banned too');
  assert.match(p[5].detail, /^`pnpm dlx`/);
  // pnpm exec, a node_modules/.bin path, comments and look-alike words pass
  assert.deepEqual(
    all.filter((x) => x.rule !== 'ad-hoc-runner'),
    [],
  );
});

test('adHocRunner unit checks', () => {
  assert.equal(adHocRunner('npx -y foo@1.2.3'), 'npx');
  assert.equal(adHocRunner('npx foo@1.2.3'), 'npx');
  assert.equal(adHocRunner('(cd x && npx foo)'), 'npx');
  assert.equal(adHocRunner('pnpm  dlx foo'), 'pnpm dlx');
  assert.equal(adHocRunner('npm exec -- foo'), 'npm exec');
  assert.equal(adHocRunner('pnpm exec cdxgen'), null);
  assert.equal(adHocRunner('pnpm --filter @nf/web exec playwright install'), null);
  assert.equal(adHocRunner('echo snpx unpnpx npx-like'), null);
});

test('APP-L5/P3: actions/checkout without persist-credentials: false fails', () => {
  const p = lintWorkflow(fixture('checkout-credentials.yml'));
  assert.deepEqual(
    p.map((x) => `${x.rule}:${x.line}`),
    ['checkout-credentials:10', 'checkout-credentials:11', 'checkout-credentials:15'],
  );
  assert.match(p[0].detail, /persist-credentials: false/);
});

test('APP-L5/P3: cdxgen is an isolated, exact-pinned CI-only package, never a root dependency', () => {
  const root = JSON.parse(readFileSync(join(repoRoot, 'package.json'), 'utf8'));
  assert.equal((root.devDependencies || {})['@cyclonedx/cdxgen'], undefined, 'not in the root');
  assert.equal((root.dependencies || {})['@cyclonedx/cdxgen'], undefined, 'not in the root');
  const iso = JSON.parse(
    readFileSync(join(repoRoot, 'tools', 'sbom-cdxgen', 'package.json'), 'utf8'),
  );
  assert.match(iso.dependencies['@cyclonedx/cdxgen'], /^\d+\.\d+\.\d+$/);
  const dir = join(repoRoot, '.github', 'workflows');
  let runs = 0;
  for (const f of readdirSync(dir).filter((x) => /\.ya?ml$/.test(x))) {
    const y = readFileSync(join(dir, f), 'utf8');
    assert.doesNotMatch(y, /npx[^\n]*cdxgen|pnpm exec cdxgen/, f);
    runs += (y.match(/tools\/sbom-cdxgen\/node_modules\/\.bin\/cdxgen/g) || []).length;
    // every job that runs the scanner installs it isolated, without install scripts
    if (/tools\/sbom-cdxgen\/node_modules/.test(y))
      assert.match(
        y,
        /pnpm install --dir tools\/sbom-cdxgen --ignore-workspace --frozen-lockfile --ignore-scripts/,
        f,
      );
  }
  assert.equal(runs, 3, 'ci.yml (web + repo SBOM) and release.yml');
});

test('APP-L4: a job using a secret needs environment:, exceptions expire', () => {
  const wf = (env) =>
    [
      'on:',
      '  workflow_dispatch:',
      'permissions:',
      '  contents: read',
      'jobs:',
      '  study:',
      '    runs-on: ubuntu-latest',
      ...(env ? ['    environment: study'] : []),
      '    steps:',
      '      - run: echo hi',
      '        env:',
      '          T: ${{ secrets.NF_STUDY_API_TOKEN }}',
      '  plain:',
      '    runs-on: ubuntu-latest',
      '    steps:',
      '      - run: echo ${{ secrets.GITHUB_TOKEN }} | wc -c',
      '',
    ].join('\n');
  const envRule = (yaml, opts) =>
    lintWorkflow(yaml, opts).filter((p) => p.rule === 'secret-environment');
  // no environment and no exception -> fails; GITHUB_TOKEN alone does not count
  assert.deepEqual(
    envRule(wf(false), { file: 'other.yml' }).map((p) => p.line),
    [11],
  );
  // with environment -> passes
  assert.deepEqual(envRule(wf(true), { file: 'other.yml' }), []);
  // listed exception before expiry -> passes; after expiry -> fails with the reason
  assert.deepEqual(envRule(wf(false), { file: 'multiverse-study.yml', today: '2026-10-31' }), []);
  const late = envRule(wf(false), { file: 'multiverse-study.yml', today: '2026-11-01' });
  assert.equal(late.length, 1);
  assert.match(late[0].detail, /expired on 2026-10-31/);
});
