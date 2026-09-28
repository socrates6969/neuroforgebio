# /no/pricing: owner review packet

> **PROVISIONAL: web-copy-2 is changing pricing.json/pricing.no.json on web/copy-licence-tiers (eb90773); regenerate
> after it merges.** §1–§5 review the text at `4370f95`. §6 reviews the pending branch text (read only), so the owner
> can check both now.

- **Route:** `/no/pricing` (built by `apps/web/src/pages/no/[page].astro`; `noindex` while `"reviewed": false`)
- **Sources read at commit `4370f95`:**
  - EN: `packages/content/content/pages/pricing.json`
  - NO: `packages/content/content/pages/pricing.no.json`
  - Rendering: `apps/web/src/pages/no/[page].astro` (renders `earlyAccessNote`), `apps/web/src/pages/[page].astro` (EN renders `EarlyAccessForm`)
  - Cross-check: `security.no.json`, `legal/privacy.no.json`, `ui.no.json`, `investor/PRICING.md`
  - Pending: `git show web/copy-licence-tiers:packages/content/content/pages/pricing{,.no}.json` @ `eb90773`
- **Findings on this page are routed to: web-copy-2** (label only; nobody was contacted).

Legend: **E** language error · **D** meaning drift · **A** ambiguity · **S** style preference · **C** consistency ·
**U** unsure · **OK** no remark. `<em>` markup is kept from the JSON.

## 1. Every user-visible string (at 4370f95)

