> UTKAST – ikke juridisk rådgivning. Må gjennomgås av norsk advokat før bruk.

# Samtykkeomfang i samtykkeregisteret (fra jus til utvikling)

Versjon [0.1] · 2026-09-26 · Eier: Marius Carlsson · Forfatter: nfb-legal-privacy · Språk: den engelske versjonen (CONSENT-SCOPES.en.md) går foran, fordi den er den tekniske spesifikasjonen [valg for advokat]

**Status og frist**
- Omfangene skal være på plass i registeret (BUILD-GUIDE 5.3; BLUEPRINT §8.3) **før den første designpartneren**.
- Teksten deltakerne ser, står i contributor-consent.{no,en}.md, del 3.
- Alle omfang med prefiks `nf.` gjør **NeuroForge til behandlingsansvarlig**. De kan bare samles inn når alt dette er på plass:
  - kunden har signert tillegget om forskningsdatabasen (Research Pool Addendum, MSA § 4.3);
  - det finnes en vurdering av personvernkonsekvenser (DPIA);
  - REK/IRB har godkjent formålet, der det er helseforskning.
- FORUTSETNING: NeuroForge Bio AS er ikke stiftet ennå.

## 1. Tabell over omfang

| Omfangs-ID | Boks | Behandlingsansvarlig | Tilsvarer planlagt omfang | Kort tekst til skjermen | Krever | Blokkeres av |
|---|---|---|---|---|---|---|
| `study.collection`, `study.processing` | (i) | Kunden | collection, processing | «Måle og bruke dataene mine i [studien]» | – | – |
| `nf.pool` | (ii) | NeuroForge | sharing (til NeuroForge) | «Oppbevare en avidentifisert kopi i NeuroForges forskningsdatabase» | `study.collection`; tillegget om forskningsdatabasen | CA `limit_use`; manglende DPIA/REK |
| `nf.internal_rnd` | (ii) (delformål) | NeuroForge | processing | «Teste og forbedre NeuroForges egen analyseprogramvare; ingen tilgang for tredjeparter; ingen modellvekter forlater NeuroForge» | `nf.pool` | som `nf.pool` |
| `nf.model_training.internal` | (iii) | NeuroForge | model training | «Trene KI-modeller som NeuroForge bruker selv» | `nf.pool` | som `nf.pool` |
| `nf.research.future_neuro` | (iv) | NeuroForge | processing (forskning) | «Fremtidig forskning på hvordan nervesystemet virker og på nevrologiske tilstander, med etikkgodkjenning der det kreves» | `nf.pool` + **prosjektpost** med REK/IRB-ref. eller vurdering av at prosjektet faller utenfor helseforskningsloven | område utenfor listen over tillatte områder (§ 2); deltakeren har reservert seg mot området |
| `nf.share.research_partner` | (v) | NeuroForge | sharing | «Dele avidentifiserte data med godkjente universiteter og sykehus etter avtale» | `nf.pool` + signert akademisk delingsavtale | – |
| `nf.model_training.licensed` | (vi) | NeuroForge | model training + commercial use | «Trene KI-modeller som lisensieres til selskaper som betaler» | `nf.pool` + modellisens med bruksbegrensninger | CA `limit_use`; reservasjon mot «sale» i USA |
| `nf.data_licence.commercial` | (vii) | NeuroForge | sharing + commercial use | «Dele avidentifiserte data med selskaper som betaler» | `nf.pool` + signert datalisensavtale | CA `limit_use`; reservasjon mot «sale» i USA |
| `nf.recontact` | (viii) | NeuroForge | – (kontaktdata) | «Kontakte meg om nye studier» | – | – |

**Valg som advokaten bør bekrefte:** `nf.internal_rnd` ligger i boks (ii), fordi det å teste programvare på dataene i databasen er en del av formålet med databasen. Hvis advokaten vil ha en egen boks for dette, kan omfanget skilles ut uten kodeendring.

## 2. Tillatte områder for `nf.research.future_neuro`
Bredt samtykke må gjelde «visse forskningsområder» (fortalepunkt 33).

**Tillatte områder:**
- grunnleggende nevrovitenskap om hjerne- og nervesignaler;
- metoder for å måle, rense og analysere nevrale signaler;
- nevrologiske og nevroutviklingsmessige tilstander;
- forskning på hjerne–datamaskin-grensesnitt (BCI);
- nevroproteser (beregningsbasert).

