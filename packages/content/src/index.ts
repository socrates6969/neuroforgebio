// @nf/content: typed, validated site copy with brand placeholders substituted.
// Synchronous; no fs access. JSON is imported with import attributes (Node 22 + Vite).
import brandJson from '../brand.json' with { type: 'json' };
import siteJson from '../content/site.json' with { type: 'json' };
import homeJson from '../content/home.json' with { type: 'json' };
import platformJson from '../content/pages/platform.json' with { type: 'json' };
import governanceJson from '../content/pages/governance.json' with { type: 'json' };
import sdksJson from '../content/pages/sdks.json' with { type: 'json' };
import pricingJson from '../content/pages/pricing.json' with { type: 'json' };
import platformNo from '../content/pages/platform.no.json' with { type: 'json' };
import governanceNo from '../content/pages/governance.no.json' with { type: 'json' };
import sdksNo from '../content/pages/sdks.no.json' with { type: 'json' };
import pricingNo from '../content/pages/pricing.no.json' with { type: 'json' };
import lawTrackerJson from '../content/pages/law-tracker.json' with { type: 'json' };
import investorsJson from '../content/pages/investors.json' with { type: 'json' };
import researchJson from '../content/pages/research.json' with { type: 'json' };
import playgroundJson from '../content/pages/playground.json' with { type: 'json' };
import interfaceJson from '../content/pages/interface.json' with { type: 'json' };
import uiEn from '../content/ui.en.json' with { type: 'json' };
import uiNo from '../content/ui.no.json' with { type: 'json' };
import securityEn from '../content/security.en.json' with { type: 'json' };
import securityNo from '../content/security.no.json' with { type: 'json' };
import privacyEn from '../content/legal/privacy.en.json' with { type: 'json' };
import privacyNo from '../content/legal/privacy.no.json' with { type: 'json' };
import termsEn from '../content/legal/terms.en.json' with { type: 'json' };
import termsNo from '../content/legal/terms.no.json' with { type: 'json' };
import cookiesEn from '../content/legal/cookies.en.json' with { type: 'json' };
import cookiesNo from '../content/legal/cookies.no.json' with { type: 'json' };
import companyEn from '../content/legal/company.en.json' with { type: 'json' };
import companyNo from '../content/legal/company.no.json' with { type: 'json' };
import somatosensoryJson from '../content/research/somatosensory-closed-loop.json' with { type: 'json' };

import type { Brand, Content, InnerPageKey, Locale, LocaleContent } from './types.ts';
import {
  brandSchema,
  homeSchema,
  lawTrackerSchema,
  legalSchema,
  securitySchema,
  uiSchema,
  pageSchema,
  researchIndexSchema,
  playgroundSchema,
  interfaceSchema,
  siteSchema,
  whitepaperSchema,
} from './schema.ts';
import type { Schema } from './schema.ts';
import { substitute, unresolvedTokens, validate } from './validate.ts';

export type * from './types.ts';
export { validate, substitute, unresolvedTokens, walkStrings } from './validate.ts';
export { STATUSES, LOCALES, SECURITY_ANCHORS } from './schema.ts';

type RawBrand = Omit<Brand, 'origin'>;

/** Raw (unsubstituted) JSON, keyed by the path used in error messages. */
export const raw = {
  brand: brandJson as RawBrand,
  site: siteJson,
  home: homeJson,
  pages: {
    platform: platformJson,
    governance: governanceJson,
    sdks: sdksJson,
    pricing: pricingJson,
    lawTracker: lawTrackerJson,
    investors: investorsJson,
    research: researchJson,
    playground: playgroundJson,
    interface: interfaceJson,
  },
  whitepapers: {
    'somatosensory-closed-loop': somatosensoryJson,
  },
  /** Localised files: every NO file has the same keys as its EN counterpart (content test). */
  locales: {
    en: {
      ui: uiEn,
      security: securityEn,
      legal: { privacy: privacyEn, terms: termsEn, cookies: cookiesEn, company: companyEn },
      innerPages: {
        platform: platformJson,
        governance: governanceJson,
        sdks: sdksJson,
        pricing: pricingJson,
      },
    },
    no: {
      ui: uiNo,
      security: securityNo,
      legal: { privacy: privacyNo, terms: termsNo, cookies: cookiesNo, company: companyNo },
      innerPages: {
        platform: platformNo,
        governance: governanceNo,
        sdks: sdksNo,
        pricing: pricingNo,
      },
    },
  },
} as const;

