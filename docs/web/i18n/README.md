# Norwegian inner pages

**Status: PENDING OWNER LANGUAGE REVIEW.** The owner, a Norwegian speaker, reviews the wording before any /no inner page
goes public (lead, 2026-09-27). Until then these texts are drafts.

web-copy-2 drafted the texts here. On branch `web/no-pages` they moved to
`packages/content/content/pages/<page>.no.json` (platform, governance, sdks, pricing), exposed as
`getContent('no').innerPages`.

- A content test (`i18n: NO inner pages have the EN keys, evidence and tags`) enforces EN parity. The NO files must
  have the same key paths and section shapes, including the evidence count per section. They must also keep the same
  `status`, `buildState`, `buildSource`, `source`, `sourceUrl`, `grade`, `href`, `variant`, `disabled`, `id` and
  code lines. Code comments stay English; only `note` is translated.
- Each NO page has `"reviewed": false`. Only the owner's review flips it. Until then `publishedInnerPages('no')` excludes
  the page, so it is noindex, not in the sitemap and not in LOCALISED_ROUTES (lead ruling).
- The only other NO-only key is `pricing.earlyAccessNote`. It replaces the English-only early-access form on /no/pricing
  with a link to it.
- Status and build labels come from `ui.no.json` (Designet/Planlagt/Veikart, "Bygget, testet internt").
- Terminology follows `security.no.json`: nevrale data, samtykke, revisjonslogg/-spor, slettebevis, proveniens.
- Bokmål, machine-drafted.

The routes (`i18n.ts` LOCALISED_ROUTES) and the PageBody locale switch are web-a11y's. PageBody currently passes
`uiEn.buildStateLabels`, so it needs that switch. hreflang and the sitemap test are web-seo's.
