#!/usr/bin/env node
// Usage: node tools/hw-guard/cli.mjs [--root <repo>] [--json]
//        node tools/hw-guard/cli.mjs --surface <doc.json> [--surface <doc2.json>] [--json]
// Scans proto/ openapi/ core/ bindings/ sdk/ tools/arena-core/ (SEC-090, SEC-091), services/ (SEC-091 in
// full; SEC-090 over route/operation/action names; see lib.mjs), apps/*/src + packages/*/src (SEC-091
// web/device rules only) and every Cargo.toml (shipping crates must be scanned). `--surface` instead scans the external surface
// of a running service: a JSON OpenAPI document (+ webhooks, + x-nf-grpc names) generated from the
// app (M2-REVIEW decision; services/platform tests call this). Exit 0 clean, 1 violation, 2 error.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  SCAN_DIRS,
  WEB_ROOTS,
  isSkippedDir,
  scanWebText,
  shouldScanWeb,
  uncoveredShippingCrates,
  uncoveredShippingManifests,
  SERVICE_DIRS,
  scanServiceText,
  scanSurface,
  scanText,
  shouldScan,
  shouldScanService,
} from './lib.mjs';

const args = process.argv.slice(2);
const json = args.includes('--json');
const surfaces = args.flatMap((a, i) => (a === '--surface' ? [args[i + 1]] : []));
if (surfaces.length) {
  const hits = [];
  try {
    for (const f of surfaces) {
      if (!f) throw new Error('--surface needs a file');
      for (const h of scanSurface(JSON.parse(readFileSync(f, 'utf8'))))
        hits.push({ file: f, ...h });
    }
  } catch (e) {
    process.stderr.write(`hw-guard: ${e.message}\n`);
    process.exit(2);
  }
  if (json) process.stdout.write(JSON.stringify(hits, null, 2) + '\n');
  else
    for (const h of hits) process.stdout.write(`${h.file}: ${h.where}: ${h.rule}: ${h.detail}\n`);
  process.stderr.write(
    hits.length
      ? `hw-guard: ${hits.length} surface problem(s); device -> SDK -> platform only\n`
      : `hw-guard: surface of ${surfaces.length} document(s) clean\n`,
  );
  process.exit(hits.length ? 1 : 0);
}
const ri = args.indexOf('--root');
const root =
  ri >= 0 ? resolve(args[ri + 1]) : resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');

function* walk(dir) {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) yield* walk(p);
    else if (e.isFile()) yield p;
  }
}

// Repo-wide walk that prunes build output, dependencies and VCS directories (for Cargo.toml
// discovery and the JS/TS pass, which would otherwise descend into node_modules or target).
function* prunedWalk(dir) {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    if (e.isDirectory()) {
      if (!isSkippedDir(e.name)) yield* prunedWalk(join(dir, e.name));
    } else if (e.isFile()) yield join(dir, e.name);
  }
}

const problems = [];
let scanned = 0;
const passes = [
  [SCAN_DIRS, shouldScan, scanText],
  [SERVICE_DIRS, shouldScanService, scanServiceText],
];
try {
  for (const [dirs, want, scan] of passes)
    for (const d of dirs) {
      const abs = join(root, d);
      if (!existsSync(abs)) continue;
      for (const f of walk(abs)) {
        const rel = relative(root, f).replace(/\\/g, '/');
        if (!want(rel) || statSync(f).size > 4 << 20) continue;
        scanned++;
        for (const h of scan(rel, readFileSync(f, 'utf8'))) problems.push({ file: rel, ...h });
      }
    }
  // Coverage guard: a shipping workspace crate outside SCAN_DIRS is itself a failure.
  const readRel = (rel) => {
    const abs = join(root, rel);
    return existsSync(abs) ? readFileSync(abs, 'utf8') : null;
  };
  // Root workspace members, then every Cargo.toml in the repo (excluded members, nested workspaces).
  const manifests = [...prunedWalk(root)]
    .map((f) => relative(root, f).replace(/\\/g, '/'))
    .filter((rel) => rel === 'Cargo.toml' || rel.endsWith('/Cargo.toml'));
  const seen = new Set();
  for (const u of [
    ...uncoveredShippingCrates(readRel),
    ...uncoveredShippingManifests(readRel, manifests),
  ]) {
    const key = `${u.member}|${u.reason}`;
    if (seen.has(key)) continue;
    seen.add(key);
    problems.push({
      file: `${u.member}/Cargo.toml`,
      line: 1,
      rule: 'SEC-091',
      detail: `scan-coverage: ${u.reason}`,
    });
  }
  // JS/TS packages: SEC-091 device rules only (apps/*/src, packages/*/src, their package.json).
  for (const d of WEB_ROOTS) {
    const abs = join(root, d);
    if (!existsSync(abs)) continue;
    for (const f of prunedWalk(abs)) {
      const rel = relative(root, f).replace(/\\/g, '/');
      if (!shouldScanWeb(rel) || statSync(f).size > 4 << 20) continue;
      scanned++;
      for (const h of scanWebText(rel, readFileSync(f, 'utf8'))) problems.push({ file: rel, ...h });
    }
  }
} catch (e) {
  process.stderr.write(`hw-guard: ${e.message}\n`);
  process.exit(2);
}
if (json) process.stdout.write(JSON.stringify(problems, null, 2) + '\n');
else
  for (const p of problems) process.stdout.write(`${p.file}:${p.line}: ${p.rule}: ${p.detail}\n`);
process.stderr.write(
  problems.length
    ? `hw-guard: ${problems.length} problem(s); device -> SDK -> platform only (SECURITY-REQUIREMENTS §G)\n`
    : `hw-guard: ${scanned} file(s) clean\n`,
);
process.exit(problems.length ? 1 : 0);
