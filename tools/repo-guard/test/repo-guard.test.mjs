import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import {
  mkdtempSync,
  mkdirSync,
  writeFileSync,
  rmSync,
  readdirSync,
  readFileSync,
  existsSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  scanSecrets,
  checkDataFile,
  checkWorkflow,
  workflowTriggers,
  ALLOW_MARKER,
  MAX_FILE_BYTES,
  checkLargeFile,
  checkArenaPkg,
  parseSha256Sums,
  ARENA_PKG,
  ARENA_MANIFEST,
  ARENA_FILES,
  ARENA_PUBLIC,
  checkBuildScripts,
  installedBuildPackages,
  lockfileBuildPackages,
  pnpmKeyName,
  REVIEWED_UNBUILT,
  lockfileSourceProblems,
  checkSbomScanner,
  SBOM_SCANNER_DIR,
} from '../lib.mjs';
import { createHash } from 'node:crypto';

const here = dirname(fileURLToPath(import.meta.url));
const cli = join(here, '..', 'cli.mjs');
const repoRoot = join(here, '..', '..', '..');

// Fake credentials are assembled at run time so no committed file contains one.
const FAKE_AWS_ID = ['AK', 'IA', 'IOSFODNN7', 'EXAMPLE'].join('');
const FAKE_AWS_SECRET = ['wJalrXUtnFEMI', '/K7MDENG/bPxRfiCY', 'EXAMPLEKEY'].join('');

function tempRepo(files) {
  const root = mkdtempSync(join(tmpdir(), 'repo-guard-'));
  execFileSync('git', ['-C', root, 'init', '-q']);
  for (const [p, content] of Object.entries(files)) {
    mkdirSync(dirname(join(root, p)), { recursive: true });
    writeFileSync(join(root, p), content);
  }
  execFileSync('git', ['-C', root, 'add', '-A']);
  return root;
}
const guard = (root) => spawnSync(process.execPath, [cli, '--root', root], { encoding: 'utf8' });

