/// <reference types="astro/client" />
declare const __NF_THEME__: 'clinical' | 'cosmos';
declare const __NF_CANONICAL_ORIGIN__: string;
declare const __NF_SITE_STAGE__: 'preview' | 'launch' | 'public';
declare const __NF_REPO_ROOT__: string;

// Decoder Arena (nfb-arena): astro.config.mjs aliases this specifier to either
// src/assets/arena/loader.mjs (real, wasm-backed) or loader-stub.mjs (zero-wasm), chosen by
// apps/web/src/lib/arena-pkg.mjs. Both export exactly this shape -- see loader.mjs's doc comment.
declare module 'virtual:arena-loader' {
  export const AVAILABLE: boolean;
  export function initArena(): Promise<void>;
  export function runMcRttEvaluation(
    assetJson: string,
    nUnits: number,
    noiseLevelIndex: number,
    choiceJson: string,
    seed: number,
  ): string;
}
