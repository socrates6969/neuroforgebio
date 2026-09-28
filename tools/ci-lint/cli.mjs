#!/usr/bin/env node
// Usage: node tools/ci-lint/cli.mjs [workflow files or dirs...]   (default: .github/workflows)
// Exit 0 clean, 1 policy violation, 2 error. Rules: see lib.mjs (SEC-080, SEC-089).
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { lintWorkflow } from './lib.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const args = process.argv.slice(2);
const targets = args.length ? args.map((a) => resolve(a)) : [join(root, '.github', 'workflows')];

const files = [];
try {
  for (const t of targets) {
    if (statSync(t).isDirectory()) {
      for (const f of readdirSync(t)) if (/\.ya?ml$/.test(f)) files.push(join(t, f));
    } else files.push(t);
  }
} catch (e) {
  process.stderr.write(`ci-lint: ${e.message}\n`);
  process.exit(2);
}

let count = 0;
for (const f of files.sort()) {
  for (const p of lintWorkflow(readFileSync(f, 'utf8'), { file: f })) {
    count++;
    process.stdout.write(
      `${relative(root, f).replace(/\\/g, '/')}:${p.line}: ${p.rule}: ${p.detail}\n`,
    );
  }
}
process.stderr.write(
  count ? `ci-lint: ${count} problem(s)\n` : `ci-lint: ${files.length} workflow(s) clean\n`,
);
process.exit(count ? 1 : 0);
