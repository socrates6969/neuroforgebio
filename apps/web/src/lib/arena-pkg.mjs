// Shared "is the Decoder Arena wasm bundle checked in?" check, used by astro.config.mjs (to
// alias virtual:arena-loader to the real loader or a stub) and src/pages/arena/index.astro (to
// render the matching markup). apps/web/src/assets/arena/pkg/ is a CI-built artifact -- never
// committed here in the normal case, see tools/arena-core/README.md -- so this is almost always
// false during local/CI builds; that's expected, not an error.
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const PKG_DIR = fileURLToPath(new URL('../assets/arena/pkg/', import.meta.url));

export const ARENA_LOADER_REAL = fileURLToPath(
  new URL('../assets/arena/loader.mjs', import.meta.url),
);
export const ARENA_LOADER_STUB = fileURLToPath(
  new URL('../assets/arena/loader-stub.mjs', import.meta.url),
);

export function arenaPkgAvailable() {
  return existsSync(`${PKG_DIR}arena_core.js`) && existsSync(`${PKG_DIR}arena_core_bg.wasm`);
}