| # | JSON key path | EN | NO | Note |
|---|---|---|---|---|
| 1 | `meta.title` | Pricing · {brand} | Priser · {brand} | OK |
| 2 | `meta.description` | Free for individual researchers and students, a banded subscription for startups, custom for enterprise. No final prices yet. | Gratis for enkeltforskere og studenter, abonnement i trinn for oppstartsselskaper, tilpasset for større virksomheter. Ingen endelige priser ennå. | S: "tilpasset" alone is vague for "custom (pricing)"; "skreddersydd pris" or "pris etter avtale". C: "større virksomheter" here, "Virksomhet" in #13, "bedriftskunder" on /no/security. |
| 3 | `hero.eyebrow` | Pricing | Priser | OK |
| 4 | `hero.heading` | Free for researchers. <em>Fair for startups.</em> | Gratis for forskere. <em>Rettferdig for oppstartsselskaper.</em> | S: for prices, "rimelig" is the idiomatic word; "rettferdig" (just) is literal. |
| 5 | `hero.lede` | No prices are final and nothing on this page is an offer. We set prices after discovery interviews with the teams who would pay them. | Ingen priser er endelige, og ingenting på denne siden er et tilbud. Vi setter prisene etter intervjuer med teamene som skal betale dem. | D (minor): "som skal betale dem" = "who will pay them" (definite); EN "who would pay" is hypothetical. Suggest "som ville betalt dem" or "som kommer til å betale". "discovery" is dropped; fine. |
| 6 | `sections[tiers].heading` | Three tiers, <em>one platform.</em> | Tre nivåer, <em>én plattform.</em> | OK (changes on the branch, §6) |
| 7 | `sections[tiers].body[0]` | Every tier runs on the same provenance graph. Higher tiers add hosting, governance and the controls regulated teams need. | Alle nivåer kjører på den samme proveniensgrafen. Høyere nivåer legger til drift, styring og kontrollene regulerte team trenger. | OK ("drift" for hosting is fine here) |
| 8 | `sections[tiers].items[0].heading` | Academic: free for individuals | Akademisk: gratis for enkeltpersoner | OK |
| 9 | `sections[tiers].items[0].body` | For individual researchers and students, with fair-use limits. The Python SDK (licence pending), local provenance, and BIDS, NWB and LSL integrations. Labs and core facilities are planned for a separate paid plan; pricing at launch. | For enkeltforskere og studenter, med grenser for rimelig bruk. Python-SDK-et (lisens avventer), lokal proveniens og integrasjoner med BIDS, NWB og LSL. Laboratorier og kjernefasiliteter er planlagt på en egen betalt plan; prising ved lansering. | **E:** "(lisens avventer)": "avvente" is transitive and needs an object ("avventer hva?"). Use "(lisensen er ikke avklart)" or "(lisens ikke avgjort)". S: "er planlagt på en egen betalt plan" repeats plan/planlagt; "får en egen betalt plan (planlagt)". OK: "kjernefasiliteter" is the term Norwegian universities use. |
| 10 | `sections[tiers].items[1].heading` | Startup: banded subscription | Oppstart: abonnement i trinn | OK |
| 11 | `sections[tiers].items[1].body` | For seed-stage neurotech teams. Hosted pipelines, the consent and deletion ledger for core US states, and SSO. A subscription priced in bands of data subjects and devices; pricing at launch. | For nevroteknologiselskaper i tidlig fase. Hostede løyper, samtykke- og sletteloggen for de sentrale amerikanske delstatene, og SSO. Et abonnement priset i trinn etter antall forsøkspersoner og enheter; prising ved lansering. | **A/D:** "de sentrale amerikanske delstatene" can be read as the geographically *central* US states. EN "core" = the main ones (CO, CA, CT). Suggest "de viktigste amerikanske delstatene" or name them. D (minor): "i tidlig fase" is broader than "seed-stage" ("i såkornfasen"). U/D: "forsøkspersoner" (research participants) for "data subjects": a startup's data subjects may be users or patients. GDPR Norwegian uses "de registrerte". /no/security also uses "forsøksperson". Owner decision. |
| 12 | `sections[tiers].items[2].heading` | Enterprise: custom | Virksomhet: tilpasset | S/C: "Virksomhet" (a business, any size) does not say "enterprise tier"; "tilpasset" is vague. Options: keep "Enterprise", or "Storbedrift: pris etter avtale". /no/security and privacy say "bedriftskunder". Owner decision. |
| 13 | `sections[tiers].items[2].body` | For organizations with regulated data. BAA available for enterprise (planned), SSO and advanced RBAC, and single-tenant or on-prem deployment on the roadmap. | For organisasjoner med regulerte data. BAA tilgjengelig for virksomheter (planlagt), SSO og avansert rollebasert tilgangsstyring, og drift på egen instans eller lokalt på veikartet. | **A:** "lokalt på veikartet" reads as "locally on the roadmap". Suggest "…, og på veikartet: drift på egen instans eller i kundens eget datasenter". S: "lokalt" is weak for on-prem; "i eget datasenter"/"hos kunden". C: "BAA" is unexplained; /no/security says "databehandleravtale etter HIPAA (BAA)". |
| 14 | `sections[why-no-prices].heading` | Why there are <em>no prices yet.</em> | Hvorfor det <em>ikke finnes priser ennå.</em> | OK |
| 15 | `sections[why-no-prices].body[0]` | We would rather publish a price we have tested than one we guessed. Early-access members will see pricing first and can help shape it. | Vi vil heller publisere en pris vi har testet enn en vi har gjettet. Medlemmer av tidlig tilgang ser prisene først og kan være med på å forme dem. | S: "Medlemmer av tidlig tilgang" is awkward; "De som er med på listen for tidlig tilgang, ser prisene først …". |
| 16 | `sections[early-access].heading` | Join the <em>early-access list.</em> | Bli med på <em>listen for tidlig tilgang.</em> | OK. C: CTAs on the other pages say "Bli med i tidlig tilgang". |
| 17 | `sections[early-access].body[0]` | The early-access list opens soon. We are not collecting any email addresses until our privacy policy is published. | Listen for tidlig tilgang åpner snart. Vi samler ikke inn e-postadresser før personvernerklæringen vår er publisert. | OK ("personvernerklæring" matches `ui.no.json` legal.privacy) |
| 18 | `earlyAccessNote.text` (NO only) | (none) | Skjemaet for tidlig tilgang finnes foreløpig bare på engelsk. | OK. EN `/pricing` renders `EarlyAccessForm`, so a form exists, but it is disabled until the list opens. S: "… finnes foreløpig bare på engelsk, og det er ikke åpnet ennå." |
| 19 | `earlyAccessNote.linkLabel` (NO only) | (none) | Se skjemaet på engelsk | OK; link `/pricing#early-access`, `hreflang="en"` |

