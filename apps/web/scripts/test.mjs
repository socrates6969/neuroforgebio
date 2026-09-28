#!/usr/bin/env node
// Runs the local dist tests (test/*.test.mjs). They need both builds; outside CI a missing dist
// is reported and skipped (so a root `pnpm test` before `pnpm build:web` does not fail), in CI it fails.
import { existsSync, readdirSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const web = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const built = ['clinical', 'cosmos'].every((t) => existsSync(join(web, 'dist', t, 'index.html')));
if (!built && !process.env.CI) {
  console.error(
    '@nf/web: dist/clinical or dist/cosmos missing; run "pnpm build:web" first. Dist tests SKIPPED.',
  );
  process.exit(0);
}
const tests = readdirSync(join(web, 'test'))
  .filter((f) => f.endsWith('.test.mjs'))
  .map((f) => join(web, 'test', f));
const r = spawnSync(process.execPath, ['--test', ...tests], { stdio: 'inherit' });
process.exit(r.status ?? 1);
