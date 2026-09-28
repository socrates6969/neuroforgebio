// Stand-in for loader.mjs when apps/web/src/assets/arena/pkg/ isn't checked in (the normal
// state -- it's a CI-built artifact, see tools/arena-core/README.md). astro.config.mjs aliases
// `virtual:arena-loader` to this file in that case, so the site build always succeeds and
// contains zero WebAssembly-compiling code: nothing here imports the wasm module or its glue.
export const AVAILABLE = false;

export async function initArena() {
  throw new Error('Decoder Arena evaluator is not built into this deployment.');
}

export function runMcRttEvaluation() {
  throw new Error('Decoder Arena evaluator is not built into this deployment.');
}