/** Schema per raw entry, used by loadContent and the tests. */
export const schemas: { path: string; value: unknown; schema: Schema }[] = [
  { path: 'brand.json', value: raw.brand, schema: brandSchema },
  { path: 'content/site.json', value: raw.site, schema: siteSchema },
  { path: 'content/home.json', value: raw.home, schema: homeSchema },
  { path: 'content/pages/platform.json', value: raw.pages.platform, schema: pageSchema },
  { path: 'content/pages/governance.json', value: raw.pages.governance, schema: pageSchema },
  { path: 'content/pages/sdks.json', value: raw.pages.sdks, schema: pageSchema },
  { path: 'content/pages/pricing.json', value: raw.pages.pricing, schema: pageSchema },
  { path: 'content/pages/law-tracker.json', value: raw.pages.lawTracker, schema: lawTrackerSchema },
  { path: 'content/pages/investors.json', value: raw.pages.investors, schema: pageSchema },
  { path: 'content/pages/research.json', value: raw.pages.research, schema: researchIndexSchema },
  { path: 'content/pages/playground.json', value: raw.pages.playground, schema: playgroundSchema },
  { path: 'content/pages/interface.json', value: raw.pages.interface, schema: interfaceSchema },
  {
    path: 'content/research/somatosensory-closed-loop.json',
    value: raw.whitepapers['somatosensory-closed-loop'],
    schema: whitepaperSchema,
  },
  ...(Object.keys(raw.locales) as Locale[]).flatMap((l) => [
    { path: `content/ui.${l}.json`, value: raw.locales[l].ui, schema: uiSchema },
    { path: `content/security.${l}.json`, value: raw.locales[l].security, schema: securitySchema },
    ...Object.entries(raw.locales[l].legal).map(([k, v]) => ({
      path: `content/legal/${k}.${l}.json`,
      value: v,
      schema: legalSchema,
    })),
    // EN inner pages are already listed above under their own file names.
    ...Object.entries(l === 'en' ? {} : raw.locales[l].innerPages).map(([k, v]) => ({
      path: `content/pages/${k}.${l}.json`,
      value: v,
      schema: pageSchema,
    })),
  ]),
];

export class ContentError extends Error {
  errors: string[];
  constructor(errors: string[]) {
    super(`@nf/content: ${errors.length} error(s)\n  ${errors.join('\n  ')}`);
    this.errors = errors;
  }
}

/** Placeholder values derived from a brand. */
export function brandVars(b: RawBrand): Record<string, string> {
  return {
    brand: b.name,
    legalName: b.legalName,
    domain: b.domain,
    origin: `https://${b.domain}`,
    pkg: b.codeIdentifiers.pythonImport,
  };
}

/**
 * Validates the raw JSON, substitutes {brand}/{legalName}/{domain}/{origin}/{pkg} and returns typed content.
 * `overrides.brand` replaces brand fields (used by tests to prove a rename flows everywhere).
 * Throws ContentError on schema errors or leftover placeholders.
 */
export function loadContent(overrides: { brand?: Partial<RawBrand> } = {}): Content {
  const b: RawBrand = { ...raw.brand, ...overrides.brand };
  const errors: string[] = [];
  for (const { path, value, schema } of schemas) {
    const v = path === 'brand.json' ? b : value;
    errors.push(...validate(v, schema).map((e) => `${path} ${e}`));
  }
  const vars = brandVars(b);
  const brand: Brand = { ...b, origin: vars.origin };
  const body = substitute(
    { site: raw.site, home: raw.home, pages: raw.pages, whitepapers: raw.whitepapers },
    vars,
  );
  const locales = {} as Record<Locale, LocaleContent>;
  for (const l of Object.keys(raw.locales) as Locale[])
    locales[l] = {
      locale: l,
      ...(substitute(raw.locales[l], vars) as Omit<LocaleContent, 'locale'>),
    };
  errors.push(...unresolvedTokens(locales));
  errors.push(...unresolvedTokens(body));
  if (errors.length) throw new ContentError(errors);
  return { brand, locales, ...(body as unknown as Omit<Content, 'brand' | 'locales'>) };
}

/** The validated site content with the real brand. */
export const content: Content = loadContent();
export const brand: Brand = content.brand;

/** English: the full site plus the localised pages. */
export type EnglishContent = LocaleContent & Omit<Content, 'locales'>;
/** Norwegian (bokmål): /security, the legal pages and the inner pages (innerPages); not the homepage. */
export type NorwegianContent = LocaleContent & { brand: Brand };

export const INNER_PAGE_KEYS: readonly InnerPageKey[] = [
  'platform',
  'governance',
  'sdks',
  'pricing',
];

/**
 * Inner pages that are published in `locale`: every English page; a translated page only once
 * `reviewed: true` (owner language review, lead ruling 2026-09-27). Routes, hreflang, the language
 * switch and the sitemap use this list; an unpublished page may be built, but only as noindex.
 */
export function publishedInnerPages(locale: Locale): InnerPageKey[] {
  const pages = content.locales[locale]?.innerPages;
  if (!pages) throw new Error(`@nf/content: unknown locale ${String(locale)}`);
  return INNER_PAGE_KEYS.filter((k) => locale === 'en' || pages[k].reviewed === true);
}

/** Content for one locale. English is complete; Norwegian has ui, security, legal and innerPages. */
export function getContent(locale: 'en'): EnglishContent;
export function getContent(locale: 'no'): NorwegianContent;
export function getContent(locale: Locale): EnglishContent | NorwegianContent;
export function getContent(locale: Locale): EnglishContent | NorwegianContent {
  const lc = content.locales[locale];
  if (!lc) throw new Error(`@nf/content: unknown locale ${String(locale)}`);
  if (locale === 'en') {
    const { locales: _unused, ...rest } = content;
    return { ...rest, ...lc };
  }
  return { brand: content.brand, ...lc };
}
