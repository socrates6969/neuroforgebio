#!/usr/bin/env node
// Usage:
//   node tools/sbom-props/cli.mjs add <sbom.cdx.json> [--overrides security/support-levels.json]
//        [--include security/sbom-ci-images.json] [-o out.json]
//   node tools/sbom-props/cli.mjs check <sbom.cdx.json>...
// `add` first appends the components listed in --include (e.g. CI container images the generator
// cannot see), fills the properties, writes in place unless -o is given, then runs `check`.
// Exit 0 ok, 1 invalid, 2 usage/IO error.
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { addProps, checkBom, includeComponents } from './lib.mjs';

const [cmd, ...rest] = process.argv.slice(2);
const opt = (flag) => {
  const i = rest.indexOf(flag);
  if (i < 0) return null;
  const v = rest[i + 1];
  rest.splice(i, 2);
  return v;
};

function load(p) {
  try {
    return JSON.parse(readFileSync(p, 'utf8'));
  } catch (e) {
    process.stderr.write(`sbom-props: cannot read ${p}: ${e.message}\n`);
    process.exit(2);
  }
}

function report(file, bom) {
  const problems = checkBom(bom);
  for (const p of problems) process.stdout.write(`${file}: ${p}\n`);
  return problems.length;
}

if (cmd === 'add') {
  const out = opt('-o');
  const ovPath = opt('--overrides');
  const incPath = opt('--include');
  const [file] = rest;
  if (!file) usage();
  const bom = load(file);
  if (incPath) {
    const n = includeComponents(bom, load(incPath).components);
    process.stderr.write(`sbom-props: included ${n} component(s) from ${incPath}\n`);
  }
  const overrides = ovPath && existsSync(ovPath) ? load(ovPath).components || {} : null;
  const touched = addProps(bom, overrides);
  writeFileSync(out || file, JSON.stringify(bom, null, 2) + '\n');
  process.stderr.write(`sbom-props: added properties to ${touched} component(s)\n`);
  process.exit(report(out || file, bom) ? 1 : 0);
} else if (cmd === 'check') {
  if (!rest.length) usage();
  let bad = 0;
  for (const f of rest) bad += report(f, load(f));
  process.stderr.write(
    bad ? `sbom-props: ${bad} problem(s)\n` : `sbom-props: ${rest.length} SBOM(s) valid\n`,
  );
  process.exit(bad ? 1 : 0);
} else usage();

function usage() {
  process.stderr.write(
    'usage: sbom-props add <sbom> [--overrides f] [--include f] [-o out] | check <sbom>...\n',
  );
  process.exit(2);
}
