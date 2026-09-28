#!/usr/bin/env node
// `pnpm --filter @nf/console test` (and `node tools/dev/tasks.mjs test` via `pnpm -r test`):
// 1. tsc --noEmit, then vitest unit/component tests (jsdom, single fork)
// 2. vite build + postbuild (headers, inline check)
// 3. node:test dist + drift tests in test/*.test.mjs
// Playwright e2e + axe are CI-only (e2e/, .github/workflows/console-e2e.yml).
import { spawnSync } from 'node:child_process';
import { readdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const CONSOLE = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(join(CONSOLE, 'package.json'));
const bin = (pkg, rel) => join(dirname(require.resolve(`${pkg}/package.json`)), rel);

function step(label, args) {
  process.stdout.write(`\n-- @nf/console: ${label}\n`);
  const r = spawnSync(process.execPath, args, { cwd: CONSOLE, stdio: 'inherit' });
  if (r.status !== 0) {
    process.stdout.write(`@nf/console: ${label} failed\n`);
    process.exit(r.status ?? 1);
  }
}

step('typecheck (tsc)', [bin('typescript', 'bin/tsc'), '--noEmit', '-p', 'tsconfig.json']);
step('unit tests (vitest)', [bin('vitest', 'vitest.mjs'), 'run']);
step('build (vite)', [bin('vite', 'bin/vite.js'), 'build', '--logLevel', 'warn']);
step('postbuild', [join(CONSOLE, 'scripts', 'postbuild.mjs')]);
const tests = readdirSync(join(CONSOLE, 'test'))
  .filter((f) => f.endsWith('.test.mjs'))
  .map((f) => join(CONSOLE, 'test', f));
step('dist + drift tests (node:test)', ['--test', ...tests]);