test('a committed fake AWS key fails', () => {
  const root = tempRepo({
    'config.js': `const id = "${FAKE_AWS_ID}";\nconst ok = 1;\n`,
    'deploy.sh': `aws_secret_access_key = ${FAKE_AWS_SECRET}\n`,
  });
  try {
    const r = guard(root);
    assert.equal(r.status, 1);
    assert.match(r.stdout, /config\.js:1: secret: aws-access-key-id/);
    assert.match(r.stdout, /deploy\.sh:1: secret: aws-secret-access-key/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('a committed .edf file (and data/ dir, .env) fails', () => {
  const root = tempRepo({
    'rec/sub-01.edf': Buffer.from([0x30, 0x20, 0x20]),
    'data/raw.csv': 'a,b\n',
    '.env': 'X=1\n',
    'README.md': 'clean\n',
  });
  try {
    const r = guard(root);
    assert.equal(r.status, 1);
    assert.match(r.stdout, /rec\/sub-01\.edf: data-file/);
    assert.match(r.stdout, /data\/raw\.csv: data-file/);
    assert.match(r.stdout, /\.env: secret-file/);
    assert.doesNotMatch(r.stdout, /README/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('clean temp repo passes; allow marker suppresses a documented example', () => {
  const root = tempRepo({
    'doc.md': `Example: ${FAKE_AWS_ID} <!-- ${ALLOW_MARKER} -->\n`,
    '.env.example': 'X=\n',
  });
  try {
    assert.equal(guard(root).status, 0);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('secret patterns', () => {
  const pk = ['-----BEGIN RSA PRIV', 'ATE KEY-----'].join('');
  assert.deepEqual(scanSecrets(`x\n${pk}\n`), [{ line: 2, name: 'private-key' }]);
  assert.deepEqual(
    scanSecrets(`token: ${'gh' + 'p_' + 'a'.repeat(36)}`).map((h) => h.name),
    ['github-token'],
  );
  assert.deepEqual(scanSecrets('AKIA is a prefix; sha256:abcdef'), []);
});

test('data file detection', () => {
  for (const f of [
    'a.EDF',
    'x/y.bdf',
    'z.nwb',
    's.xdf',
    'e.set',
    'r.fif',
    'h.vhdr',
    'm.vmrk',
    'b.eeg',
    'data/x.txt',
    'd/rec.zarr/0.0',
  ])
    assert.ok(checkDataFile(f), f);
  for (const f of ['src/metadata.ts', 'docs/database.md', 'tools/synth/writers/edf.py'])
    assert.equal(checkDataFile(f), null, f);
});

test('workflow trigger parser', () => {
  assert.equal(
    checkWorkflow('name: x\non:\n  workflow_dispatch:\n    inputs: {}\njobs: {}\n'),
    null,
  );
  assert.equal(checkWorkflow('on: workflow_dispatch\njobs: {}\n'), null);
  assert.equal(checkWorkflow('on: [workflow_dispatch]\n'), null);
  assert.match(checkWorkflow('on:\n  workflow_dispatch:\n  push:\n    branches: [main]\n'), /push/);
  assert.match(checkWorkflow('on: [push, workflow_dispatch]\n'), /push/);
  assert.match(checkWorkflow('"on":\n  pull_request:\n'), /pull_request/);
  assert.match(
    checkWorkflow('on:\n  schedule:\n    - cron: "0 0 * * *"\n  workflow_dispatch:\n'),
    /schedule/,
  );
  assert.deepEqual(
    [...workflowTriggers('on:\n  # push:\n  workflow_dispatch:\n')],
    ['workflow_dispatch'],
  );
});

test('no workflow in this repo has a non-dispatch trigger', () => {
  const dir = join(repoRoot, '.github', 'workflows');
  const files = existsSync(dir) ? readdirSync(dir).filter((f) => /\.ya?ml$/.test(f)) : [];
  for (const f of files) assert.equal(checkWorkflow(readFileSync(join(dir, f), 'utf8')), null, f);
});

test('SEC-087: every listed recording extension and data/ are rejected', () => {
  for (const ext of [
    'edf',
    'bdf',
    'nwb',
    'xdf',
    'set',
    'fdt',
    'fif',
    'vhdr',
    'eeg',
    'vmrk',
    'mat',
    'npy',
    'zarr',
  ])
    assert.ok(checkDataFile(`any/dir/rec.${ext}`), ext);
  assert.ok(checkDataFile('data/README.txt'));
  assert.ok(checkDataFile('sub/data/x.csv'));
});

test('SEC-087: a tracked file > 5 MB fails outside tools/synth/fixtures', () => {
  const big = Buffer.alloc(MAX_FILE_BYTES + 1, 0x61);
  const root = tempRepo({
    'assets/huge.bin': big,
    'tools/synth/fixtures/ok.bin': big,
    'small.txt': 'x\n',
  });
  try {
    const r = guard(root);
    assert.equal(r.status, 1);
    assert.match(r.stdout, /assets\/huge\.bin: large-file: file is 5\.0 MB/);
    assert.doesNotMatch(r.stdout, /ok\.bin/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
  assert.equal(checkLargeFile('x.bin', MAX_FILE_BYTES), null);
  assert.ok(checkLargeFile('x.bin', MAX_FILE_BYTES + 1));
});

test('SEC-087: .gitignore covers every recording pattern', () => {
  const gi = readFileSync(join(repoRoot, '.gitignore'), 'utf8').split(/\r?\n/);
  for (const p of [
    '*.edf',
    '*.bdf',
    '*.nwb',
    '*.xdf',
    '*.set',
    '*.fdt',
    '*.fif',
    '*.vhdr',
    '*.eeg',
    '*.vmrk',
    '*.mat',
    '*.npy',
    '*.zarr',
    'data/',
  ])
    assert.ok(gi.includes(p), p);
});

// EXC-150-1 condition 4 (ADR 0014): the committed /arena wasm must match the CI-verified manifest.
test('arena pkg/: exact manifest passes; hand edits, extra files, bad or orphan manifests fail', () => {
  const root = mkdtempSync(join(tmpdir(), 'repo-guard-arena-'));
  const sha = (b) => createHash('sha256').update(b).digest('hex');
  try {
    assert.deepEqual(checkArenaPkg(root), [], 'no pkg/ yet (stub state): nothing to check');
    const dir = join(root, ARENA_PKG);
    const man = join(root, ARENA_MANIFEST);
    const bytes = {
      'arena_core.d.ts': 'export function run(): string;\n',
      'arena_core.js': "import wasmUrl from './arena_core_bg.wasm?url';\n",
      'arena_core_bg.wasm': Buffer.from([0x00, 0x61, 0x73, 0x6d, 0x01, 0x00, 0x00, 0x00]),
      'arena_core_bg.wasm.d.ts': 'export const memory: WebAssembly.Memory;\n',
    };
    assert.deepEqual(Object.keys(bytes).sort(), [...ARENA_FILES].sort());
    const write = (files) => {
      rmSync(dir, { recursive: true, force: true });
      mkdirSync(dir, { recursive: true });
      for (const [n, b] of Object.entries(files)) writeFileSync(join(dir, n), b);
    };
    const sums = (files) =>
      Object.keys(files)
        .sort()
        .map((n) => `${sha(files[n])}  ${n}`)
        .join('\n') + '\n';
    const rules = () =>
      checkArenaPkg(root)
        .map((p) => `${p.rule}: ${p.file}: ${p.detail}`)
        .join('\n');
    write(bytes);
    // pkg/ without a manifest fails
    assert.match(rules(), /arena-pkg\.sha256: missing/);
    mkdirSync(dirname(man), { recursive: true });
    writeFileSync(man, sums(bytes));
    assert.equal(rules(), '', 'exact manifest passes');
    // a hand-edited .wasm fails
    writeFileSync(
      join(dir, 'arena_core_bg.wasm'),
      Buffer.from([0x00, 0x61, 0x73, 0x6d, 0x01, 0x00, 0x00, 0x01]),
    );
    assert.match(rules(), /arena_core_bg\.wasm: SHA-256 .* does not match the manifest/);
    // an extra file fails
    write({ ...bytes, 'evil.js': 'alert(1)\n' });
    writeFileSync(man, sums(bytes));
    assert.match(rules(), /file set must be exactly/);
    // a malformed or incomplete manifest fails
    write(bytes);
    writeFileSync(man, sums(bytes).split('\n').slice(1).join('\n') + 'nonsense\n');
    const r2 = rules();
    assert.match(r2, /malformed line: nonsense/);
    assert.match(r2, /must list exactly/);
    assert.equal(parseSha256Sums(sums(bytes)).entries.size, 4);
    // a manifest without pkg/ fails
    rmSync(dir, { recursive: true, force: true });
    writeFileSync(man, sums(bytes));
    assert.match(rules(), /present but .* is not committed/);
    rmSync(man);
    // anything under apps/web/public/arena/ fails (arena files must be Vite-hashed assets)
    mkdirSync(join(root, ARENA_PUBLIC, 'pkg'), { recursive: true });
    writeFileSync(join(root, ARENA_PUBLIC, 'pkg', 'arena_core.js'), 'x\n');
    assert.match(rules(), /public\/arena: must not exist/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('arena pkg/: this repo passes (vacuous until pkg/ is committed)', () => {
  assert.deepEqual(checkArenaPkg(repoRoot), []);
});

test('APP-L6/P4: a requiresBuild package outside pnpm.onlyBuiltDependencies fails', () => {
  const lock = [
    "lockfileVersion: '9.0'",
    'packages:',
    '  esbuild@0.25.12:',
    '    resolution: {integrity: sha512-x}',
    '    requiresBuild: true',
    "  '@evil/pkg@1.0.0':",
    '    requiresBuild: true',
    '  plain@1.0.0:',
    '    resolution: {integrity: sha512-y}',
    '',
  ].join('\n');
  assert.deepEqual(lockfileBuildPackages(lock), ['@evil/pkg', 'esbuild']);
  const pkg = (allow) =>
    JSON.stringify({
      name: 'x',
      private: true,
      ...(allow ? { pnpm: { onlyBuiltDependencies: allow } } : {}),
    });
  const details = (files) => {
    const root = tempRepo(files);
    try {
      return checkBuildScripts(root)
        .map((p) => `${p.file}: ${p.detail}`)
        .join('\n');
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  };
  assert.match(
    details({ 'package.json': pkg(null), 'pnpm-lock.yaml': lock }),
    /onlyBuiltDependencies` missing/,
  );
  const d = details({ 'package.json': pkg(['esbuild']), 'pnpm-lock.yaml': lock });
  assert.match(d, /@evil\/pkg has requiresBuild: true/);
  assert.doesNotMatch(d, /esbuild has requiresBuild/);
  assert.equal(
    details({ 'package.json': pkg(['esbuild', '@evil/pkg']), 'pnpm-lock.yaml': lock }),
    '',
  );
  assert.match(
    details({
      'package.json': pkg(['esbuild', '@evil/pkg']),
      'pnpm-lock.yaml': lock,
      'pnpm-workspace.yaml': 'packages: []\nonlyBuiltDependencies: []\n',
    }),
    /ignored by pnpm 9/,
  );
  // the CLI reports it too
  const root = tempRepo({ 'package.json': pkg(['esbuild']), 'pnpm-lock.yaml': lock });
  try {
    const r = guard(root);
    assert.equal(r.status, 1);
    assert.match(r.stdout, /build-scripts: @evil\/pkg/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
  assert.equal(pnpmKeyName('/@a/b@1.0.0(peer@2.0.0)'), '@a/b');
  assert.equal(pnpmKeyName('@a+b@1.0.0_x@2'), '@a/b');
  assert.equal(pnpmKeyName('astro@5.18.2_rollup@4.63.5'), 'astro');
});

// APP-L5 (nfb-security 2026-09-27): isolated SBOM scanner + lockfile source policy.
const LOCK_OK = [
  "lockfileVersion: '9.0'",
  '',
  'importers:',
  '',
  '  .:',
  '    dependencies:',
  "      '@cyclonedx/cdxgen':",
  '        specifier: 12.8.4',
  '        version: 12.8.4',
  '',
  'packages:',
  '',
  "  '@cyclonedx/cdxgen@12.8.4':",
  '    resolution: {integrity: sha512-AAAA}',
  '    hasBin: true',
  '',
  '  left-pad@1.3.0:',
  '    resolution: {integrity: sha512-BBBB}',
  '',
  'snapshots:',
  '',
  '  left-pad@1.3.0: {}',
  '',
].join('\n');

test('APP-L5: lockfile source policy: integrity required, git and tarball sources refused', () => {
  assert.deepEqual(lockfileSourceProblems(LOCK_OK), []);
  const git = LOCK_OK.replace(
    'resolution: {integrity: sha512-BBBB}',
    'resolution: {commit: abc, repo: https://github.com/x/left-pad, type: git}',
  );
  assert.match(lockfileSourceProblems(git)[0].detail, /left-pad@1\.3\.0: git or tarball/);
  const tarball = LOCK_OK.replace(
    'resolution: {integrity: sha512-BBBB}',
    'resolution: {integrity: sha512-BBBB, tarball: https://evil.example/left-pad.tgz}',
  );
  assert.match(lockfileSourceProblems(tarball)[0].detail, /git or tarball/);
  const noHash = LOCK_OK.replace('resolution: {integrity: sha512-BBBB}', 'resolution: {}');
  assert.match(lockfileSourceProblems(noHash)[0].detail, /no integrity hash/);
});

test('APP-L5: the SBOM scanner stays isolated (workspace exclusion, own lockfile, not in the root lockfile)', () => {
  const files = (over = {}) => ({
    'package.json': '{"private":true,"pnpm":{"onlyBuiltDependencies":[]}}',
    'pnpm-workspace.yaml': `packages:\n  - 'tools/*'\n  - '!${SBOM_SCANNER_DIR}'\n`,
    'pnpm-lock.yaml': LOCK_OK.replace(/^ {2}'@cyclonedx.*\n.*\n.*\n\n/m, '').replace(
      /'@cyclonedx\/cdxgen':\n.*\n.*\n/,
      '',
    ),
    [`${SBOM_SCANNER_DIR}/package.json`]: '{"private":true}',
    [`${SBOM_SCANNER_DIR}/pnpm-lock.yaml`]: LOCK_OK,
    ...over,
  });
  const run = (over) => {
    const root = tempRepo(files(over));
    try {
      return checkSbomScanner(root).map((p) => `${p.file}: ${p.detail}`);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  };
  assert.deepEqual(run(), []);
  assert.match(run({ [`${SBOM_SCANNER_DIR}/pnpm-lock.yaml`]: '' }).join('\n'), /missing/);
  assert.match(
    run({ 'pnpm-workspace.yaml': "packages:\n  - 'tools/*'\n" }).join('\n'),
    /must exclude the scanner/,
  );
  assert.match(run({ 'pnpm-lock.yaml': LOCK_OK }).join('\n'), /must not be in the root lockfile/);
});

test('APP-L6/P4: this repo sets an allowlist and every installed install script is reviewed', () => {
  const allow = JSON.parse(readFileSync(join(repoRoot, 'package.json'), 'utf8')).pnpm
    ?.onlyBuiltDependencies;
  assert.ok(Array.isArray(allow), 'package.json pnpm.onlyBuiltDependencies');
  assert.deepEqual(checkBuildScripts(repoRoot), []);
  const installed = installedBuildPackages(repoRoot);
  if (installed) {
    assert.ok(installed.includes('esbuild'), 'the scan sees esbuild');
    for (const n of installed) assert.ok(allow.includes(n) || REVIEWED_UNBUILT.includes(n), n);
  }
});
