#!/usr/bin/env node
// Verifies a figure manifest against the files on disk. Exit 1 on any SHA-256 mismatch.
// Usage: node packages/figures/scripts/verify.mjs <manifest.json> [repoRoot]
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadManifest, verifyManifest } from '../src/manifest.ts';

const [manifestArg, rootArg] = process.argv.slice(2);
if (!manifestArg) {
  console.error('usage: verify.mjs <manifest.json> [repoRoot]');
  process.exit(2);
}
const here = dirname(fileURLToPath(import.meta.url));
const manifestPath = resolve(manifestArg);
const repoRoot = resolve(rootArg ?? resolve(here, '../../..'));
try {
  const m = loadManifest(manifestPath);
  verifyManifest(m, repoRoot);
  console.error(`figures: ${m.figures.length} pinned files verified (${m.paper})`);
} catch (e) {
  console.error(e.message);
  process.exit(1);
}
