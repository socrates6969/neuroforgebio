#!/usr/bin/env node
// Re-pins a figure manifest: recomputes SHA-256 (text files CRLF->LF normalised, see src/manifest.ts) of every result/SVG/script file and the last git
// commit that touched each script. Run it ONLY after the research team has changed a result on
// purpose; the build fails on any unpinned change.
// Usage: node packages/figures/scripts/pin.mjs <manifest.json> [repoRoot]
import { sha256File } from '../src/manifest.ts';
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const [manifestPath, rootArg] = process.argv.slice(2);
if (!manifestPath) {
  console.error('usage: pin.mjs <manifest.json> [repoRoot]');
  process.exit(2);
}
const repoRoot = resolve(rootArg ?? resolve(dirname(fileURLToPath(import.meta.url)), '../../..'));
const sha = (p) => sha256File(resolve(repoRoot, p));
const m = JSON.parse(readFileSync(manifestPath, 'utf8'));
for (const f of m.figures) {
  f.result.sha256 = sha(f.result.path);
  if (f.staticSvg) f.staticSvg.sha256 = sha(f.staticSvg.path);
  f.script.sha256 = sha(f.script.path);
  f.script.commit =
    execFileSync('git', ['-C', repoRoot, 'log', '-1', '--format=%H', '--', f.script.path], {
      encoding: 'utf8',
    }).trim() || 'uncommitted';
}
writeFileSync(manifestPath, JSON.stringify(m, null, 2) + '\n');
console.log(`pinned ${m.figures.length} figures in ${manifestPath}`);
