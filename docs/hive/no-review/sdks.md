# /no/sdks: owner review packet

- **Route:** `/no/sdks` (built by `apps/web/src/pages/no/[page].astro`; `noindex` while `"reviewed": false`)
- **Sources read at commit `4370f95`:**
  - EN: `packages/content/content/pages/sdks.json`
  - NO: `packages/content/content/pages/sdks.no.json`
  - Labels: `packages/content/content/ui.no.json`; cross-check `security.no.json`, `legal/terms.no.json`
  - Cited evidence: `market/landscape.md` §2; build source `docs/hive/M4-REPORT.md`; licence decision `docs/adr/0006-licensing.md`
  - Pending change, read only: branch `web/copy-licence-tiers` @ `eb90773` (commit `09d96cb` edits `sdks.json`/`sdks.no.json`)
- **Findings on this page are routed to: web-copy** (label only; nobody was contacted).

Legend: **E** language error · **D** meaning drift · **A** ambiguity · **S** style preference · **C** consistency ·
**U** unsure · **OK** no remark. `<em>` markup is kept from the JSON.

## 1. Every user-visible string

| # | JSON key path | EN | NO | Note |
|---|---|---|---|---|
| 1 | `meta.title` | SDKs · {brand} | SDK-er · {brand} | OK ("SDK-er" is the correct Bokmål plural of an abbreviation; `legal/terms.no.json` also says "SDK-er"). C: /no/security says "programvaresett" (see glossary). |
| 2 | `meta.description` | A Python SDK first, built and tested internally, on one shared core. A C interface for C++ and game engines is planned. Licence pending the owner's decision. | Et Python-SDK først, bygget og testet internt, på én felles kjerne. Et C-grensesnitt for C++ og spillmotorer er planlagt. Lisensen avventer eierens beslutning. | OK as Norwegian. **Stale in EN and NO:** ADR 0006 is Accepted (see S5). `web/copy-licence-tiers` replaces this sentence (see §6). |
| 3 | `hero.eyebrow` | SDKs | SDK-er | OK |
| 4 | `hero.heading` | Python first. <em>One shared core.</em> | Python først. <em>Én felles kjerne.</em> | OK |
| 5 | `hero.lede` | Every SDK records provenance the same way because every SDK uses the same core. Signal processing stays in the Python tools your lab already trusts. | Alle SDK-er registrerer proveniens på samme måte, fordi alle bruker den samme kjernen. Signalbehandlingen blir værende i Python-verktøyene laboratoriet ditt allerede stoler på. | OK |
| 6 | `sections[example].heading` | Every run carries <em>its provenance.</em> | Hver kjøring har <em>sin egen proveniens.</em> | S/D (negligible): "egen" (own) is added. Harmless; "Hver kjøring <em>bærer med seg proveniensen sin.</em>" is closer. |
| 7 | `sections[example].body[0]` | Open a recording, run a pinned pipeline version, and get a provenance handle that records every parameter, version and input hash. | Åpne et opptak, kjør en låst versjon av en løype, og få et proveniens-håndtak som registrerer hver parameter, versjon og inndata-hash. | S (orthography): "proveniens-håndtak" joins two Norwegian words, so the normal form is one word, "provenienshåndtak". The hyphen is not strictly wrong (Språkrådet allows it for readability) but is unusual here. C: "løype". |
| 8 | `sections[example].code.note` | Illustrative API, subject to change | Illustrerende API, kan endres | OK. Code comments stay English by design. |
| 9 | `sections[languages].heading` | Languages, <em>in order.</em> | Språk, <em>i rekkefølge.</em> | OK |
| 10 | `sections[languages].body[0]` | We build for the languages our users already work in, in the order they ask for them. | Vi bygger for språkene brukerne våre allerede jobber i, i den rekkefølgen de ber om dem. | OK |
| 11 | `sections[languages].items[0].heading` | Python | Python | OK |
| 12 | `sections[languages].items[0].body` | The first SDK, designed to work alongside MNE-Python, BIDS and NWB tooling. Not published yet. | Det første SDK-et, laget for å fungere sammen med MNE-Python, BIDS- og NWB-verktøy. Ikke publisert ennå. | OK |
| 13 | `sections[languages].items[1].heading` | C and C++ | C og C++ | OK |
| 14 | `sections[languages].items[1].body` | A C interface on the shared core, with interoperability through LSL and BrainFlow. | Et C-grensesnitt på den felles kjernen, med samspill via LSL og BrainFlow. | OK ("samspill"; alt. "interoperabilitet") |
| 15 | `sections[languages].items[2].heading` | Unity and Unreal | Unity og Unreal | OK |
| 16 | `sections[languages].items[2].body` | Planned, on the same C interface. | Planlagt, på det samme C-grensesnittet. | Faithful to EN, but **EN is inconsistent**: the body says "Planned" while `status` is `roadmap`, so the pill reads "Veikart"/"Roadmap". Route: web-copy. |
| 17 | `sections[languages].evidence[0].text` | MNE-Python had about 308,000 PyPI downloads in the month to 26 September 2026. | MNE-Python hadde rundt 308 000 nedlastinger fra PyPI i måneden fram til 26. september 2026. | A (minor): "i måneden" also means "per month". Suggest "i løpet av måneden fram til 26. september 2026". Number format "308 000" is correct; it uses a normal space, so it can wrap (no-break space recommended). |
| 18 | `sections[licence].heading` | Open where it <em>helps you.</em> | Åpent der det <em>hjelper deg.</em> | OK |
| 19 | `sections[licence].body[0]` | The SDKs, the shared core, the format converters and the pipeline step library are planned as open source (Apache-2.0 proposed), pending the owner's decision. The hosted platform, including the consent ledger and model registry, is proprietary. | SDK-ene, den felles kjernen, formatkonverterne og biblioteket av løypetrinn er planlagt som åpen kildekode (Apache-2.0 er foreslått), i påvente av eierens beslutning. Den hostede plattformen, inkludert samtykkeloggen og modellregisteret, er proprietær. | OK as Norwegian ("formatkonverterne" is the correct definite plural). S: "hostede" is an anglicism common in IT; alt. "den driftede plattformen", "skyplattformen". S: "trinnbiblioteket for løyper". **Stale in EN and NO** (see S5, §6). |
| 20 | `sections[licence].body[1]` | No SDK code is published yet. | Ingen SDK-kode er publisert ennå. | OK |
| 21 | `cta[0].label` | Join early access | Bli med i tidlig tilgang | S/C: see /no/platform #36; suggest "Meld deg på tidlig tilgang". |
| 22 | `cta[0].note` | Early-access list opens soon | Listen for tidlig tilgang åpner snart | OK |
| 23 | `cta[1].label` | See the platform | Se plattformen | OK. Links to EN `/platform`. |

