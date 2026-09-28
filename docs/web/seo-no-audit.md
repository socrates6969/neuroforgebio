# Norwegian (/no/) metadata audit (web-seo, T6, report only)

Scope: every `/no/` page's `<title>` / meta description — genuinely Norwegian (not an English
copy), unique, and length-sane. Method: source review (`packages/content/content/{security.no.json,
legal/*.no.json}`), cross-checked against the matching `.en.json` file for each page. No build needed
for this check (pure content/text), so no bci-queen slot used.

There are exactly 5 `/no/` pages, per `apps/web/src/lib/i18n.ts`'s `LOCALISED_ROUTES` (the only routes
that exist in both locales) and confirmed against `apps/web/src/pages/no/`: `/no/security/`,
`/no/legal/privacy/`, `/no/legal/terms/`, `/no/legal/cookies/`, `/no/legal/company/`.

## Genuinely Norwegian, not an English copy

**Clean, all 5.** Every `/no/` page's `meta.title` and `meta.description` differ from its `.en.json`
counterpart (checked programmatically, not just by eye) and read as real Norwegian bokmål, not
machine-literal or copy-pasted English:

| Page | Title | Description (first words) |
|---|---|---|
| `/no/security/` | "Sikkerhet \| {brand}" | "Slik er {brand} utformet for å beskytte..." |
| `/no/legal/privacy/` | "Personvernerklæring · {brand}" | "Utkast til personvernerklæring: hvilke data..." |
| `/no/legal/terms/` | "Vilkår for bruk av nettstedet · {brand}" | "Utkast til vilkår for bruk av nettstedet..." |
| `/no/legal/cookies/` | "Erklæring om informasjonskapsler (cookies) · {brand}" | "Utkast til cookie-erklæring: nettstedet..." |
| `/no/legal/company/` | "Selskapsinformasjon · {brand}" | "Utkast til selskapsinformasjon for det..." |

One note, not a gap: `/no/legal/cookies/`'s title and description both keep the English word "cookie"
(as "informasjonskapsler (cookies)" / "cookie-erklæring"). This is a deliberate, common convention in
Norwegian tech and legal writing (e.g. Datatilsynet's own guidance uses "cookies" alongside
"informasjonskapsler"), already used in the page's visible heading and body text — not a translation
gap.

## Unique

**Clean, all 5.** No two `/no/` pages share a title or a description (the 4 legal pages' descriptions
used to be identical — see `docs/web/seo-audit.md` T2 — that's fixed on main). Titles were always
distinct.

## Length-sane

**One finding.** Target ranges: title ≲60 characters (SERP display), description ~120–160 characters
(Google's snippet length). `{brand}` substituted to "NeuroForge Bio" (14 characters) below.

| Page | Title (chars) | Description (chars) |
|---|---|---|
| `/no/security/` | 26 | ~~168~~ 137, fixed (see below) |
| `/no/legal/privacy/` | 36 | 146 |
| `/no/legal/terms/` | 46 | 139 |
| `/no/legal/cookies/` | 59 (borderline, not flagged) | 151 |
| `/no/legal/company/` | 36 | 143 |

- **`/no/security/` description is 168 characters, 8 over the common ~160-character soft cap** and
  likely to get truncated mid-word in a Google snippet. Same finding as the original T1 audit
  (`docs/web/seo-audit.md`); **now fixed** — see below.

  The first version of this proposal, quoted here originally, had a typo ("Slik er {brand} **er**
  utformet...", a duplicate "er") that also broke `content.test.mjs`'s pinned prefix regex
  (`/^Slik er \{brand\} utformet for å beskytte nevrale data: /`). nfb-security and web-queen both
  caught it independently. **Do not copy the text below with "er utformet" — that version was never
  applied.** The corrected, nfb-security-approved, and applied text (137 chars substituted, 130 chars
  raw with the `{brand}` token) is:
  `"Slik er {brand} utformet for å beskytte nevrale data: kryptering, tilgangsstyring, revisjonslogg, sletting og ærlige statusmerker."`
  (drops "egne nøkler per forsøksperson" ["per-subject keys"] from the description only — the fact
  itself stays on the page and in the English description is untouched). Applied in
  `web/seo-no-security-fix` @ 528eb90, verified against the pinned regex and both theme builds/test
  suites, sha confirmed by nfb-security as matching their approval.
- `/no/legal/cookies/`'s title at 59 characters is right at the edge but not flagged: it's one
  character short of the guideline and the "(cookies)" suffix is meaningful, not filler.

## Owner for the one gap (resolved)

`/no/security/`'s content lives in `packages/content/content/security.no.json`. This file had no
explicit owner in `docs/hive/WEB-BOARD.md`'s ownership table; nfb-security reviewed and approved the
fix directly, and it's applied (`web/seo-no-security-fix` @ 528eb90).

## Summary

| Check | Result |
|---|---|
| Genuinely Norwegian (not English copies) | Clean, all 5 |
| Unique | Clean, all 5 |
| Length-sane | Fixed: `/no/security/` description was 168 chars, now 137 (nfb-security-approved, applied @ 528eb90) |
