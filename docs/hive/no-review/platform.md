# /no/platform: owner review packet

- **Route:** `/no/platform` (built by `apps/web/src/pages/no/[page].astro`; `noindex` while `"reviewed": false`)
- **Sources read at commit `4370f95`:**
  - EN: `packages/content/content/pages/platform.json`
  - NO: `packages/content/content/pages/platform.no.json`
  - Labels: `packages/content/content/ui.no.json` (`statusLabels`, `buildStateLabels`, `statusPill`), `packages/content/content/ui.en.json`
  - Rendering: `apps/web/src/components/PageBody.astro`, `apps/web/src/components/Evidence.astro`, `apps/web/src/components/BuildStatePill.astro`, `packages/ui/src/components/Button.astro`
  - Cited evidence: `market/landscape.md` §3, `market/regulation.md` §4; build sources `docs/hive/M2-REPORT.md`, `M3-REPORT.md`, `M4-REPORT.md`, `M6-REPORT.md`
- **Owner of findings:** not routed (web-copy-2 drafted the NO text; the queen decides routing).

Legend for the "note" column:
**E** = language error (should be fixed) · **D** = meaning drift (NO says more, less or something else than EN) ·
**A** = ambiguity (correct Bokmål, but readers can misread it) · **S** = style preference (optional) ·
**C** = consistency with other NO pages/labels · **U** = unsure, needs owner judgement · **OK** = no remark.
`<em>` markup is kept from the JSON (it renders as italics here).

## 1. Every user-visible string

