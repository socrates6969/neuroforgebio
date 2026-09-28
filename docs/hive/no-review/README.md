# Owner review packet: Norwegian inner pages

**For:** Marius Carlsson (owner), to decide whether `/no/platform`, `/no/sdks`, `/no/governance` and `/no/pricing` can be
marked reviewed (`"reviewed": true`, which makes them indexed, adds them to the sitemap and turns on hreflang).
**Prepared by:** hive H1 (website), task H1-a, vote V1 (3/3). **Base:** `origin/main` @ `4370f95`.
**Status: nothing on the site was changed.** This packet only adds `docs/hive/no-review/*.md`.

| Page | File | Findings routed to |
|---|---|---|
| /no/platform | [platform.md](platform.md) | queen decides |
| /no/sdks | [sdks.md](sdks.md) | **web-copy** |
| /no/governance | [governance.md](governance.md) | queen decides |
| /no/pricing | [pricing.md](pricing.md) | **web-copy-2**. **PROVISIONAL: web-copy-2 is changing pricing.json/pricing.no.json on web/copy-licence-tiers (eb90773); regenerate after it merges.** |

## Scope

- EN `packages/content/content/pages/<page>.json` vs NO `<page>.no.json` for platform, sdks, governance and pricing.
- UI labels rendered on these pages from `packages/content/content/ui.no.json` (status and build pills).
- Terminology cross-check against the NO pages that are already public: `security.no.json`, `legal/*.no.json`.
- Claims checked against the sources the page cites (`market/landscape.md`, `market/regulation.md`,
  `docs/hive/M*-REPORT.md`, `docs/adr/0006-licensing.md`).
- Out of scope: layout, nav/footer, the homepage, and anything outside these four pages. Two rendering observations
  are noted (English code-block `aria-label`; CTAs link to EN pages).

## Method

1. Read both JSON files per page at `4370f95` and put **every user-visible string** side by side, keyed by JSON path
   (arrays shown by section `id`, e.g. `sections[why].evidence[0].text`). Code lines, source paths and grades are
   left out of the count because they are deliberately untranslated.
2. Read each NO string as Bokmål and tag it: **E** language error, **D** meaning drift, **A** ambiguity,
   **S** style preference, **C** consistency, **U** unsure, **OK**. Only E is a clear error; S is optional.
3. Listed every domain term and its NO rendering, then compared across the four pages, `ui.no.json` and
   `security.no.json`/`legal/*.no.json`.
4. Listed every number, date, law, standard, status and capability claim with its EN counterpart and EN tag
   (`source`/`sourceUrl`/`grade`/`status`/`buildState`/`buildSource`). Opened the cited `market/*.md` section and
   confirmed the numbers and dates. For `buildSource`, confirmed that the report has a row for the cited step
   (existence only; H1-c re-audits them).
5. Compared key sets EN vs NO by reading (no scripts were run).
6. For /pricing and /sdks, read `web/copy-licence-tiers` @ `eb90773` with `git show` (read only) and noted what
   changes.

**No runs were made:** no node, pnpm, python, build, test or lint. Only file reads and git.

## Summary per page

