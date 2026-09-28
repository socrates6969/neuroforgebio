#!/usr/bin/env node
// Usage (CI produces the inputs; this script does no network I/O):
//   node tools/vuln-gate/cli.mjs [--pnpm pnpm-audit.json] [--pip pip-audit.json] [--cargo cargo-audit.json]
//                                 --kev kev.json [--vex security/vex]
// Exit 0 pass, 1 blocking vulnerability (or invalid VEX), 2 usage/IO error.
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fromCargoAudit, fromPipAudit, fromPnpmAudit, gate, kevSet, validateVex } from './lib.mjs';

const args = process.argv.slice(2);
const arg = (f) => (args.indexOf(f) >= 0 ? args[args.indexOf(f) + 1] : null);
const load = (p) => {
  try {
    const t = readFileSync(p, 'utf8').trim();
    if (!t) throw new Error('empty file (did the audit tool fail?)');
    return JSON.parse(t);
  } catch (e) {
    process.stderr.write(`vuln-gate: cannot read ${p}: ${e.message}\n`);
    process.exit(2);
  }
};

const kevPath = arg('--kev');
if (!kevPath) {
  process.stderr.write(
    'vuln-gate: --kev <catalogue.json> is required (CISA KEV feed, downloaded in CI)\n',
  );
  process.exit(2);
}
const findings = [];
if (arg('--pnpm')) findings.push(...fromPnpmAudit(load(arg('--pnpm'))));
if (arg('--pip')) findings.push(...fromPipAudit(load(arg('--pip'))));
if (arg('--cargo')) findings.push(...fromCargoAudit(load(arg('--cargo'))));
const kev = kevSet(load(kevPath));
if (kev.size === 0) {
  process.stderr.write('vuln-gate: KEV catalogue is empty; refusing to pass without it\n');
  process.exit(2);
}

const vexDir = arg('--vex') || 'security/vex';
const vexDocs = [];
let bad = 0;
if (existsSync(vexDir))
  for (const f of readdirSync(vexDir)
    .filter((x) => x.endsWith('.json'))
    .sort()) {
    const doc = load(join(vexDir, f));
    const errs = validateVex(doc);
    for (const e of errs) process.stdout.write(`${join(vexDir, f)}: invalid VEX: ${e}\n`);
    if (errs.length) bad++;
    else vexDocs.push(doc);
  }

const r = gate(findings, kev, vexDocs);
const fmt = (f) =>
  `${f.ecosystem}:${f.package}@${f.version ?? '?'} ${f.id}${f.aliases.length ? ` (${f.aliases.join(', ')})` : ''}`;
for (const s of r.suppressed)
  process.stdout.write(`VEX ${s.status}: ${fmt(s.finding)} [${s.reason}]\n`);
for (const x of r.failures) process.stdout.write(`BLOCK: ${fmt(x.finding)} [${x.reason}]\n`);
process.stderr.write(
  `vuln-gate: ${findings.length} finding(s), ${r.failures.length} blocking, ${r.suppressed.length} covered by VEX, ${r.ignored} below the gate; KEV entries ${kev.size}\n`,
);
process.exit(r.failures.length || bad ? 1 : 0);
