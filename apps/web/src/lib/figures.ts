// Build-time access to the figure manifests. verifyAll() THROWS on any SHA-256 mismatch, which
// fails `astro build` (BLUEPRINT §2.5; BUILD-GUIDE 1.7 acceptance test).
import { basename, join } from 'node:path';
import { loadManifest, verifyManifest, type FigureManifest } from '@nf/figures/manifest.ts';

// Injected by astro.config.mjs (import.meta.url is unreliable after bundling).
export const REPO_ROOT = __NF_REPO_ROOT__;
const MANIFEST_DIR = join(REPO_ROOT, 'packages/figures/manifests');

const cache = new Map<string, FigureManifest>();

/** Loads and verifies the manifest of a paper; null when the paper has no figures. */
export function manifestFor(slug: string): FigureManifest | null {
  if (cache.has(slug)) return cache.get(slug) ?? null;
  let m: FigureManifest;
  try {
    m = loadManifest(join(MANIFEST_DIR, `${slug}.figures.json`));
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === 'ENOENT') return null;
    throw e;
  }
  verifyManifest(m, REPO_ROOT);
  cache.set(slug, m);
  return m;
}

/** Public URL of a pinned static SVG (served by src/pages/research/files/[file].ts). */
export const staticSvgUrl = (repoPath: string) => `/research/files/${basename(repoPath)}`;