**Utenfor, og krever nytt og spesifikt samtykke:**
- genetikk og genomikk, eller kobling mot biobanker;
- legemiddelutvikling basert på personens data;
- psykiatrisk eller atferdsmessig profilering av enkeltpersoner;
- all kommersiell lisensiering (bruk (vi) eller (vii) i stedet);
- alt som ikke gjelder nervesystemet.

**Prosjektposter:**
- Hvert prosjekt registreres med tittel, område, REK/IRB-referanse, startdato og lenke til et offentlig sammendrag.
- `policy.check` nekter tilgang hvis prosjektets område ikke står på listen, eller hvis deltakeren har reservert seg mot området.
- Deltakerne får beskjed om nye prosjekter. Helseforskningsloven § 14 gir dem «krav på jevnlig informasjon».

## 3. Regler for håndheving (`policy.check`, BUILD-GUIDE 5.4)

1. **Avhengighet.** Alle `nf.*`-omfang unntatt `nf.recontact` virker bare når `nf.pool` er gitt. Trekkes `nf.pool` tilbake, faller alle omfang som avhenger av det, bort.
2. **Tilbaketrekking for hvert omfang.** Hvert omfang kan trekkes tilbake alene, like lett som det ble gitt (art. 7 nr. 3; Connecticut: «at least as easy»). For amerikanske deltakere skal behandlingen stanse innen 15 dager (Connecticut). Vårt mål er umiddelbart.
3. **Sletting per omfang** (BLUEPRINT §8.4). Sletting gjelder bare behandlingen under omfanget som trekkes tilbake:
   - `nf.pool`: kopien i databasen slettes, og databasens deltakernøkkel ødelegges;
   - `nf.model_training.*`: berørte modeller merkes `retrain_required` og sperres for ny utrulling (kan konfigureres). Der SISA brukes, trenes bare den berørte delen (sharden) på nytt;
   - `nf.share.*` og `nf.data_licence.*`: mottakerne får varsel om tilbaketrekking og skal levere slettebevis innen [30] dager.
4. **Versjonering.** Hvert samtykke lagres med skjemaversjon og hash. Endres betydningen av et omfang, må deltakeren samtykke på nytt. Gamle samtykker gjelder ikke for den nye betydningen.
5. **USA.** Deltakere i Colorado, California, Connecticut og Montana får aldri noe omfang som standardvalg. `limit_use` (California Civ. Code 1798.121) blokkerer `nf.pool` og alt som avhenger av det.
6. **Data vi behandler for kunder.** Data i kundens tenant (bare `study.*`) kan aldri leses av `nf.*`-jobber (DPA § 3.4, MSA § 4.3). Dette skal bevises med tester i CI.
7. **Mindreårige.** Samtykke til `nf.*` fra personer under 18 år avvises, med mindre kunden har en egen prosess for mindreårige som er godkjent av REK/IRB.

## 4. Rettslig grunnlag
- **Alle `nf.*`-omfang:** uttrykkelig samtykke etter art. 6 nr. 1 bokstav a og art. 9 nr. 2 bokstav a.
- **Forskning:** garantier etter art. 89 nr. 1. Lengre lagring er bare tillatt etter art. 5 nr. 1 bokstav e, og bare så lenge forskningsomfanget gjelder.
- **Bredt samtykke:** fortalepunkt 33 og helseforskningsloven § 14. REK kan sette vilkår eller kreve nytt samtykke.
- **Kommersiell lisensiering:** dekkes **ikke** av bredt forskningssamtykke. Deling mot betaling er «sale» i Connecticut og California og krever uttrykkelig samtykke (opt-in).

## Hjemmel / Legal basis
- **Personvernforordningen, offisiell engelsk tekst** (Publikasjonskontoret, http://publications.europa.eu/resource/celex/32016R0679, åpnet 2026-09-26): fortalepunkt 33 og 42; art. 5 nr. 1 bokstav b og e; art. 89 nr. 1.
- **Personvernforordningen, norsk tekst på Lovdata** (åpnet 2026-09-26):
  - art. 7: https://lovdata.no/lov/2018-06-15-38/gdpr/a7
  - art. 9: https://lovdata.no/lov/2018-06-15-38/gdpr/a9
- **Helseforskningsloven** §§ 14 og 17: https://lovdata.no/lov/2008-06-20-44/§14 (åpnet 2026-09-26).
- **Connecticut PA 25-113** (åpnet 2026-09-26): https://www.cga.ct.gov/2025/ACT/PA/PDF/2025PA-00113-R00SB-01295-PA.PDF
- **California Civ. Code 1798.121** (åpnet 2026-09-26): https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1798.121
- **Colorado og Montana:** **UVERIFISERT**.