| # | JSON key path | EN | NO | Note |
|---|---|---|---|---|
| 1 | `meta.title` | Platform · {brand} | Plattform · {brand} | OK |
| 2 | `meta.description` | Hardware-agnostic ingest, versioned and comparable preprocessing pipelines, provenance for every run, and a governed model registry. Built and tested internally; not deployed yet. | Maskinvareuavhengig innlesing, versjonerte og sammenlignbare forbehandlingsløyper, proveniens for hver kjøring og et styrt modellregister. Bygget og testet internt; ikke tatt i bruk ennå. | C: "løype" (see glossary). C: "ikke tatt i bruk" vs "i drift" on /no/security (`security.no.json` note.body) and privacy. |
| 3 | `hero.eyebrow` | Platform | Plattform | OK |
| 4 | `hero.heading` | Reproducible, comparable pipelines, <em>from electrode to model.</em> | Reproduserbare, sammenlignbare løyper, <em>fra elektrode til modell.</em> | C: "løype" |
| 5 | `hero.lede` | Every run is pinned to a pipeline version and records every parameter, version and input hash. Compare pipelines side by side instead of trusting one cleaning default. | Hver kjøring er låst til en versjon av løypen og registrerer hver parameter, versjon og inndata-hash. Sammenlign løyper side om side i stedet for å stole på én standard for rensing. | D (minor): "default" = standardinnstilling; "én standard for rensing" can read as "one standard (norm) for cleaning". Suggest "én standardinnstilling for rensing". |
| 6 | `sections[why].heading` | Preprocessing choices <em>change results.</em> | Valg i forbehandlingen <em>endrer resultatene.</em> | OK |
| 7 | `sections[why].body[0]` | There is no single correct way to clean a neural recording. The published evidence says the choice of pipeline moves the answer, so the pipeline has to be recorded, versioned and comparable. | Det finnes ingen enkelt riktig måte å rense et nevralt opptak på. Publisert forskning viser at valget av løype flytter svaret, så løypen må registreres, versjoneres og kunne sammenlignes. | S: "ingen enkelt riktig måte" is an anglicism; "Det finnes ikke én riktig måte …" reads more naturally. S: "flytter svaret" is literal; "påvirker resultatet" is idiomatic. "viser" (shows) vs "says": same strength in practice, OK. |
| 8 | `sections[why].evidence[0].text` | In a 2025 study, every artifact-correction step reduced decoding performance, while higher high-pass cutoffs increased it. | I en studie fra 2025 reduserte hvert trinn for artefaktkorreksjon dekodingsytelsen, mens høyere høypass-grenser økte den. | S: "høypassgrenser" (one word) or "høyere grensefrekvens for høypassfilteret"; the hyphen is not needed. |
| 9 | `sections[why].evidence[1].text` | A 2025 comparison of 43 preprocessing pipelines found no single best pipeline. | En sammenligning av 43 forbehandlingsløyper fra 2025 fant ingen enkelt beste løype. | A: "fra 2025" attaches to the pipelines, not the comparison. Suggest "En sammenligning fra 2025 av 43 forbehandlingsløyper fant ingen løype som var best i alle tilfeller" or "… fant ingen enkelt løype som var best". |
| 10 | `sections[why].evidence[2].text` | A systematic review of 129 EEG-BCI publications found code or pipeline availability in 20.9% of them. | En systematisk gjennomgang av 129 EEG-BCI-publikasjoner fant at kode eller løype var tilgjengelig i 20,9 % av dem. | OK (decimal comma and space before % are correct Norwegian). S: the space is a normal space, not a no-break space, so "20,9" and "%" can wrap onto two lines. |
| 11 | `sections[ingest].heading` | Hardware-agnostic <em>ingest.</em> | Maskinvareuavhengig <em>innlesing.</em> | OK (alt.: "datainntak") |
| 12 | `sections[ingest].body[0]` | Connectors for EEG, ECoG and microelectrode recordings in open formats. Recordings are stored on standard time-series infrastructure; we compete on provenance, not on storage. | Koblinger for EEG-, ECoG- og mikroelektrodeopptak i åpne formater. Opptakene lagres på standard infrastruktur for tidsserier; vi konkurrerer på proveniens, ikke på lagring. | S: "Koblinger" usually means links/couplings; "Tilkoblinger" or "Konnektorer" is closer to software "connectors". |
| 13 | `sections[ingest].items[0].heading` | Open formats | Åpne formater | OK |
| 14 | `sections[ingest].items[0].body` | EDF/BDF, BrainVision, XDF and BIDS import, with typed errors for corrupt files. NWB import is written but not yet tested. | Import av EDF/BDF, BrainVision, XDF og BIDS, med typede feilmeldinger for ødelagte filer. NWB-import er skrevet, men ikke testet ennå. | D (minor): "typed errors" are distinct error types (M2-REPORT step 2.5: "seeded corrupt-file fuzz gives typed errors"), not error *messages*. Suggest "egne feiltyper for ødelagte filer". S: "Koden for NWB-import er skrevet …". |
| 15 | `sections[ingest].items[1].heading` | Streaming | Strømming | OK |
| 16 | `sections[ingest].items[1].body` | Lab Streaming Layer (LSL) input for real-time sessions, tested on a single host. | Inndata fra Lab Streaming Layer (LSL) for sanntidsøkter, testet på én maskin. | OK |
| 17 | `sections[ingest].items[2].heading` | Existing tools | Eksisterende verktøy | OK |
| 18 | `sections[ingest].items[2].body` | Integrations with MNE-Python, BrainFlow and the BIDS and NWB tooling your lab already uses. | Integrasjoner med MNE-Python, BrainFlow og BIDS- og NWB-verktøyene laboratoriet ditt allerede bruker. | OK |
| 19 | `sections[pipelines].heading` | Versioned pipelines <em>with full provenance.</em> | Versjonerte løyper <em>med full proveniens.</em> | C: "løype" |
| 20 | `sections[pipelines].body[0]` | Versioned preprocessing pipelines with full provenance. Run one, or run a grid of them and see how your results move. | Versjonerte forbehandlingsløyper med full proveniens. Kjør én, eller kjør et rutenett av dem og se hvordan resultatene dine flytter seg. | S: "flytter seg" → "endrer seg". U: "rutenett" (grid) is used in "rutenettsøk" (grid search); acceptable, owner to confirm. |
| 21 | `sections[pipelines].items[0].heading` | Pinned versions | Låste versjoner | OK |
| 22 | `sections[pipelines].items[0].body` | A run names an exact pipeline version, so it can be repeated later. | En kjøring navngir en eksakt versjon av løypen, slik at den kan gjentas senere. | E (word choice): "navngi" means "to give something a name". Here "names" means "specifies": use "angir". |
| 23 | `sections[pipelines].items[1].heading` | Provenance graph | Proveniensgraf | OK |
| 24 | `sections[pipelines].items[1].body` | Inputs, parameters, versions and outputs are linked, from raw recording to trained model. | Inndata, parametere, versjoner og utdata er koblet sammen, fra rått opptak til trent modell. | OK |
| 25 | `sections[pipelines].items[2].heading` | Pipeline grids | Rutenett av løyper | OK (follows #20) |
| 26 | `sections[pipelines].items[2].body` | Run a grid of pipelines on one dataset and see how decoding metrics shift across them. | Kjør et rutenett av løyper på ett datasett og se hvordan dekodingsmålene endrer seg mellom dem. | S/A: "mål" can mean "goal" or "measure"; "måltallene for dekoding" or "dekodingsmetrikkene" is unambiguous. |
| 27 | `sections[pipelines].code.note` | Illustrative API, subject to change | Illustrerende API, kan endres | OK. Code lines and their comments stay English by design (`docs/web/i18n/README.md`). |
| 28 | `sections[models].heading` | A governed <em>model registry.</em> | Et styrt <em>modellregister.</em> | S/U: "styrt" (steered/controlled) is understandable; alt. "Et modellregister <em>med styring.</em>" |
| 29 | `sections[models].body[0]` | Governed model registry, built and tested internally but not deployed: versioned models with provenance, documented intended use and use restrictions. Benchmarks will be published with methods. | Styrt modellregister, bygget og testet internt, men ikke tatt i bruk: versjonerte modeller med proveniens, dokumentert tiltenkt bruk og bruksbegrensninger. Referansemålinger publiseres sammen med metodene. | OK. ("publiseres" in the present is normal for a future commitment in Norwegian; "vil bli publisert" would be stricter.) C: "ikke tatt i bruk" (see #2). |
| 30 | `sections[models].body[1]` | Models whose outputs drive a clinical or assistive device are likely to be regulated as device software in the customer's product. The registry is built to document that boundary, not to blur it. | Modeller der utdataene styrer et klinisk eller assisterende apparat, vil trolig bli regulert som programvare i medisinsk utstyr i kundens produkt. Registeret er laget for å dokumentere den grensen, ikke for å viske den ut. | U/D: "device software" (FDA sense) covers both software *in* a device and software that *is* a device; "programvare i medisinsk utstyr" names only the first. The source (`market/regulation.md` §4) says the model is "likely device software in the customer's product", so "i" is defensible. Owner/legal to confirm the term. C: "apparat" here, "enheter" on /no/pricing, "utstyr" in the regulatory phrase. Comma before "vil" is correct (it closes the embedded clause). |
| 31 | `sections[models].items[0].heading` | Intended use and restrictions | Tiltenkt bruk og begrensninger | OK |
| 32 | `sections[models].items[0].body` | Each model records what it is for and where it must not be deployed. | Hver modell registrerer hva den er ment for, og hvor den ikke skal tas i bruk. | OK |
| 33 | `sections[models].items[1].heading` | Component disclosure | Oversikt over komponenter | OK |
| 34 | `sections[models].items[1].body` | Model components listed for customers' software documentation. | Modellens komponenter listes opp til kundens programvaredokumentasjon. | S: "til bruk i kundens programvaredokumentasjon" is more idiomatic than "listes opp til". |
| 35 | `sections[models].evidence[0].text` | Our planning assumption, not legal advice: outputs that drive a clinical or assistive BCI are likely device software in the customer's product, which then carries the regulatory submission. | Vår planleggingsantakelse, ikke juridisk rådgivning: utdata som styrer et klinisk eller assisterende BCI, er trolig programvare i medisinsk utstyr i kundens produkt, og da er det kunden som står for den regulatoriske søknaden. | OK. In EN the *product* "carries the submission"; NO says the *customer* does, which matches the source ("the customer carries the 510(k), De Novo or PMA burden"). U: same term question as #30. |
| 36 | `cta[0].label` | Join early access | Bli med i tidlig tilgang | S/C: you do not "join" "tidlig tilgang". /no/pricing uses "Bli med på listen for tidlig tilgang". Suggest "Meld deg på tidlig tilgang" on every page. |
| 37 | `cta[0].note` | Early-access list opens soon | Listen for tidlig tilgang åpner snart | OK |
| 38 | `cta[1].label` | Governance | Styring | C: follows the /no/governance title (see glossary). The link goes to the EN `/governance` (see §5). |

Not counted (not translated by design): `sections[*].evidence[*].source` (shown as link text, e.g. "market/landscape.md §3"),
`grade` ("[A]"), `code.lines`, `buildSource` (not rendered). Rendered from `ui.no.json`: status pill "Planlagt"
(items #17/#18, `status: planned`) with hidden prefix "Status:", and build pill "Bygget, testet internt" on the 7
`built-internal` items.

## 2. Term choices

| EN term | NO on this page | Where | Remark |
|---|---|---|---|
| pipeline | løype (forbehandlingsløype) | #2, #4, #5, #7, #9, #10, #19, #20, #22, #25, #26 | **Owner decision.** Not standard Norwegian for a processing pipeline ("løype" = trail/ski track). Common alternatives: "pipeline" (loanword), "prosesseringskjede", "(for)behandlingskjede". Used on /no/sdks, /no/governance, /no/pricing too. |
| preprocessing | forbehandling | #2, #6, #9, #20 | OK |
| ingest | innlesing | #2, #11 | OK (alt. "datainntak") |
| provenance | proveniens | #2, #19, #23 … | OK; matches /no/security ("Byggeproveniens") and `docs/web/i18n/README.md` |
| run (noun) | kjøring | #2, #5, #22 | OK |
| pinned (version) | låst (versjon) | #5, #21 | OK |
| input hash | inndata-hash | #5 | OK (a hyphen is acceptable with the loanword "hash") |
| input / output | inndata / utdata | #16, #24, #30 | OK |
| grid (of pipelines) | rutenett | #20, #25, #26 | U, see #20 |
| decoding performance / metrics | dekodingsytelse / dekodingsmål | #8, #26 | S, see #26 |
| artifact correction | artefaktkorreksjon | #8 | OK |
| high-pass cutoff | høypass-grense | #8 | S, see #8 |
| recording | opptak | #7, #12 | OK |
| connectors | koblinger | #12 | S, see #12 |
| streaming | strømming | #15 | OK |
| typed errors | typede feilmeldinger | #14 | D, see #14 |
| host | maskin | #16 | OK |
| governed model registry | styrt modellregister | #2, #28, #29 | S/U |
| intended use | tiltenkt bruk | #29, #31 | OK |
| use restrictions | bruksbegrensninger | #29 | OK; the same on /no/governance |
| benchmarks | referansemålinger | #29 | OK |
| device (clinical/assistive) | apparat | #30 | C: "enheter" on /no/pricing, /no/security |
| device software | programvare i medisinsk utstyr | #30, #35 | U, see #30 |
| deployed / not deployed | tatt i bruk / ikke tatt i bruk | #2, #29, #32 | C: /no/security and privacy say "i drift" |
| built and tested internally | bygget og testet internt | #2, #29 | OK; pill label "Bygget, testet internt" (`ui.no.json`) mirrors the EN pill |
| early access | tidlig tilgang | #36, #37 | C, see #36 |
| governance | styring | #38 | Owner decision (glossary) |
| BCI | BCI (neuter: "et … BCI") | #35 | OK |

## 3. Claims (numbers, dates, standards, laws, status, capabilities)

| ID | Key | NO claim | EN counterpart | EN source / tag | Finding |
|---|---|---|---|---|---|
| P1 | `meta.description`, `sections[models].body[0]` | Bygget og testet internt; ikke tatt i bruk ennå | Built and tested internally; not deployed yet | backed by the item `buildSource`s below | Same meaning |
| P2 | `hero.lede` | Hver kjøring … registrerer hver parameter, versjon og inndata-hash | records every parameter, version and input hash | no tag on the lede; items P9/P10 carry M3-REPORT step 3.1/3.2 | Same meaning. EN capability claim in the hero has no tag of its own. |
| P3 | `evidence[0]` | studie fra 2025; alle artefaktkorreksjonstrinn senket dekodingsytelsen; høyere høypass økte den | 2025 study … | `market/landscape.md §3`, doi:10.1038/s42003-025-08464-3, grade A | Same meaning; matches landscape.md §3 item 2 (Kessler et al. 2025). |
| P4 | `evidence[1]` | 43 løyper, 2025, ingen enkelt beste | 43 pipelines, 2025, no single best | `market/landscape.md §3`, doi:10.1111/psyp.70197, grade A | Same meaning (ambiguity A, see #9). Matches landscape.md (Huang et al. 2025). |
| P5 | `evidence[2]` | 129 publikasjoner; 20,9 % | 129 publications; 20.9% | `market/landscape.md §3`, doi:10.3390/s26175562, grade A | Same meaning; matches landscape.md §3 item 1 (Peksa et al., *Sensors* 2026). |
| P6 | `sections[ingest].body[0]` | Koblinger for EEG, ECoG og mikroelektrodeopptak; lagring på standard tidsserie-infrastruktur | same | **none** (no status, no buildState) | EN claim with no source/tag. The item cards carry tags; the section body does not. |
| P7 | `items[0]` Åpne formater | EDF/BDF, BrainVision, XDF, BIDS import; NWB skrevet, ikke testet | same | built-internal, `docs/hive/M2-REPORT.md step 2.5` | D (minor) "typede feilmeldinger", see #14. M2 step 2.5 lists EDF, BDF, BrainVision, XDF, BIDS and does not list NWB, which fits "not yet tested". |
| P8 | `items[1]` Strømming | LSL, testet på én maskin | tested on a single host | built-internal, M2 step 2.7; M4 step 4.4 | Same meaning; M4 step 4.4 says "pass on one host". |
| P9 | `items[2]` Eksisterende verktøy | integrasjoner med MNE-Python, BrainFlow, BIDS, NWB | same | status planned | Same meaning |
| P10 | `pipelines.items[0]` | kjøring angir eksakt versjon | same | built-internal, M3 step 3.2 | E "navngir", meaning intact |
| P11 | `pipelines.items[1]` | proveniensgraf fra rått opptak til trent modell | same | built-internal, M3 step 3.1; M6 step 6.1 | Same meaning |
| P12 | `pipelines.items[2]` | rutenett av løyper | same | built-internal, M3 step 3.6 | Same meaning |
| P13 | `models.body[0]` | Referansemålinger publiseres sammen med metodene | Benchmarks will be published with methods | **none** | Commitment with no source (EN and NO). |
| P14 | `models.body[1]` + `evidence[0]` | trolig regulert som programvare i medisinsk utstyr; kunden står for søknaden | likely device software; product carries submission | `market/regulation.md §4` (no grade) | U on the term (see #30). Planning assumption is labelled "ikke juridisk rådgivning" in NO too. |
| P15 | `models.items[0]` | tiltenkt bruk og hvor modellen ikke skal tas i bruk | same | built-internal, M6 step 6.2 | Same meaning |
| P16 | `models.items[1]` | komponentoversikt til kundens programvaredokumentasjon | same | built-internal, M6 step 6.5 | Same meaning |
| P17 | `cta[0].note` | Listen … åpner snart | opens soon | none (status statement) | Same meaning |

Build sources were checked for existence only (each cited report has a row for the cited step at `4370f95`). They
were not re-audited here; that is H1-c claims-audit-2's job.

## 4. Meaning drifts on this page

1. #5 "én standard for rensing" (default → standard/norm), minor.
2. #14 "typede feilmeldinger" (typed errors → typed error messages), minor.
3. #30/#35 "programvare i medisinsk utstyr" for "device software", **unsure**, owner/legal.

No NO string on this page claims a status or capability beyond its EN string.

## 5. Missing / extra keys

- **Extra in NO:** `reviewed: false` (expected; only the owner flips it).
- **Missing in NO:** none. Same sections (`why`, `ingest`, `pipelines`, `models`), same item and evidence counts
  (3/3/3/2 items; 3 + 1 evidence), same `status`/`buildState`/`buildSource`/`source`/`sourceUrl`/`grade`/`href`/
  `variant`/`disabled` values, identical `code.lines`.
- **Observation (not a key issue):** the CTAs link to EN pages (`/pricing#early-access`, `/governance`).
  `Button.astro` renders `cta.href` as is and does not call `localiseHref`, so this stays true even after the owner
  marks the pages reviewed. Route: queen to decide (web-a11y owns routes per `docs/web/i18n/README.md`).
- **Observation:** the code block's `aria-label` comes from `site.json` `aria.codeSample` = "Illustrative Python
  example" (English) and is not locale-aware, so screen readers hear English on /no/platform and /no/sdks.
