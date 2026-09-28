// The ONE adapter between @nf/content and the pages. Copy is never typed here; the company name
// is read from content.brand (brand token rule, BLUEPRINT §2.2).
import { content, getContent, publishedInnerPages } from '@nf/content';
import { DOCS_ROUTES } from './docs.ts';
import { organizationSchema, type JsonLdNode } from './jsonld.ts';

export { content };
export const THEME = __NF_THEME__;
export const CANONICAL_ORIGIN = __NF_CANONICAL_ORIGIN__;
/** SITE_STAGE=preview|launch|public, resolved once in astro.config.mjs (preview builds are noindex). */
export const SITE_STAGE = __NF_SITE_STAGE__;
export const site = content.site;
/**
 * Site-wide Organization JSON-LD node (web-seo, WEB-PLAN roster). Base.astro is frozen (it is one of
 * the homepage-pinned sources in apps/web/test/homepage.test.mjs), so this is NOT auto-injected there;
 * each inner page renders it itself via <JsonLd schema={[organizationJsonLd, ...]} />, never on "/".
 */
export const organizationJsonLd: JsonLdNode = organizationSchema(
  content.brand.name,
  CANONICAL_ORIGIN,
);
/** English site chrome (localised chrome for other locales: lib/i18n.ts ui(locale)). */
export const uiEn = getContent('en').ui;
export const statusLabels = uiEn.statusLabels;
export const statusPrefix = uiEn.statusPill;

/** Canonical URL of a page = the same path on the clinical (canonical) host. */
export function canonicalUrl(pathname: string): string {
  let p = pathname.replace(/index\.html$/, '').replace(/\.html$/, '');
  if (!p.startsWith('/')) p = `/${p}`;
  if (p !== '/' && !p.endsWith('/')) p = `${p}/`;
  return new URL(p, CANONICAL_ORIGIN).href;
}

/** Generic content pages rendered by src/pages/[page].astro. (/security has its own page.) */
export const genericPages = {
  platform: content.pages.platform,
  governance: content.pages.governance,
  sdks: content.pages.sdks,
  pricing: content.pages.pricing,
} as const;

export const LEGAL_KEYS = ['privacy', 'terms', 'cookies', 'company'] as const;

/**
 * Routes listed in sitemap.xml. The gallery (noindex), 404, the legal drafts (noindex until the
 * advokat review) and any unreviewed /no/<inner page> (noindex until the owner's language review,
 * @nf/content publishedInnerPages) are deliberately absent.
 */
export function sitemapRoutes(): string[] {
  return [
    '/',
    ...Object.keys(genericPages).map((k) => `/${k}/`),
    '/security/',
    '/no/security/',
    '/law-tracker/',
    '/playground/',
    '/interface/',
    '/research/',
    ...Object.keys(content.whitepapers).map((s) => `/research/${s}/`),
    ...DOCS_ROUTES,
    ...LEGAL_KEYS.flatMap((k) =>
      content.locales.en.legal[k].draft ? [] : [`/legal/${k}/`, `/no/legal/${k}/`],
    ),
    ...publishedInnerPages('no').map((k) => `/no/${k}/`),
  ];
}
