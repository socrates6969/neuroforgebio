// Build-time theme resolution (BLUEPRINT §2.3, approach A).
// THEME=clinical|cosmos selects ONE theme directory through the `@theme` alias, so the other
// theme's slots (and three.js) never enter the module graph. Output: apps/web/dist/<THEME>.
import { defineConfig } from 'astro/config';
import { fileURLToPath } from 'node:url';
import brand from '@nf/content/brand.json' with { type: 'json' };
import { ARENA_LOADER_REAL, ARENA_LOADER_STUB, arenaPkgAvailable } from './src/lib/arena-pkg.mjs';
import { resolveStage } from './stage.mjs';

const THEMES = ['clinical', 'cosmos'];
const THEME = process.env.THEME ?? 'clinical';
if (!THEMES.includes(THEME))
  throw new Error(`THEME must be one of ${THEMES.join('|')}, got "${THEME}"`);

const repoRoot = fileURLToPath(new URL('../../', import.meta.url));
const themeDir = fileURLToPath(new URL(`../../packages/themes/${THEME}`, import.meta.url));
// Decoder Arena (nfb-arena, EXC-150-1/ADR 0014): apps/web/src/assets/arena/pkg/ is a CI-built
// artifact, almost never present locally. `virtual:arena-loader` resolves to the real loader
// only when it is, otherwise to a stub with zero WebAssembly-compiling code -- so a missing
// bundle degrades only /arena (rendered "decoder unavailable"; src/pages/arena/index.astro),
// never fails the whole site build.
const arenaLoaderTarget = arenaPkgAvailable() ? ARENA_LOADER_REAL : ARENA_LOADER_STUB;
// Canonical host = the clinical deployment (DECISIONS.md D3). Placeholder while brand.domainIsPlaceholder.
const canonicalOrigin = `https://${brand.domain}`;

export default defineConfig({
  site: canonicalOrigin,
  // NF_WEB_OUT_DIR: only for the 5.6 rebuild test (a temp RuleSet copy must not clobber dist/).
  outDir: process.env.NF_WEB_OUT_DIR || `./dist/${THEME}`,
  cacheDir: `./node_modules/.astro-cache/${THEME}`,
  trailingSlash: 'ignore',
  // SEC-150a: no inline <style> (stylesheets are always files); scripts are bundled modules.
  build: { format: 'directory', assets: '_assets', inlineStylesheets: 'never' },
  devToolbar: { enabled: false },
  vite: {
    resolve: { alias: { '@theme': themeDir, 'virtual:arena-loader': arenaLoaderTarget } },
    define: {
      __NF_THEME__: JSON.stringify(THEME),
      __NF_CANONICAL_ORIGIN__: JSON.stringify(canonicalOrigin),
      // APP-L8: preview builds (the default) are noindex (indexing.mjs)
      __NF_SITE_STAGE__: JSON.stringify(resolveStage()),
      __NF_REPO_ROOT__: JSON.stringify(repoRoot),
    },
    // Never inline scripts or fonts: keeps a strict CSP (script-src 'self') possible.
    build: { assetsInlineLimit: 0 },
  },
});
