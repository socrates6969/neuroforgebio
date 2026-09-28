#!/usr/bin/env node
// Usage: node tools/repo-guard/cli.mjs [--root <repo>] [--json]
// Exit 0 clean, 1 policy violation, 2 error (e.g. not a git checkout).
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { guardRepo } from './lib.mjs';

const args = process.argv.slice(2);
const json = args.includes('--json');
const ri = args.indexOf('--root');
const root =
  ri >= 0 ? resolve(args[ri + 1]) : resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');

let problems;
try {
  problems = guardRepo(root);
} catch (e) {
  process.stderr.write(`repo-guard: ${e.message}\n`);
  process.exit(2);
}
if (json) process.stdout.write(JSON.stringify(problems, null, 2) + '\n');
else {
  for (const p of problems)
    process.stdout.write(`${p.file}${p.line ? `:${p.line}` : ''}: ${p.rule}: ${p.detail}\n`);
  process.stderr.write(
    problems.length ? `repo-guard: ${problems.length} problem(s)\n` : 'repo-guard: clean\n',
  );
}
process.exit(problems.length ? 1 : 0);