Not counted: `evidence[0].source` ("market/landscape.md §2", shown as text), `code.lines`, `buildSource`. Rendered from
`ui.no.json`: "Bygget, testet internt" (Python item), "Planlagt" (C/C++), "Veikart" (Unity/Unreal).

## 2. Term choices

| EN term | NO on this page | Where | Remark |
|---|---|---|---|
| SDK / SDKs | SDK (et SDK, SDK-et, SDK-er, SDK-ene) | #1–#3, #5, #12, #19, #20 | OK and consistent with `legal/terms.no.json`. **C: /no/security says "programvaresett"** ("programvaresettene våre", `security.no.json` sections never/software). Owner decision. |
| shared core | felles kjerne | #2, #4, #14, #19 | OK |
| C interface | C-grensesnitt | #2, #14, #16 | OK |
| game engines | spillmotorer | #2 | OK |
| provenance handle | proveniens-håndtak | #7 | S, see #7 |
| pinned pipeline version | låst versjon av en løype | #7 | C: "løype" |
| interoperability | samspill | #14 | OK |
| format converters | formatkonvertere | #19 | OK |
| pipeline step library | biblioteket av løypetrinn | #19 | S |
| open source | åpen kildekode | #19 | OK |
| hosted | hostet | #19 | S (also on /no/pricing: "Hostede løyper") |
| consent ledger | samtykkelogg | #19 | OK; same on /no/governance |
| proprietary | proprietær | #19 | OK |
| the owner | eieren | #2, #19 | U: an outside reader cannot tell who "the owner" is (EN has the same problem). Disappears with the `web/copy-licence-tiers` wording. |
| lab | laboratorium | #5 | OK |

