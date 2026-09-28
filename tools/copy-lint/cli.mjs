#!/usr/bin/env node
// Usage: node tools/copy-lint/cli.mjs [--json] <files|dirs...>
// Exit codes: 0 clean, 1 banned term or unlabelled mock number found, 2 usage/parse error.
import { lintFiles } from './lib.mjs';

const args = process.argv.slice(2);
const json = args.includes('--json');
const paths = args.filter((a) => a !== '--json');

if (paths.length === 0 || args.includes('--help') || args.includes('-h')) {
  process.stderr.write(
    'usage: node tools/copy-lint/cli.mjs [--json] <files|dirs...>\n' +
      'Scans .json .md .mdx .html .htm .astro for banned copy terms (see tools/copy-lint/README.md).\n',
  );
  process.exit(paths.length === 0 ? 2 : 0);
}

let out;
try {
  out = lintFiles(paths);
} catch (e) {
  process.stderr.write(`copy-lint: ${e.message}\n`);
  process.exit(2);
}
const { results, errors } = out;

if (json) {
  process.stdout.write(JSON.stringify({ results, errors }, null, 2) + '\n');
} else {
  for (const r of results) process.stdout.write(`${r.file}:${r.line}: ${r.term}\n`);
  for (const e of errors) process.stderr.write(`${e.file}: parse error: ${e.error}\n`);
  if (results.length === 0 && errors.length === 0) process.stderr.write('copy-lint: clean\n');
}
process.exit(results.length > 0 ? 1 : errors.length > 0 ? 2 : 0);
