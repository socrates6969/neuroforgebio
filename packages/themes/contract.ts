// Theme contract (CONTRACTS.md §3.1, §3.2; BLUEPRINT §2.2).
// Components use ONLY these custom properties. Both tokens.css files must define every token in
// THEME_TOKENS and nothing else (packages/themes/test/contract.test.mjs parses this file).

/** The §3.1 semantic tokens every theme defines. */
export const REQUIRED_TOKENS = [
  '--color-bg',
  '--color-surface',
  '--color-ink',
  '--color-muted',
  '--color-accent',
  '--color-accent-ink',
  '--color-secondary',
  '--color-line',
  '--emphasis-paint',
  '--font-display',
  '--font-body',
  '--font-mono',
  '--radius-card',
  '--motion-duration',
  '--motion-ease',
  '--elevation-card',
] as const;

/**
 * Extra tokens requested by packages/ui (nfb-frontend). Both themes define them; ui keeps a
 * fallback for each, so a future theme may omit them only if the contract test is relaxed.
 */
export const EXTENDED_TOKENS = [
  '--color-on-accent',
  '--color-focus',
  '--color-surface-2',
  '--color-status-designed-bg',
  '--color-status-designed-ink',
  '--color-status-planned-bg',
  '--color-status-planned-ink',
  '--color-status-roadmap-bg',
  '--color-status-roadmap-ink',
] as const;

export const THEME_TOKENS = [...REQUIRED_TOKENS, ...EXTENDED_TOKENS] as const;
export type ThemeToken = (typeof THEME_TOKENS)[number];

export const THEMES = ['clinical', 'cosmos'] as const;
export type ThemeName = (typeof THEMES)[number];

export const SLOT_NAMES = ['HeroVisual', 'BrandMark', 'SectionOrnament', 'SecurityVisual'] as const;
export type SlotName = (typeof SLOT_NAMES)[number];

/** Props of the four presentational slots. All text comes from packages/content. */
export interface SlotContract {
  /** role="img" wrapper labelled by `label`; canvas/WebGL inside is aria-hidden. */
  HeroVisual: { label: string; caption?: string };
  /** Visible brand name next to a decorative mark. */
  BrandMark: { name: string };
  /** Decorative, inline, aria-hidden. */
  SectionOrnament: { index?: number };
  /** role="img" illustration labelled by `label`. */
  SecurityVisual: { label: string };
}