Rendered from `ui.no.json`: "Planlagt" pill (with hidden prefix "Status:") on all three tiers. There are no CTAs on
this page.

## 2. Term choices

| EN term | NO on this page | Where | Remark |
|---|---|---|---|
| pricing / prices | priser / prising | #1, #9, #11 | OK ("prising ved lansering" is understandable; "priser kommer ved lansering" is smoother) |
| tier | nivå | #6, #7 | OK |
| banded subscription | abonnement i trinn | #2, #10, #11 | OK (alt. "trinnvis abonnement") |
| custom (price) | tilpasset | #2, #12 | S, see #12 |
| enterprise | virksomhet / større virksomheter | #2, #12, #13 | **C: /no/security + privacy say "bedriftskunder"**. Owner decision. |
| startup | oppstartsselskap / oppstart | #2, #4, #10 | OK |
| seed-stage | i tidlig fase | #11 | D minor |
| fair-use limits | grenser for rimelig bruk | #9 | OK |
| core facilities | kjernefasiliteter | #9 | OK |
| data subjects | forsøkspersoner | #11 | U/D, owner decision |
| devices | enheter | #11 | OK; C: "apparat" on /no/platform |
| hosted pipelines | hostede løyper | #11 | S ("hostet") + C ("løype") |
| consent and deletion ledger | samtykke- og slettelogg | #11 | OK |
| SSO | SSO | #11, #13 | S: /no/security writes "Felles pålogging (SSO)" on first use |
| RBAC | rollebasert tilgangsstyring | #13 | OK |
| BAA | BAA | #13 | C: explain as on /no/security |
| single-tenant | (drift på) egen instans | #13 | OK |
| on-prem | lokalt | #13 | S/A, see #13 |
| roadmap | veikart | #13 | OK (matches the status label) |
| early access / early-access list | tidlig tilgang / listen for tidlig tilgang | #15–#19 | C, see #16 |
| privacy policy | personvernerklæring | #17 | OK |

## 3. Claims (at 4370f95)

| ID | Key | NO claim | EN counterpart | EN source / tag | Finding |
|---|---|---|---|---|---|
| R1 | `meta.description`, `hero.lede` | ingen endelige priser; ingenting er et tilbud | same | none (statement) | Same meaning |
| R2 | `tiers.heading` | tre nivåer | three tiers | none on page | Same meaning. Becomes five on the branch. |
| R3 | `items[0]` | Akademisk gratis; Python-SDK (lisens uavklart); lokal proveniens; BIDS/NWB/LSL; labs får egen betalt plan | same | status planned; no source | Same meaning (E in wording). EN has no source; `investor/PRICING.md` §3.1–3.2 is the obvious one. Licence "pending" is stale versus ADR 0006 (Accepted). |
| R4 | `items[1]` | oppstart; hostede løyper; logg for sentrale delstater; SSO; trinn etter forsøkspersoner og enheter | same | status planned; no source | A/D, see #11 |
| R5 | `items[2]` | BAA (planlagt), SSO, RBAC; egen instans/lokalt på veikartet | same | status planned; no source | A, see #13. The item status is `planned`, while the text puts single-tenant/on-prem on the roadmap (EN has the same mix). |
| R6 | `why-no-prices.body[0]` | early-access members see prices first | same | none | Same meaning |
| R7 | `early-access.body[0]` | ingen e-postadresser samles inn før personvernerklæringen er publisert | same | none | Same meaning. Consistent with the disabled EN form. |
| R8 | `earlyAccessNote.text` | skjemaet finnes bare på engelsk | (NO only) | `apps/web/src/pages/[page].astro` renders `EarlyAccessForm` on EN /pricing | True; see #18 |

