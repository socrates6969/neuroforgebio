#!/usr/bin/env node
// Regenerator for e2e/homepage-pin.spec.ts's text-snapshot baseline (home-content.txt, home-meta.txt,
// both themes). Same spirit as scripts/home-baseline.mjs's guard, but with two distinct write modes
// (lead's correction, 2026-09-27): --owner-approved means the OWNER approved THIS write, and covers a
// later regeneration only; it is not standing permission to bootstrap a pin that doesn't exist yet.
// The lead's one-time sign-off covered only the first creation, so that path is a separate flag,
// --init, which refuses the moment any baseline file already exists (from then on, a change needs a
// fresh --owner-approved, i.e. an actual owner say-so for that specific write, not a script flag
// anyone can pass). Both modes require the working tree to have no homepage-affecting diff against
// origin/main (the source list test/homepage.test.mjs already pins) -- this baseline must always come
// from a build of origin/main, never a branch. Without either flag: read-only, and any snapshot file
// Playwright wrote as a side effect of a missing baseline (it always auto-writes one) is deleted
// again, so a bare run never leaves an unapproved write behind.
//
// Usage:
//   node scripts/homepage-pin-baseline.mjs --init            (only when no pin file exists yet)
//   node scripts/homepage-pin-baseline.mjs --owner-approved   (only to change an existing pin, with
//                                                               the owner's specific sign-off for it)
//   node scripts/homepage-pin-baseline.mjs                    (read-only report)
// Build both themes first, from a checkout that matches origin/main. Record origin/main's sha in the
// commit message either way.
import { existsSync, readdirSync, rmSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const REPO = resolve(WEB, '../..');
// Matches playwright.config.ts's snapshotPathTemplate: {testDir}/__snapshots__/{projectName}/
// {platform}/{testFilePath}/{arg}{ext}. process.platform is exactly Playwright's {platform} value.
const SNAP_DIRS = ['clinical', 'cosmos'].map((t) =>
  join(WEB, 'e2e/__snapshots__', t, process.platform, 'homepage-pin.spec.ts'),
);

// Mirrors test/homepage.test.mjs's HOME_SOURCES: everything that renders on /.
const HOME_SOURCES = [
  'apps/web/src/pages/index.astro',
  'apps/web/src/layouts/Base.astro',
  'packages/content/content/home.json',
  'packages/content/content/site.json',
  'packages/ui/src/components',
  'packages/themes/clinical/slots',
  'packages/themes/cosmos/slots',
];

function git(...args) {
  return spawnSync('git', ['-C', REPO, ...args], { encoding: 'utf8' });
}

function existingFiles() {
  const out = new Set();
  for (const dir of SNAP_DIRS)
    if (existsSync(dir)) for (const f of readdirSync(dir)) out.add(join(dir, f));
  return out;
}

const init = process.argv.includes('--init');
const approved = process.argv.includes('--owner-approved');
if (init && approved) {
  console.error('homepage-pin-baseline: pass --init OR --owner-approved, not both');
  process.exit(2);
}
const write = init || approved;
const before = existingFiles();

if (write) {
  if (init && before.size > 0) {
    console.error(
      `homepage-pin-baseline: --init refused, a baseline already exists (${before.size} file(s)).\n` +
        "A change to an existing pin needs --owner-approved, with the owner's specific sign-off for that write.",
    );
    process.exit(1);
  }
  if (approved && before.size === 0) {
    console.error(
      'homepage-pin-baseline: --owner-approved refused, no baseline exists yet -- use --init for the first one.',
    );
    process.exit(1);
  }
  const mainRef = ['origin/main', 'main'].find(
    (r) => git('rev-parse', '--verify', '--quiet', r).status === 0,
  );
  if (!mainRef) {
    console.error(
      'homepage-pin-baseline: no origin/main or main ref found; cannot verify freshness',
    );
    process.exit(2);
  }
  const diff = git('diff', '--name-only', mainRef, '--', ...HOME_SOURCES);
  const changed = diff.stdout.split('\n').filter(Boolean);
  if (changed.length) {
    console.error(
      `homepage-pin-baseline: working tree differs from ${mainRef} in homepage sources -- refusing.\n` +
        `This baseline must come from a build of ${mainRef}, not a branch (lead ruling 2026-09-27).\n` +
        `Changed: ${changed.join(', ')}`,
    );
    process.exit(1);
  }
  const sha = git('rev-parse', mainRef).stdout.trim();
  console.log(
    `homepage-pin-baseline: working tree matches ${mainRef} (${sha}) in homepage sources.`,
  );
}

const args = ['exec', 'playwright', 'test', 'e2e/homepage-pin.spec.ts'];
if (write) args.push('--update-snapshots');
const r = spawnSync('pnpm', args, {
  cwd: WEB,
  stdio: 'inherit',
  shell: process.platform === 'win32',
});

if (!write) {
  // Playwright auto-writes a missing baseline even without --update-snapshots; without --init or
  // --owner-approved, that write must not survive. Anything that didn't exist before this run gets
  // removed again.
  const after = existingFiles();
  let removed = 0;
  for (const f of after) {
    if (!before.has(f)) {
      rmSync(f);
      removed++;
    }
  }
  for (const dir of SNAP_DIRS)
    if (existsSync(dir) && readdirSync(dir).length === 0) rmSync(dir, { recursive: true });
  if (removed) {
    console.log(
      `\nhomepage-pin-baseline: removed ${removed} snapshot file(s) Playwright wrote without approval.\n` +
        "Not written. Re-run with --init (no baseline exists yet) or --owner-approved (with the owner's sign-off).",
    );
    process.exit(1);
  }
}

process.exit(r.status ?? 1);
