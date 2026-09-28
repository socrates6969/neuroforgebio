# Proposal: og:type + Twitter Card in Base.astro (web-seo)

**Status:** proposed, not applied on this branch. `apps/web/src/layouts/Base.astro` is frozen — it is
one of the homepage-pinned sources in `apps/web/test/homepage.test.mjs`, whose source check
(`git diff <merge-base-with-main> -- ...Base.astro...`) fails on ANY diff, regardless of whether the
rendered output for `/` changes. It needs to land centrally (the lead merging it directly, so it is
already at every branch's merge-base), not from an individual worker's branch.

## What & why

Every inner page already gets `og:title`, `og:description`, `og:url`, `og:site_name` and `og:locale`
from Base.astro. Two things are still missing for correct Open Graph / Twitter Card unfurls:
`og:type`, and the three Twitter Card tags (`twitter:card`, `twitter:title`, `twitter:description`).
Both need `<head>` placement — unlike JSON-LD (which Google explicitly supports anywhere in the
document, and which web-seo has instead added directly in each inner page's body, with no Base.astro
change), link-unfurl crawlers generally only read `<head>` reliably.

## Design

One new optional prop, `ogType?: 'website' | 'article'`. Left unset — as `index.astro` always is —
Base.astro renders byte-identical to today, so `/` is provably unaffected; every other inner page would
pass `ogType="website"` (listing/product/policy pages) or `ogType="article"` (docs pages, the
whitepaper).

`twitter:card` is `summary`, not `summary_large_image`: there is no brand/social-card image anywhere in
the repo yet (see docs/web/seo-audit.md), and shipping the large-image card variant without a real
image would be worse than the plain summary card.

## Exact diff

```diff
--- a/apps/web/src/layouts/Base.astro
+++ b/apps/web/src/layouts/Base.astro
@@
-interface Props { title: string; description: string; noindex?: boolean; locale?: Locale }
-const { title, description, noindex = false } = Astro.props;
+interface Props {
+  title: string;
+  description: string;
+  noindex?: boolean;
+  locale?: Locale;
+  /** Opts an inner page into og:type + Twitter Card. Left unset (as index.astro always is),
+   *  Base.astro renders exactly as before — "/" is provably unaffected. */
+  ogType?: 'website' | 'article';
+}
+const { title, description, noindex = false, ogType } = Astro.props;
@@
     <meta property="og:locale" content={locale === 'no' ? 'nb_NO' : 'en_US'} />
+    {ogType && <meta property="og:type" content={ogType} />}
+    {ogType && <meta name="twitter:card" content="summary" />}
+    {ogType && <meta name="twitter:title" content={title} />}
+    {ogType && <meta name="twitter:description" content={description} />}
   </head>
```

Every inner page then adds `ogType="website"` or `ogType="article"` to its existing `<Base ...>` call —
mechanical; no other change needed since title/description are already passed everywhere. Once this
lands, each shared-file owner (web-copy for `[page].astro`, web-docs for `pages/docs/**`, nfb-legal for
the legal pages, web-seo for the rest) adds the one attribute to their own `<Base>` calls.

## Verification once landed

`apps/web/test/seo.test.mjs` (web-seo) has an Open Graph assertion block; extending it to also require
`og:type` + the three Twitter tags on every in-scope inner page, and to assert the homepage has
neither, is a small follow-up once this lands.
