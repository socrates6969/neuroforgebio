// Locales: English at "/", Norwegian bokmål under "/no/". HTML lang "en" / "nb" (BCP 47 bokmål),
// hreflang alternates en / nb / x-default. /security and the three legal pages exist in Norwegian;
// an inner page (platform/governance/sdks/pricing) joins LOCALISED_ROUTES only once its owner has
// reviewed the translation (@nf/content publishedInnerPages, lead ruling 2026-09-27) - until then
// its /no/<page> route is still built (apps/web/src/pages/no/[page].astro), but noindex, out of the
// sitemap, and absent here, so no hreflang tag or language-switch link ever points at it.
import { getContent, publishedInnerPages, type Locale } from '@nf/content';
import { CANONICAL_ORIGIN } from './site.ts';

export type { Locale };
export const LOCALES: Locale[] = ['en', 'no'];
export const DEFAULT_LOCALE: Locale = 'en';
/** <html lang> and hreflang per locale. */
export const HTML_LANG: Record<Locale, string> = { en: 'en', no: 'nb' };

/** Paths (without locale prefix, trailing slash) that exist in every locale. */
export const LOCALISED_ROUTES: readonly string[] = [
  '/security/',
  '/legal/privacy/',
  '/legal/terms/',
  '/legal/cookies/',
  '/legal/company/',
  ...publishedInnerPages('no').map((k) => `/${k}/`),
];

export const prefix = (l: Locale) => (l === 'en' ? '' : `/${l}`);
export const ui = (l: Locale) => getContent(l).ui;

const withSlash = (p: string) => (p.endsWith('/') ? p : `${p}/`);

/** Locale of a URL path ("/no/security/" -> "no"). */
export function localeOf(pathname: string): Locale {
  return /^\/no(\/|$)/.test(pathname) ? 'no' : 'en';
}

/** Path without its locale prefix ("/no/security/" -> "/security/"). */
export function basePath(pathname: string): string {
  const p = pathname.replace(/index\.html$/, '');
  return withSlash(p.replace(/^\/no(?=\/|$)/, '') || '/');
}

export const isLocalised = (base: string) => LOCALISED_ROUTES.includes(withSlash(base));

/** The same page in `to`, or null when it does not exist there. */
export function pathIn(pathname: string, to: Locale): string | null {
  const base = basePath(pathname);
  if (to === 'en') return base;
  return isLocalised(base) ? `${prefix(to)}${base}` : null;
}

/** hreflang alternates (absolute, canonical host) for a page that exists in every locale. */
export function alternates(pathname: string): { hreflang: string; href: string }[] {
  if (!isLocalised(basePath(pathname))) return [];
  const abs = (p: string) => new URL(p, CANONICAL_ORIGIN).href;
  return [
    ...LOCALES.map((l) => ({ hreflang: HTML_LANG[l], href: abs(pathIn(pathname, l)!) })),
    { hreflang: 'x-default', href: abs(pathIn(pathname, DEFAULT_LOCALE)!) },
  ];
}

/** An internal link from a page in `locale`: points at the localised page when it exists. */
export function localiseHref(href: string, locale: Locale): string {
  if (locale === 'en' || !href.startsWith('/') || href.startsWith('//')) return href;
  const [path, hash] = href.split('#');
  const target = pathIn(path, locale);
  if (!target || !isLocalised(basePath(path))) return href;
  return hash !== undefined ? `${target}#${hash}` : target;
}
