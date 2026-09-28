// Real Decoder Arena wasm loader. Only ever bundled when apps/web/src/assets/arena/pkg/ (a
// CI-built artifact, never committed -- tools/arena-core/README.md) actually exists:
// astro.config.mjs aliases `virtual:arena-loader` to this file, or to loader-stub.mjs, based on
// that check (apps/web/src/lib/arena-pkg.mjs), so a build with no pkg/ never even parses this
// file's imports and contains zero WebAssembly-compiling code (nfb-security condition 5/checklist
// item 1). Both imports below are ordinary Vite imports -- no @vite-ignore -- so Vite
// content-hashes the glue and the .wasm into dist's /_assets/ like any other asset.
import init, { run_mc_rtt_evaluation } from './pkg/arena_core.js';
import wasmUrl from './pkg/arena_core_bg.wasm?url';

export const AVAILABLE = true;

export async function initArena() {
  await init({ module_or_path: wasmUrl });
}

export const runMcRttEvaluation = run_mc_rtt_evaluation;
