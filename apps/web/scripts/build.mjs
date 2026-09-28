#!/usr/bin/env node
// Web build: copy-lint content -> verify figure manifests -> per theme: astro build -> postbuild
// (security.txt, SEC-150a inline check, _headers) -> copy-lint dist.
// Env: SITE_STAGE=preview|launch|public (HSTS stage; launch and public fail on placeholders),
//      SITE_BUILD_DATE=YYYY-MM-DD,
//      SITE_HOST=netlify|cloudflare (_headers path layout, host-headers.mjs; default cloudflare, which is
//      only the build default: no host is chosen and nothing is deployed).
// Usage: node scripts/build.mjs [clinical|cosmos ...]   (default: $THEME if set, else both in turn)
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { readdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const webDir = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repoRoot = resolve(webDir, '../..');
const THEMES = ['clinical', 'cosmos'];
// explicit args win; else THEME env (tools/dev/tasks.mjs build-web <theme>); else both
const themes = process.argv.slice(2).length
  ? process.argv.slice(2)
  : process.env.THEME
    ? [process.env.THEME]
    : THEMES;
for (const t of themes)
  if (!THEMES.includes(t)) {
    console.error(`unknown theme ${t}`);
    process.exit(2);
  }

const require = createRequire(join(webDir, 'package.json'));
const astroBin = join(dirname(require.resolve('astro/package.json')), 'astro.js');

function run(label, args, env = {}) {
  console.error(`\n[web build] ${label}`);
  const r = spawnSync(process.execPath, args, {
    cwd: webDir,
    stdio: 'inherit',
    env: { ...process.env, ...env },
  });
  if (r.status !== 0) {
    console.error(`[web build] FAILED: ${label}`);
    process.exit(r.status ?? 1);
  }
}

// One build date for both themes, so security.txt is identical across builds (except Canonical).
process.env.SITE_BUILD_DATE ??= new Date().toISOString().slice(0, 10);

const copyLint = join(repoRoot, 'tools/copy-lint/cli.mjs');
run('copy-lint packages/content', [copyLint, join(repoRoot, 'packages/content')]);

const manifests = join(repoRoot, 'packages/figures/manifests');
for (const f of readdirSync(manifests).filter((n) => n.endsWith('.figures.json'))) {
  run(`verify figure manifest ${f}`, [
    join(repoRoot, 'packages/figures/scripts/verify.mjs'),
    join(manifests, f),
    repoRoot,
  ]);
}

for (const theme of themes) {
  run(`astro build THEME=${theme}`, [astroBin, 'build'], {
    THEME: theme,
    ASTRO_TELEMETRY_DISABLED: '1',
  });
  run(`postbuild dist/${theme} (security.txt, inline check, headers)`, [
    join(webDir, 'scripts/postbuild.mjs'),
    theme,
  ]);
  run(`copy-lint dist/${theme}`, [copyLint, join(webDir, 'dist', theme)]);
}
console.error(`\n[web build] done: ${themes.map((t) => `apps/web/dist/${t}`).join(', ')}`);