## 3. Claims

| ID | Key | NO claim | EN counterpart | EN source / tag | Finding |
|---|---|---|---|---|---|
| S1 | `meta.description`, `items[0]` | Python-SDK bygget og testet internt; ikke publisert | same | built-internal, `docs/hive/M4-REPORT.md step 4.2–4.3` | Same meaning |
| S2 | `meta.description`, `items[1]` | C-grensesnitt for C++ og spillmotorer planlagt | same | status planned (C/C++), roadmap (Unity/Unreal) | Same meaning. EN meta calls game engines "planned"; their item is `roadmap`. |
| S3 | `hero.lede` | alle SDK-er registrerer proveniens likt fordi de deler kjerne | same | **none** | EN design claim, no source. Only one SDK exists (internal). |
| S4 | `evidence[0]` | ca. 308 000 PyPI-nedlastinger, måneden fram til 26.09.2026 | about 308,000 | `market/landscape.md §2` (no grade, no URL) | Same meaning. landscape.md §2 table: "308,276 PyPI downloads/month", pypistats.org "recent" on 2026-09-26. Consistent. |
| S5 | `meta.description`, `licence.body[0]` | lisens venter på eierens beslutning; Apache-2.0 foreslått | same | **none on the page** | **Stale:** `docs/adr/0006-licensing.md` says "Status: **Accepted**" (Apache-2.0 for SDK/core later, proprietary platform). `docs/web/COPY-CLAIMS-RECHECK.md` flags this as open. Fixed on `web/copy-licence-tiers`. Route: web-copy. |
| S6 | `licence.body[0]` | plattformen (samtykkelogg, modellregister) er proprietær | same | none on page; matches ADR 0006 | Same meaning |
| S7 | `licence.body[1]` | ingen SDK-kode er publisert | same | none on page; ADR 0006 says the repo stays all-rights-reserved until the SDK ships | Same meaning |

## 4. Meaning drifts on this page

None in NO versus EN (the "egen" in #6 is negligible). Two **EN-side** issues, both routed to **web-copy**:
the licence status is stale (S5), and Unity/Unreal says "Planned" under a "Roadmap" pill (#16).

## 5. Missing / extra keys

- **Extra in NO:** `reviewed: false` (expected).
- **Missing in NO:** none. Same sections (`example`, `languages`, `licence`), 3 items, 1 evidence, identical
  `code.lines`, `status`/`buildState`/`buildSource`/`source`/`href`/`variant`/`disabled`.
- Same observations as /no/platform §5: CTAs link to EN pages; the code block `aria-label` is English.

## 6. Pending change on `web/copy-licence-tiers` (eb90773, read only)

Commit `09d96cb` changes two strings in each language:

| Key | New EN | New NO | Note |
|---|---|---|---|
| `meta.description` (last sentence) | Apache-2.0 for the SDK and core when the SDK ships; nothing is published yet. | Apache-2.0 for SDK-et og kjernen når SDK-et lanseres; ingenting er publisert ennå. | OK Bokmål. "lanseres" for "ships" is fine. Fixes S5. |
| `sections[licence].body[0]` | … will be open source under Apache-2.0 when the SDK ships. … | … blir åpen kildekode under Apache-2.0 når SDK-et lanseres. … | OK. Fixes S5 and removes "eieren". |

If that branch merges, regenerate rows #2 and #19 and claim S5 of this file.