EN claims with no source: R3, R4, R5 (tier contents). None of them is a number or a date.

## 4. Meaning drifts (at 4370f95)

1. #5 "som skal betale dem" (more definite than "would pay"), minor.
2. #11 "de sentrale amerikanske delstatene" (can mean the geographically central states), **real ambiguity**.
3. #11 "i tidlig fase" for "seed-stage", minor.
4. #11 "forsøkspersoner" for "data subjects", unsure, owner decision.
5. #13 "lokalt på veikartet" (garden-path reading), ambiguity.

## 5. Missing / extra keys

- **Extra in NO:** `reviewed: false` (expected) and `earlyAccessNote` {`text`, `linkLabel`, `href`} (expected, the only
  NO-only content key per `docs/web/i18n/README.md`).
- **Missing in NO:** none. Sections `tiers` (3 items), `why-no-prices`, `early-access`; statuses identical.

## 6. Pending text on `web/copy-licence-tiers` @ eb90773 (read only)

Changed keys (EN and NO): `meta.description`, `sections[tiers].heading` ("Five tiers" / "Fem nivåer"), and `items`
(3 → 5: Open Core, Lab and institution, Startup, Growth, Enterprise and pharma; the last has status `roadmap`).
Unchanged: `hero.*`, `tiers.body`, `why-no-prices`, `early-access`, `earlyAccessNote`. So findings #4, #5, #15–#19
still apply after the merge, and #2, #6, #8–#13 will be replaced. The branch's `docs/web/COPY-CLAIMS-RECHECK.md` addendum
cites `investor/PRICING.md` §3.1–3.5 as the source and shows no ESTIMATE price.

Language notes on the new NO strings (for web-copy-2):

| Key (branch) | NO (branch) | Note |
|---|---|---|
| `meta.description` | En gratis Open Core for enkeltforskere og studenter, og betalte planer for laboratorier, oppstartsselskaper, selskaper i vekst og større virksomheter eller legemiddelselskaper. … | OK. C: "større virksomheter" (see glossary: enterprise). |
| `items[0]` Open Core: gratis | … en kjører for rutenett av løyper, … Driftes av deg selv. | S: "en kjører" (runner) is first read as the verb "kjører"; "et verktøy for å kjøre rutenett av løyper". S: "Driftes av deg selv" is stiff; "Du drifter den selv." / "Egendriftet." |
| `items[1]` Laboratorium og institusjon: per laboratorium | … betalt av institusjonen eller et forskningsprosjekt … plasser for teamet … områdelisenser for kjernefasiliteter … | D (minor): "a grant" is "en forskningsbevilgning"/"et tilskudd", not "et forskningsprosjekt". S: "brukerplasser" for seats. U: "områdelisens" for "site licence" is unusual; "campuslisens" or "institusjonslisens". |
| `items[2]` Oppstart | For nevroteknologiselskaper i oppstartsfasen og avleggere fra universiteter. … | S: "avleggere" (offshoots) is informal for spinouts; "selskaper som er skilt ut fra universiteter". C: the "de sentrale amerikanske delstatene" ambiguity from #11 is **still present**. |
| `items[3]` Vekst | … et dokumentasjonssett til søknader hos FDA, multiversrevisjoner, drift som kan dekkes av en BAA … | OK. U: "multiversrevisjoner" ("multiverse audits") is opaque in both languages. |
| `items[4]` Virksomhet og legemiddel: tilbud | … Arbeidsflyter for FDAs krav til elektroniske registreringer, drift på egen instans eller i VPC, valideringspakker og SLA-er. Priset per program eller studie. | **A (new, real):** "tilbud" (the price type "quote") clashes with the hero lede on the same page, "ingenting på denne siden er et tilbud" ("nothing here is an offer"). EN avoids this with "quote" vs "offer". Suggest "pris på forespørsel". |

The intentional mismatch the branch records (homepage teaser = 3 tiers, /pricing = 5, owner decision 2026-09-27) is not
a translation issue and is not flagged here.