| Page | Strings (EN / NO) | Terms listed | Claims | NO meaning drifts | Language errors (E) | Ambiguities (A) | EN-side issues |
|---|---|---|---|---|---|---|---|
| /no/platform | 38 / 38 | 28 | 17 | 3 (1 unsure) | 1 (#22 "navngir") | 1 (#9) | 2 EN claims with no source (P6, P13) |
| /no/sdks | 23 / 23 | 15 | 7 | 0 | 0 | 1 (#17) | licence status stale vs ADR 0006 (S5); Unity/Unreal "Planned" under a Roadmap pill (#16) |
| /no/governance | 32 / 32 | 20 | 15 | 4 (1 unsure) | 0 | 1 (#20 "Før …") | EN "education settings" looser than the Article (#29) |
| /no/pricing (provisional) | 17 / 19 | 21 | 8 | 5 (1 unsure) | 1 (#9 "lisens avventer") | 2 (#11, #13) | tier contents have no source (R3–R5); licence "pending" stale |
| **Total** | **110 / 112** | **84** (with overlaps) | **47** | **12** (3 unsure) | **2** | **5** | |

**Missing/extra keys:** no key is missing in any NO file. Extra in NO, all expected: `reviewed: false` (4 files) and
`pricing.earlyAccessNote` (text, linkLabel, href). All `status`, `buildState`, `buildSource`, `source`, `sourceUrl`,
`grade`, `href`, `variant`, `disabled`, section `id`s and `code.lines` match EN.

**Overall reading:** the Norwegian is correct, readable Bokmål. There are two small grammar/word-choice errors and a
handful of ambiguities. No NO string claims a higher build status or a stronger capability than its EN string. The main
open items are terminology choices (below) and EN-side staleness on the licence.

## PROPOSED NO GLOSSARY: proposal, needs owner approval

**Proposal, needs owner approval. Nothing here is applied.** Per vote V1, a glossary test is only written after the
owner approves the terms.

| EN term | Proposed NO | Used now (where) | Alternatives | Why |
|---|---|---|---|---|
| pipeline | **owner decision**: "prosesseringskjede" (short: "kjede"), or keep "pipeline" | "løype" everywhere: platform, sdks, governance, pricing ("forbehandlingsløype", "løypetrinn", "hostede løyper") | "pipeline" (loanword, what Norwegian developers say), "behandlingskjede", "løype" (current) | "løype" means a trail or ski track. Readers can work it out, but it is not an established term, and it is the word used most often on these pages. |
| preprocessing | forbehandling | platform | "preprosessering" | Established; keep. |
| provenance | proveniens | all four; /no/security "Byggeproveniens" | "opphavssporing", "sporbarhet" | Already the house term (`docs/web/i18n/README.md`); keep. |
| run (noun) | kjøring | platform, sdks | none | Keep. |
| ingest | innlesing | platform | "datainntak" | Keep. |
| governance (page name) | **owner decision**: "Styring" | governance title, eyebrow, CTA on platform; "styringslaget" | "Datastyring", "Styring og etterlevelse" | "Styring" alone is broad (management/steering); "Datastyring" is clearer if the owner wants that. |
| governed (model registry) | "modellregister med styring" | platform "styrt modellregister" | "styrt" (current) | "styrt" reads as "steered". Optional. |
| SDK / SDKs | **SDK, SDK-et, SDK-er, SDK-ene** | sdks, pricing, `legal/terms.no.json` | "programvaresett" (used on /no/security) | Two terms for one thing on the public site. Proposal: SDK everywhere; /no/security would need a later change (not in this task). |
| built and tested internally | "bygget og testet internt" (prose); pill "Bygget, testet internt" | all four; `ui.no.json` | none | Keep both; they mirror EN prose and EN pill. |
| deployed / not deployed yet | **"i drift" / "ikke i drift ennå"** | four pages say "tatt i bruk"; /no/security and privacy say "i drift" | "tatt i bruk" (current) | "i drift" is more precise for a hosted service and matches the public pages. |
| enterprise (tier / customers) | **owner decision**: "bedriftskunder" (prose), tier name "Enterprise" or "Storbedrift" | pricing "Virksomhet", "større virksomheter", "virksomheter"; /no/security + privacy "bedriftskunder" | "Virksomhet" (current) | "Virksomhet" = any business; it does not signal the top tier. |
| data subjects | **owner decision**: "de registrerte" (GDPR term) or "forsøkspersoner" | pricing, /no/security "forsøksperson" | "personer dataene gjelder" | "forsøkspersoner" fits research; startup customers' subjects can be users or patients. |
| device | "enhet" (hardware), "medisinsk utstyr" (regulatory) | platform "apparat"; pricing and /no/security "enheter" | "apparat" | One word for the same thing. |
| device software (FDA) | **unsure, legal check**: "programvare som er eller inngår i medisinsk utstyr" | platform "programvare i medisinsk utstyr" | none | The current wording covers only software *in* a device. |
| consent ledger | samtykkelogg | sdks, governance, pricing | "samtykkeregister" | Keep. |
| audit trail / audit log | revisjonsspor / revisjonslogg | governance, /no/security, `ui.no.json` | none | Keep. |
| deletion certificate | slettebevis | governance, /no/security | none | Keep. |
| opt-in consent | aktivt samtykke | governance | "uttrykkelig samtykke" (that is "explicit") | Keep. |
| emotion inference | **utledning av følelser** | governance: "gjenkjenning av følelser" (#24) and "utleder følelser" (#29) | "følelsesgjenkjenning" (a different AI Act term) | Make one term, the one Art. 5(1)(f) uses. |
| EU AI Act | KI-forordningen (EUs KI-forordning) | governance | none | Official Norwegian short name; keep. |
| early access / join | **"Meld deg på tidlig tilgang"**, "listen for tidlig tilgang" | CTAs "Bli med i tidlig tilgang" (platform, sdks, governance); pricing "Bli med på listen for tidlig tilgang" | "Få tidlig tilgang" | You join a list, not "tidlig tilgang". |
| hosted | "driftet" / "i skyen" | sdks "hostede plattformen"; pricing "Hostede løyper" | "hostet" (current, common IT anglicism) | Style only; "hostet" is acceptable. |
| BAA | "databehandleravtale etter HIPAA (BAA)" on first use | pricing "BAA"; /no/security explains it | none | Match /no/security. |
| SSO | "felles pålogging (SSO)" on first use | pricing "SSO"; /no/security explains it | none | Match /no/security. |
| on-prem | "i kundens eget datasenter" | pricing "lokalt" | "lokalt installert" | "lokalt" alone is vague and caused the #13 ambiguity. |
| custom (price) / quote | "pris etter avtale" / "pris på forespørsel" | pricing "tilpasset"; branch "tilbud" | none | "tilbud" clashes with "ingenting på denne siden er et tilbud". |
| fair (pricing) | "rimelig" | pricing hero "Rettferdig" | "rettferdig" | Idiom. |
| grid (of pipelines) | rutenett | platform, pricing branch | "grid" | Keep (as in "rutenettsøk"); unsure, owner to confirm. |
| status labels | Designet / Planlagt / Veikart / Under arbeid | `ui.no.json` | none | Keep. |

## Owner decisions needed

1. **Mark reviewed?** Per page, decide after reading the tables. Suggested order: /no/governance and /no/platform are
   closest to ready (no E errors on governance; one on platform). /no/sdks needs the licence wording settled first.
   /no/pricing should wait for `web/copy-licence-tiers` to merge and this file to be regenerated.
2. **"pipeline" term** (glossary row 1): keep "løype", or switch to "prosesseringskjede"/"pipeline" on all four pages.
3. **"Styring"** as the page name for Governance, or "Datastyring".
4. **SDK vs "programvaresett"**: pick one for the whole NO site (/no/security currently differs).
5. **Enterprise wording**: "Virksomhet" vs "bedriftskunder"/"Enterprise"/"Storbedrift".
6. **"forsøkspersoner" vs "de registrerte"** for data subjects (pricing and /no/security).
7. **"tatt i bruk" vs "i drift"** for "deployed".
8. **"programvare i medisinsk utstyr"** for "device software": needs a legal-minded check (unsure).
9. **AI Act date for Norwegian readers**: add "i EU" to "gjeldende fra 2. feb. 2025"? EEA applicability in Norway was
   not verified here (unsure).
10. **Licence wording on /sdks and /pricing**: ADR 0006 is Accepted, but the live EN and NO pages still say "pending the
    owner's decision". `web/copy-licence-tiers` fixes this. Confirm that branch (routed: web-copy for /sdks,
    web-copy-2 for /pricing).
11. **Fix list** (if you agree, the copy owners apply it; this packet edits nothing):
    - E: platform #22 "navngir" → "angir"; pricing #9 "(lisens avventer)" → "(lisensen er ikke avklart)".
    - A: pricing #11 "de sentrale amerikanske delstatene"; pricing #13 "lokalt på veikartet"; governance #20
      "Før tilbaketrukket samtykke videre"; platform #9 "43 forbehandlingsløyper fra 2025"; sdks #17 "i måneden".
    - D: governance #24/#26/#28, platform #5/#14, pricing #5; branch pricing "tilbud" vs "ikke et tilbud".
12. **Observations for the queen to route** (not copy): the CTAs on NO pages link to EN pages even after review
    (`Button.astro` does not localise hrefs), and the code-block `aria-label` ("Illustrative Python example",
    `site.json`) is English on /no/platform and /no/sdks.
