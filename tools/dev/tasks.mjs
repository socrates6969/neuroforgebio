#!/usr/bin/env node
// Cross-platform task runner behind `just` and the root package.json scripts (BUILD-GUIDE 0.1).
// Zero dependencies. Usage:
//   node tools/dev/tasks.mjs lint [--skip=rust,python,web,prettier]
//   node tools/dev/tasks.mjs test [--skip=rust,python,web]
//   node tools/dev/tasks.mjs fmt
//   node tools/dev/tasks.mjs build-web <clinical|cosmos>     (also accepts THEME=cosmos)
// A missing optional tool is skipped with a warning locally; with CI=true it is an error.
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const WIN = process.platform === 'win32';
const CI = /^(1|true)$/i.test(process.env.CI || '');
const THEMES = ['clinical', 'cosmos'];

const [task, ...rest] = process.argv.slice(2);
const skip = new Set(
  rest
    .filter((a) => a.startsWith('--skip='))
    .flatMap((a) => a.slice(7).split(','))
    .filter(Boolean),
);
const positional = rest.filter((a) => !a.startsWith('--'));

const failures = [];

function run(label, cmd, args, opts = {}) {
  process.stdout.write(`\n==> ${label}\n$ ${cmd} ${args.join(' ')}\n`);
  const r = spawnSync(cmd, args, {
    cwd: ROOT,
    stdio: 'inherit',
    shell: WIN && /\.(cmd|bat)$|^(npx|pnpm)$/i.test(cmd),
    env: { ...process.env, ...(opts.env || {}) },
  });
  if (r.error || r.status !== 0) {
    failures.push(label);
    process.stdout.write(
      `!! ${label} failed (${r.error ? r.error.message : `exit ${r.status}`})\n`,
    );
  }
}

function missing(label, why) {
  const msg = `${label}: skipped (${why})`;
  if (CI) {
    failures.push(label);
    process.stdout.write(`!! ${msg}; not allowed with CI=true\n`);
  } else {
    process.stdout.write(`-- ${msg}\n`);
  }
}

function which(bin) {
  const r = spawnSync(WIN ? 'where' : 'which', [bin], { encoding: 'utf8' });
  return r.status === 0 ? r.stdout.split(/\r?\n/)[0].trim() : null;
}

function venvBin(name) {
  const p = WIN ? join(ROOT, '.venv', 'Scripts', `${name}.exe`) : join(ROOT, '.venv', 'bin', name);
  return existsSync(p) ? p : null;
}

function pnpm() {
  if (which('pnpm')) return ['pnpm', []];
  return ['npx', ['-y', 'pnpm@9.15.0']];
}

const hasNodeModules = () => existsSync(join(ROOT, 'node_modules'));
const node = process.execPath;

function nodeTests() {
  const globs = [
    'tools/copy-lint/test/*.test.mjs',
    'tools/repo-guard/test/*.test.mjs',
    'tools/hw-guard/test/*.test.mjs',
    'tools/ci-lint/test/*.test.mjs',
    'tools/sbom-props/test/*.test.mjs',
    'tools/licence-check/test/*.test.mjs',
    'tools/vuln-gate/test/*.test.mjs',
  ].filter((g) => existsSync(join(ROOT, g.split('/*')[0])));
  run('node tests (tools)', node, ['--test', ...globs]);
}

