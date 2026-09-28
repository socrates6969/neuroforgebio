#!/usr/bin/env node
// Usage: node tools/licence-check/cli.mjs [--root <repo>] [--policy security/licences.json]
// Needs an installed node_modules (pnpm install --frozen-lockfile). Exit 0 ok, 1 violation, 2 error.
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { checkTree } from './lib.mjs';

const args = process.argv.slice(2);
const arg = (f) => (args.indexOf(f) >= 0 ? args[args.indexOf(f) + 1] : null);
const root = resolve(arg('--root') || join(dirname(fileURLToPath(import.meta.url)), '..', '..'));
const policyPath = resolve(arg('--policy') || join(root, 'security', 'licences.json'));

if (!existsSync(join(root, 'node_modules'))) {
  process.stderr.write(
    'licence-check: node_modules missing; run `pnpm install --frozen-lockfile` first\n',
  );
  process.exit(2);
}
let result;
try {
  result = checkTree(root, JSON.parse(readFileSync(policyPath, 'utf8')));
} catch (e) {
  process.stderr.write(`licence-check: ${e.message}\n`);
  process.exit(2);
}
for (const p of result.problems)
  process.stdout.write(`${p.pkg}: ${p.detail}${p.licence ? ` (${p.licence})` : ''}  [${p.path}]\n`);
process.stderr.write(
  result.problems.length
    ? `licence-check: ${result.problems.length} problem(s) in ${result.checked} browser-shipped package(s); see docs/security/licences.md\n`
    : `licence-check: ${result.checked} browser-shipped package(s) ok\n`,
);
process.exit(result.problems.length ? 1 : 0);
