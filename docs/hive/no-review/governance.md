# /no/governance: owner review packet

- **Route:** `/no/governance` (built by `apps/web/src/pages/no/[page].astro`; `noindex` while `"reviewed": false`)
- **Sources read at commit `4370f95`:**
  - EN: `packages/content/content/pages/governance.json`
  - NO: `packages/content/content/pages/governance.no.json`
  - Labels: `packages/content/content/ui.no.json`; cross-check `security.no.json`, `legal/privacy.no.json`
  - Cited evidence: `market/regulation.md` §1 and §5, `market/landscape.md` §3; build sources `docs/hive/M5-REPORT.md`,
    `docs/hive/M6-REPORT.md`, `services/platform/tests/governance/test_gov_rules.py`,
    `services/platform/tests/governance/test_gov_audit_integrity.py` (existence checked)
- **Owner of findings:** not routed (the queen decides).

Legend: **E** language error · **D** meaning drift · **A** ambiguity · **S** style preference · **C** consistency ·
**U** unsure · **OK** no remark. `<em>` markup is kept from the JSON.

## 1. Every user-visible string

| # | JSON key path | EN | NO | Note |
|---|---|---|---|---|
| 1 | `meta.title` | Governance · {brand} | Styring · {brand} | Owner decision on "Styring" (glossary). |
| 2 | `meta.description` | Per-jurisdiction classification, a versioned consent ledger, deletion that follows data into derivatives and models, and use restrictions on models. Built and tested internally; not deployed yet. | Klassifisering per jurisdiksjon, en versjonert samtykkelogg, sletting som følger dataene inn i avledede data og modeller, og bruksbegrensninger på modeller. Bygget og testet internt; ikke tatt i bruk ennå. | OK. C: "ikke tatt i bruk" vs "i drift" (/no/security). |
| 3 | `hero.eyebrow` | Governance | Styring | see #1 |
| 4 | `hero.heading` | Govern neural data <em>wherever it flows.</em> | Styr nevrale data <em>uansett hvor de havner.</em> | S: "havner" (ends up) vs "flows"; "uansett hvor de flyter" is closer but less natural. Acceptable. |
| 5 | `hero.lede` | Classification, consent and deletion, tracked on the same provenance graph as your pipelines, so a withdrawal reaches every derivative and model built from the data. | Klassifisering, samtykke og sletting spores på den samme proveniensgrafen som løypene dine, slik at en tilbaketrekking når alle avledede data og modeller som er bygget på dataene. | S: "en tilbaketrekking av samtykke" is clearer than bare "en tilbaketrekking". C: "løype". |
| 6 | `banner` | Not legal advice. This is a research summary for product planning. Engage qualified counsel before relying on it. | Ikke juridisk rådgivning. Dette er et forskningssammendrag for produktplanlegging. Kontakt kvalifisert advokat før du legger det til grunn. | OK ("Kontakt kvalifisert advokat" without an article is normal instruction register). |
| 7 | `sections[why-now].heading` | The laws exist, and <em>they disagree.</em> | Lovene finnes, og <em>de er uenige.</em> | S: "uenige" is normally said of people. "… og <em>de spriker.</em>" is idiomatic. |
| 8 | `sections[why-now].body[0]` | Three US states have added neural data to the sensitive data their privacy laws protect, and a peer-reviewed review reports a fourth (Montana). Their definitions differ. One EEG or EMG recording can be neural data in one state and not in another, so classification has to happen per channel and per derived feature. | Tre amerikanske delstater har lagt nevrale data til de sensitive dataene personvernlovene deres beskytter, og en fagfellevurdert oversiktsartikkel rapporterer en fjerde (Montana). Definisjonene er ulike. Ett EEG- eller EMG-opptak kan være nevrale data i én delstat og ikke i en annen, så klassifiseringen må gjøres per kanal og per avledet egenskap. | OK |
| 9 | `sections[why-now].evidence[0].text` | Colorado (effective 7 Aug 2024), California (Ch. 887, 28 Sep 2024) and Connecticut (signed 24 Jun 2025; amendment sections effective July 1, 2026) have neural-data provisions. | Colorado (i kraft 7. aug. 2024), California (Ch. 887, 28. sep. 2024) og Connecticut (signert 24. jun. 2025; endringsbestemmelsene i kraft 1. juli 2026) har bestemmelser om nevrale data. | OK. Month abbreviations "aug.", "sep.", "jun." are valid Bokmål. S: "Ch. 887" is left in English; "kap. 887" or "Chapter 887" (as a name). EN mixes date styles ("24 Jun 2025" vs "July 1, 2026"); NO is consistent. |
| 10 | `sections[why-now].evidence[1].text` | A peer-reviewed review reports that Montana adopted SB 163 in May 2025 to regulate neurological data. We have not yet checked the statute text. | En fagfellevurdert oversiktsartikkel rapporterer at Montana vedtok SB 163 i mai 2025 for å regulere nevrologiske data. Vi har ennå ikke kontrollert selve lovteksten. | OK |
| 11 | `sections[why-now].evidence[2].text` | Colorado and California cover the central or peripheral nervous system; Connecticut covers the central nervous system only; California excludes data inferred from non-neural information. | Colorado og California omfatter det sentrale eller perifere nervesystemet; Connecticut omfatter bare sentralnervesystemet; California utelater data som er utledet av ikke-nevral informasjon. | OK. S: "unntar" is the more legal verb than "utelater". |
| 12 | `sections[why-now].evidence[3].text` | No neural-specific privacy tool was found among the software tools reviewed. | Blant programvareverktøyene som ble gjennomgått, fant vi ingen personvernverktøy laget spesielt for nevrale data. | OK |
| 13 | `sections[capabilities].heading` | What the governance layer <em>is built to do.</em> | Hva styringslaget <em>er bygget for å gjøre.</em> | OK |
| 14 | `sections[capabilities].body[0]` | Each capability below is built and tested internally. None is deployed or available to customers yet. | Hver funksjon nedenfor er bygget og testet internt. Ingen av dem er tatt i bruk eller tilgjengelig for kunder ennå. | OK (singular agreement after "ingen" is correct). |
| 15 | `sections[capabilities].items[0].heading` | Per-jurisdiction classification | Klassifisering per jurisdiksjon | OK |
| 16 | `sections[capabilities].items[0].body` | Classify every channel and derived feature against the Colorado, California and Connecticut definitions, and record the reasoning. Montana is shown as not evaluated until its statute text is verified. | Klassifiser hver kanal og hver avledet egenskap mot definisjonene i Colorado, California og Connecticut, og registrer begrunnelsen. Montana vises som ikke vurdert til lovteksten er verifisert. | S: "inntil" or "før" is the written-register form for the time clause ("til" is colloquial). |
| 17 | `sections[capabilities].items[1].heading` | Versioned consent ledger | Versjonert samtykkelogg | OK |
| 18 | `sections[capabilities].items[1].body` | Capture opt-in consent with its version and scope, and keep an audit trail of every change. | Registrer aktivt samtykke med versjon og omfang, og behold et revisjonsspor over hver endring. | OK ("aktivt samtykke" is a good rendering of opt-in). S: "… av alle endringer". |
| 19 | `sections[capabilities].items[2].heading` | Deletion that follows the data | Sletting som følger dataene | OK |
| 20 | `sections[capabilities].items[2].body` | Propagate consent withdrawal to raw data, derivatives and trained models, and flag models that need retraining. | Før tilbaketrukket samtykke videre til rådata, avledede data og trente modeller, og merk modeller som må trenes på nytt. | A: grammatical (imperative of "føre"), but a sentence that starts with "Før" is first read as "Before …". Suggest "La tilbaketrekking av samtykke gjelde for rådata, avledede data og trente modeller, …" or "Send tilbaketrekkingen videre til …". |
| 21 | `sections[capabilities].items[3].heading` | Limit-use flag | Merke for begrenset bruk | OK |
| 22 | `sections[capabilities].items[3].body` | Flag data that counts as sensitive personal information in California, where consumers have the right to limit its use. | Merk data som California regner som sensitive personopplysninger, der forbrukere har rett til å begrense bruken. | OK. ("sensitive personopplysninger" is right for the CCPA term; do not swap in the GDPR term "særlige kategorier".) |
| 23 | `sections[capabilities].items[4].heading` | Model use restrictions | Bruksbegrensninger på modeller | OK |
| 24 | `sections[capabilities].items[4].body` | Attach use-restriction metadata to models, for example for emotion inference in EU workplace and education settings. | Knytt metadata om bruksbegrensninger til modeller, for eksempel for gjenkjenning av følelser på arbeidsplasser og i utdanning i EU. | D (minor) + C: "gjenkjenning av følelser" = emotion *recognition*; EN says emotion *inference*, and the evidence on this page (#29) says "utleder følelser". The AI Act uses both terms for different things. Suggest "utledning av følelser". |
| 25 | `sections[capabilities].items[5].heading` | Audit export | Revisjonseksport | OK |
| 26 | `sections[capabilities].items[5].body` | Export the audit trail, including classification changes and deletion events, and signed deletion certificates for reviewers and counsel. | Eksporter revisjonssporet, inkludert endringer i klassifisering og slettehendelser, og signerte slettebevis for granskere og advokater. | D (minor): "granskere" suggests investigators. /no/security uses "revisorene dine". Suggest "for revisorer og advokater" or "for de som gjennomgår dem og advokater". |
| 27 | `sections[eu].heading` | EU rules <em>reach models too.</em> | EU-reglene <em>når også modellene.</em> | OK |
| 28 | `sections[eu].body[0]` | The EU AI Act restricts some uses of models regardless of how the data was collected, so use restrictions belong on the model record. | EUs KI-forordning begrenser enkelte bruksområder for modeller uansett hvordan dataene ble samlet inn, så bruksbegrensninger hører hjemme i modellens register. | D (minor): "i modellens register" = "in the model's register"; EN means the model's *record* (its entry). Suggest "i registeroppføringen for modellen" or "i modellposten". "KI-forordningen" is the official Norwegian short name, OK. |
| 29 | `sections[eu].evidence[0].text` | EU AI Act Art. 5(1)(f), applicable from 2 Feb 2025, bans AI that infers emotions in workplace and education settings, except for medical or safety reasons. | KI-forordningen art. 5 nr. 1 bokstav f, gjeldende fra 2. feb. 2025, forbyr KI som utleder følelser på arbeidsplasser og i utdanningsinstitusjoner, unntatt av medisinske eller sikkerhetsmessige grunner. | OK (EEA citation style "art. 5 nr. 1 bokstav f" is correct). NO "utdanningsinstitusjoner" is narrower than EN "education settings" but **matches the Article text** ("workplace and education institutions", `market/regulation.md` §5); the EN is the looser one. U: "gjeldende fra 2. feb. 2025" is the EU date; a Norwegian reader may take it as the date it applies in Norway. Whether and when the AI Act applies in Norway via the EEA was **not verified** here. Consider "i EU". |
| 30 | `cta[0].label` | Read the law tracker | Les lovoversikten | OK. Links to EN `/law-tracker` (no NO version exists); consider "(på engelsk)". |
| 31 | `cta[1].label` | Join early access | Bli med i tidlig tilgang | S/C, see /no/platform #36 |
| 32 | `cta[1].note` | Early-access list opens soon | Listen for tidlig tilgang åpner snart | OK |

Not counted: `evidence[*].source` (shown), `grade` ("[A]", "[B]"), `buildSource` (not rendered). Rendered from
`ui.no.json`: "Bygget, testet internt" on all 6 capability items.

## 2. Term choices

| EN term | NO on this page | Where | Remark |
|---|---|---|---|
| governance / governance layer | styring / styringslaget | #1, #3, #13 | Owner decision (glossary) |
| neural data | nevrale data | #4, #8, #9 | OK; matches /no/security and `docs/web/i18n/README.md` |
| per-jurisdiction classification | klassifisering per jurisdiksjon | #2, #15 | OK |
| consent ledger | samtykkelogg | #2, #17 | OK |
| opt-in consent | aktivt samtykke | #18 | OK |
| consent withdrawal | tilbaketrekking (av samtykke), tilbaketrukket samtykke | #5, #20 | OK; A in #20 |
| audit trail | revisjonsspor | #18, #26 | OK; /no/security uses "Revisjonsspor" (and "revisjonslogg" for audit log) |
| audit export | revisjonseksport | #25 | OK |
| deletion certificate | slettebevis | #26 | OK; matches /no/security |
| derivatives / derived feature | avledede data / avledet egenskap | #2, #5, #8, #16 | OK |
| sensitive personal information (CCPA) | sensitive personopplysninger | #22 | OK |
| use restrictions | bruksbegrensninger | #2, #23, #24, #28 | OK |
| emotion inference | gjenkjenning av følelser (#24) / utleder følelser (#29) | #24, #29 | **Inconsistent within the page**, see #24 |
| EU AI Act | KI-forordningen / EUs KI-forordning | #28, #29 | OK (official Norwegian short name) |
| peer-reviewed review | fagfellevurdert oversiktsartikkel | #8, #10 | OK |
| statute text | lovtekst | #10, #16 | OK |
| effective / signed | i kraft / signert | #9 | OK |
| reviewers and counsel | granskere og advokater | #26 | D (minor), see #26 |
| law tracker | lovoversikt | #30 | OK |
| model record | modellens register | #28 | D (minor), see #28 |

## 3. Claims

| ID | Key | NO claim | EN counterpart | EN source / tag | Finding |
|---|---|---|---|---|---|
| G1 | `meta.description`, `capabilities.body[0]` | bygget og testet internt; ikke i bruk eller tilgjengelig for kunder | same | items G7–G12 | Same meaning |
| G2 | `why-now.body[0]` | tre amerikanske delstater + Montana rapportert av en fagfellevurdert artikkel | same | backed by G3/G4 | Same meaning |
| G3 | `evidence[0]` | Colorado i kraft 7.8.2024; California Ch. 887, 28.9.2024; Connecticut signert 24.6.2025, endringer i kraft 1.7.2026 | same | `market/regulation.md §1`, grade A | Same meaning. regulation.md §1: Colorado HB24-1058 effective 7 Aug 2024; California SB 1223 chaptered 28 Sep 2024, Ch. 887; Connecticut PA 25-113 signed 24 Jun 2025, "Effective July 1, 2026". All match. |
| G4 | `evidence[1]` | Montana SB 163, mai 2025; lovteksten ikke kontrollert | same | `market/regulation.md §1` (no grade) | Same meaning, same caveat. Source: Cabrera et al., *Bioethics* 2026 (secondary). |
| G5 | `evidence[2]` | CO/CA: sentrale eller perifere; CT: bare sentrale; CA unntar data utledet av ikke-nevral informasjon | same | `market/regulation.md §1`, grade A | Same meaning; matches regulation.md §1 "definitions do not agree". |
| G6 | `evidence[3]` | ingen personvernverktøy for nevrale data blant gjennomgåtte verktøy | same | `market/landscape.md §3` (no grade) | Same meaning; matches landscape.md §3 item 4. |
| G7 | `items[0]` | klassifisering mot CO/CA/CT; Montana "ikke vurdert" | same | built-internal, M5 step 5.2 | Same meaning |
| G8 | `items[1]` | samtykkelogg med versjon, omfang, revisjonsspor | same | built-internal, M5 step 5.3 | Same meaning |
| G9 | `items[2]` | sletting til rådata, avledede data, modeller; merk for ny trening | same | built-internal, M5 step 5.5 | Same meaning (A in wording) |
| G10 | `items[3]` | merke for Californias sensitive personopplysninger | same | built-internal, M5 step 5.2; `test_gov_rules.py` | Same meaning |
| G11 | `items[4]` | metadata om bruksbegrensninger, f.eks. følelser på arbeidsplass/utdanning i EU | same | built-internal, M6 step 6.2 | D (minor) recognition vs inference |
| G12 | `items[5]` | eksport av revisjonsspor og signerte slettebevis | same | built-internal, M5 step 5.5; `test_gov_audit_integrity.py` | Same meaning (D minor on "granskere") |
| G13 | `eu.body[0]` | KI-forordningen begrenser bruk uansett innsamling | same | backed by G14 | Same meaning |
| G14 | `eu.evidence[0]` | art. 5 nr. 1 bokstav f, gjeldende fra 2.2.2025, forbyr følelsesutledning på arbeidsplass og i utdanningsinstitusjoner, unntak medisinsk/sikkerhet | same | `market/regulation.md §5`, artificialintelligenceact.eu/article/5, grade B | NO follows the Article more closely than EN ("institutions"). U: EEA applicability in Norway not verified. |
| G15 | `banner` | ikke juridisk rådgivning | same | none (disclaimer) | Same meaning |

## 4. Meaning drifts on this page

1. #24 "gjenkjenning av følelser" (recognition) vs EN "emotion inference", minor; also inconsistent with #29.
2. #26 "granskere" for "reviewers", minor.
3. #28 "modellens register" for "model record", minor.
4. #29 "gjeldende fra 2. feb. 2025" without "i EU", **unsure** (Norwegian reader context; EEA status not checked).

The NO never claims more status than EN. In #29 the NO is *more* precise than the EN; EN "education settings" is
looser than the Article, so EN copy could tighten it (no owner assigned).

## 5. Missing / extra keys

- **Extra in NO:** `reviewed: false` (expected).
- **Missing in NO:** none. `banner` present; sections `why-now` (4 evidence), `capabilities` (6 items), `eu`
  (1 evidence); all tags identical.
- Same observation as /no/platform §5: CTAs link to EN pages.