function lint() {
  // Repo policy first: tracked data files / secrets / non-dispatch workflow triggers.
  run('repo-guard', node, ['tools/repo-guard/cli.mjs']);
  // SEC-090/091: no stimulation/actuator API, inlet-only LSL, no device handles (non-negotiable).
  run('hw-guard', node, ['tools/hw-guard/cli.mjs']);
  // SEC-080/089: SHA-pinned actions, no pull_request_target, read-only token, frozen installs.
  run('ci-lint', node, ['tools/ci-lint/cli.mjs']);
  // SEC-084: licences of browser-shipped packages (needs node_modules).
  if (hasNodeModules()) run('licence-check', node, ['tools/licence-check/cli.mjs']);
  else missing('licence-check', 'node_modules missing; nfb-frontend runs pnpm install');
  if (existsSync(join(ROOT, 'packages/content'))) {
    run('copy-lint packages/content', node, ['tools/copy-lint/cli.mjs', 'packages/content']);
  } else {
    process.stdout.write('-- copy-lint: packages/content not present yet\n');
  }
  if (!skip.has('prettier')) {
    const bin = join(ROOT, 'node_modules', '.bin', WIN ? 'prettier.cmd' : 'prettier');
    if (existsSync(bin)) run('prettier --check', bin, ['--check', '.']);
    else missing('prettier', 'not installed; nfb-frontend runs pnpm install');
  }
  if (!skip.has('python')) {
    const ruff = venvBin('ruff') || which('ruff');
    if (ruff) {
      run('ruff check', ruff, ['check', '.']);
      run('ruff format --check', ruff, ['format', '--check', '.']);
    } else missing('ruff', 'no .venv; run `uv sync` (see docs/dev/toolchain.md)');
  }
  if (!skip.has('rust')) {
    if (which('cargo')) run('cargo fmt --check', 'cargo', ['fmt', '--all', '--', '--check']);
    else missing('cargo fmt', 'cargo not installed');
  }
}

function test() {
  nodeTests();
  if (!skip.has('web')) {
    if (hasNodeModules()) {
      const [cmd, pre] = pnpm();
      run('workspace tests (pnpm -r)', cmd, [
        ...pre,
        '-r',
        '--if-present',
        '--filter',
        '!@nf/copy-lint',
        '--filter',
        '!@nf/repo-guard',
        'test',
      ]);
    } else missing('workspace tests', 'node_modules missing; nfb-frontend runs pnpm install');
  }
  if (!skip.has('python')) {
    const py = venvBin('python');
    if (py) run('pytest', py, ['-m', 'pytest']);
    else missing('pytest', 'no .venv; run `uv sync`');
  }
  if (!skip.has('rust')) {
    if (which('cargo'))
      run('cargo test (debug)', 'cargo', ['test', '--workspace'], {
        env: { CARGO_BUILD_JOBS: process.env.CARGO_BUILD_JOBS || '1' },
      });
    else missing('cargo test', 'cargo not installed');
  }
}

function fmt() {
  const bin = join(ROOT, 'node_modules', '.bin', WIN ? 'prettier.cmd' : 'prettier');
  if (existsSync(bin)) run('prettier --write', bin, ['--write', '.']);
  else missing('prettier', 'not installed');
  const ruff = venvBin('ruff') || which('ruff');
  if (ruff) {
    run('ruff check --fix', ruff, ['check', '--fix', '.']);
    run('ruff format', ruff, ['format', '.']);
  } else missing('ruff', 'no .venv');
  if (which('cargo')) run('cargo fmt', 'cargo', ['fmt', '--all']);
}

function buildWeb() {
  const arg = positional[0] || process.env.THEME;
  const theme = arg && arg.startsWith('THEME=') ? arg.slice(6) : arg;
  if (!THEMES.includes(theme)) {
    process.stderr.write(`build-web: THEME must be one of ${THEMES.join(', ')} (got ${theme})\n`);
    process.exit(2);
  }
  const [cmd, pre] = pnpm();
  run(`build-web ${theme}`, cmd, [...pre, '--filter', '@nf/web', 'build'], {
    env: { THEME: theme },
  });
}

const tasks = { lint, test, fmt, 'build-web': buildWeb };
if (!tasks[task]) {
  process.stderr.write(
    `usage: node tools/dev/tasks.mjs <${Object.keys(tasks).join('|')}> [--skip=...]\n`,
  );
  process.exit(2);
}
tasks[task]();
if (failures.length) {
  process.stdout.write(`\nFAILED: ${failures.join(', ')}\n`);
  process.exit(1);
}
process.stdout.write(`\n${task}: ok\n`);
