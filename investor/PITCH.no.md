# NeuroForge Bio: investorpresentasjon (tekstversjon)

> **Oversatt fra PITCH.md (engelsk). Ved avvik gjelder den engelske versjonen inntil eier har godkjent.**

Utarbeidet 26.09.2026 av CEO-agenten for eieren, Marius Carlsson. **UTKAST til eiers gjennomgang. Ikke sendt til noen.**

Tallformat: desimalkomma og mellomrom som tusenskille. USD-beløp står i USD, NOK-beløp i NOK (f.eks. «USD 3,63 mill.», «NOK 1 mill.»).

**Les dette først**
- **Før produkt.** Ingenting av det som beskrives her, er bygget. Alle funksjoner er *designet*, *planlagt* eller på *veikart*.
- **Ingen trekkraft er påstått.** Det finnes ingen kunder, intensjonsavtaler (LOI), piloter, partnere eller brukere.
- **Alle finansielle tall er ESTIMATER** fra `investor\financial-model.py` (metode og kilder står i ASSUMPTIONS-delen). Alle priser er ESTIMAT inntil kundeintervjuer har validert dem (`investor\PRICING.md`).
- **Navn.** «NeuroForge Bio» er gjenstand for **varemerkeklarering som pågår**. Navnet «NeuroForge» alene er mye brukt: Neuroforge GmbH & Co. KG driver innen AI/Big Data-programvare i Tyskland, og andre AI-selskaper bruker det også (`market\names.md`). Et advokatsøk er nødvendig før offentlig lansering.
- **Ikke medisinsk utstyr.** NeuroForge Bio er designet som programvare for forskning og utvikling som ikke er medisinsk utstyr. Den fremsetter ingen diagnostiske eller terapeutiske påstander (`market\regulation.md` §4).
- Kildegrader: A = fagfellevurdert eller primær lovtekst; B = seriøs presse eller tertiærkilde; C = preprint eller teori; D = selskapsmarkedsføring.

---

## Lysbilde 1. Tittel

**NeuroForge Bio**
*Versjonerte, sammenlignbare pipelines og styring av nevrale data, fra elektrode til modell.*

Dokumentasjons- og styringslaget for nevroteknologiteam. Før produkt, 2026.
Marius Carlsson, gründer.

---

## Lysbilde 2. Problem

Nevroteknologiteam kan vanskelig vise **hva som er gjort med dataene deres**, eller **hva de har lov til å gjøre med dem**.

1. **Resultatene avhenger av valg i forbehandlingen, og disse valgene blir sjelden dokumentert eller delt.**
   - Alle trinn for artefaktkorreksjon *reduserte* dekodingsytelsen, mens høyere høypass-grenser økte den (Kessler et al., *Commun Biol* 2025, doi:10.1038/s42003-025-08464-3, A).
   - På tvers av 43 pipelines fantes det «no single best pipeline» – ingen enkelt beste pipeline (Huang et al., *Psychophysiology* 2025, doi:10.1111/psyp.70197, A).
   - Bare **20,9 %** av 129 EEG-BCI-artikler gjorde kode eller pipelines tilgjengelig (Peksa et al., *Sensors* 2026, doi:10.3390/s26175562, A).
2. **Nevrale data er nå regulert, og reglene spriker.** Colorado og California omfatter data fra både sentralnervesystemet *og* det perifere nervesystemet; Connecticut omfatter bare sentralnervesystemet; California unntar data som er utledet fra ikke-nevral informasjon (`market\regulation.md` §1, A). Ett og samme EMG- eller EEG-opptak kan være «nevrale data» i én delstat og ikke i neste.
3. **Tilbaketrekking av samtykke må nå avledede data og trente modeller.** Vi fant ikke noe nevralspesifikt verktøy for dette (`market\landscape.md` §3).
4. **Team i klinisk fase trenger dokumentert evidens.** FDA skriver at implanterte BCI-er «should generally address the recommendations for an Enhanced Documentation Level» (FDA BCI guidance, 2021, med en oppdatert merknad; `market\regulation.md` §4, A).

*Ikke målt ennå:* hvor mange ingeniøruker oppstartsselskaper taper på dette. Det er spørsmål nr. 1 i kundeintervjuene (`market\validation.md` #1, vurdering WEAK).

---

## Lysbilde 3. Hvorfor nå

| Drivkraft | Evidens | Grad |
|---|---|---|
| Delstatlige lover om nevrale data er i kraft | CO HB24-1058 (i kraft 7. aug. 2024); CA SB 1223 (Ch. 887, 28. sep. 2024); MT SB 163 (mai 2025, via en fagfellevurdert oversikt; lovteksten er ikke åpnet ennå); CT PA 25-113 (CTDPA-bestemmelsene i kraft **1. jul. 2026**) | A |
| Føderal oppmerksomhet | MIND Act ble fremmet i sep. 2025; den pålegger en FTC-utredning (Young, Simon & Evans, *Neurology* 2026) | A |
| EU-begrensninger | AI Act art. 5(1)(f) forbyr slutninger om følelser på arbeidsplassen og i utdanning (unntatt av medisinske eller sikkerhetsmessige grunner), gjeldende fra 2. feb. 2025 | B |
| Implantater går inn i kliniske studier | Paradromics fikk IDE godkjent i nov. 2025 og første implantat i jun. 2026; Precision 510(k) i apr. 2025; Science' PRIMA lansert i EU i jul. 2026 (`market\landscape.md` §1) | B / D |
| Kapital strømmer til sektoren | Nevroteknologisk utstyr fikk USD 1,2 mrd. i risikokapital i 2024, «more than any other type of medical device» (*Sci Adv* 2026, med HSBC som kilde, A). HSBC 1H 2026: «Neuro remained the strongest medtech investment category» (B) | A / B |

Kilder for alle rader: `market\regulation.md`, `market\sizing.md` §1.

---

## Lysbilde 4. Produkt

**Én lineage-graf (sporbarhetsgraf) over nevrale data, pipelines og modeller, med tre produkter bygget oppå** (`market\new-ideas.md`, topp 5; `architecture\BLUEPRINT.md` §0).

| Produkt | Hva det gjør | Status |
|---|---|---|
| **Open Core SDK** (Apache-2.0, jf. D6) | Python-SDK, konverterere, validatorer, lokal proveniens; integrerer MNE, BIDS, NWB, LSL og BrainFlow i stedet for å erstatte dem | Planlagt, måned 0–3 |
| **Multiverse-revisjon** | Kjører et rutenett av forbehandlings-pipelines og rapporterer hvordan resultatene endrer seg, med alle parametre registrert | Planlagt, måned 0–3 (på offentlige DANDI/OpenNeuro-data) |
| **Consent & Deletion Ledger** (samtykke- og slettelogg) | Jurisdiksjonsklassifisering per kanal (CO/CA/CT/MT og EU-flagg); versjonert aktivt samtykke (opt-in); tilbaketrekking videreført til rådata, avledede data og trente modeller; signert slettesertifikat | Planlagt, måned 3–9 |
| **FDA Evidence Kit + latency harness** (FDA-dokumentasjonspakke + latensmåling) | Maler for sporbarhet, SBOM og OTS/SOUP-dokumentasjon fra samme graf; reproduserbare ende-til-ende tidsrapporter | Veikart, måned 9–18 |
| **Styrt modellregister** | Modellproveniens med flagg for bruksbegrensninger (EU AI Act 5(1)(f)) | Veikart, kun ved etterspørsel fra kunder |

**Det vi ikke påstår:** sertifisert «unlearning», HIPAA-samsvar, SOC 2 eller «automatisk rensing». Slettegarantien er «retrained without the subject, with a provenance proof» – trent på nytt uten personen, med proveniensbevis (`BLUEPRINT.md` §8.4). Juridiske regler leveres med en `review_status` og må gjennomgås av advokat før kunder stoler på dem.

---

## Lysbilde 5. Slik fungerer det

```
 enheter / filer ──► innlesing (åpne lesere: MNE, pynwb, pyxdf, liblsl)
                         │
                         ▼
          ┌──────── proveniensgraf (Postgres) ──────────┐
          │ personer · opptak · kanaler · pipeline-     │
          │ kjøringer · artefakter · datasett · modeller│
          └─────────────────────────────────────────────┘
             │                 │                    │
             ▼                 ▼                    ▼
     Consent & Deletion   Multiverse-revisjon  FDA Evidence Kit
     Ledger (styring)     (reproduserbarhet)   (regulert evidens)
```

- Signaler lagres som oppdelte (chunked) Zarr-arrays på S3-kompatibel lagring. Standardlagring er et bevisst valg: lagring med lav latens er ikke et konkurransefortrinn (`market\validation.md` #7).
- Én Rust-kjerne (`nf-core`) ligger bak SDK-ene for Python og C/C++ (D7).
- Hver lesing, pipeline-kjøring og treningsjobb går gjennom én og samme samtykkekontroll (`BLUEPRINT.md` §8.3).

---

## Lysbilde 6. Marked

Alle tall er **ESTIMATER** fra `market\sizing.md`.

| Lag | Tall | Metode |
|---|---|---|
| **TAM** (all programvare for nevrale data) | USD 0,1–1,1 mrd. | Ovenfra og ned fra analytikertall som spriker med om lag 11x. **Ikke beslutningsgrunnlag.** |
| **SAM** (nåbart med dette produktet) | **USD 10–86 mill. ARR** | Nedenfra og opp: antall i segment × ACV i fire segmenter |
| **SOM** (3 år etter lansering) | **~USD 2,4 mill. ARR, 108 kunder** | Nedenfra og opp, antall kunder |

Segmenter (antall × ACV, ESTIMAT):
- **S1** nevroteknologi i klinisk fase og implantater: 80–150 × USD 50 000–150 000
- **S2** forbrukernevroteknologi under delstatlige lover: 100–300 × USD 10 000–50 000
- **S3** forskningslaboratorier, betalte institusjonsplaner: 900–1 750 laboratorier × USD 2 000–10 000 (10–20 % betalende)
- **S4** CNS-farma og CRO-er med EEG-endepunkter: 50–150 × USD 100 000–300 000

**Ærlig vurdering:** «hakke og spade for BCI-maskinvareprodusenter» alene er et lite marked. S1 alene utgjør USD 4–22 mill. Pengene ligger hos **regulerte kjøpere**: S1 og S4 utgjør til sammen om lag 70–80 % av SAM (`market\sizing.md` §4).

---

## Lysbilde 7. Forretningsmodell

Open core for distribusjon, med en betalt hostet plattform. Verdimålet er **antall dataobjekter (personer) pluss enheter under forvaltning**, ikke GB. Alle priser er **ESTIMAT** (`investor\PRICING.md`).

| Nivå | Kjøper | Pris (ESTIMAT) |
|---|---|---|
| Open Core | Enkeltforskere | USD 0 |
| Lab / Institusjon | Laboratorier, kjernefasiliteter (kan budsjetteres under NIH DMS-policyen) | USD 3 000–10 000 per år |
| Startup | Nevroteknologiske oppstartsselskaper som har hentet ≤ USD 2 mill. | USD 300–800 per måned |
| Growth | Nevroteknologi i Series A–C og klinisk fase | USD 50 000–150 000 per år |
| Enterprise / Pharma | CNS-sponsorer, CRO-er, store utstyrsprodusenter | USD 100 000–300 000+ per år |
| Tjenester | Multiverse-revisjon, tidsrapport, konvertering | USD 5 000–40 000 per oppdrag |

Sammenlignbare (alle D, leverandørsider): NeuroPype startup USD 79–99 per måned; EmotivPRO USD 1 068–2 689 per år; Aptible HIPAA Production USD 499 per måned; W&B forbeholder HIPAA til Enterprise; Flywheel kun etter tilbud innen regulert bildediagnostikk.

Bruttomargin i modellen (basis, ESTIMAT): 52 % i år 2, økende til 74 % i år 5.

---

## Lysbilde 8. Markedsstrategi (go-to-market)

Rekkefølgen følger `market\pricing-and-gtm.md` §5:
1. **Måned 0–3 (troverdighet, ingen kunder nødvendig):** lansere open core-SDK-en og validatoren. Kjøre multiverse-revisjonen på offentlige DANDI/OpenNeuro-data og publisere resultatene.
2. **Måned 3–9:** MVP av loggen (ledger) og Startup-nivået. Rekruttere **5 designpartnere** med 50 % rabatt på Growth i 12 måneder, mot casestudier.
3. **Måned 9–18:** FDA Evidence Kit og latency harness; Growth-nivået; første farmapilot.

Kanaler:
- **Integrasjoner** der brukerne allerede er: MNE (308 000 nedlastinger per måned), pynwb (108 000), pylsl (34 000) (pypistats, sep. 2026).
- **Innhold:** en gratis oversikt over lover om nevrale data (ikke juridisk rådgivning); fagfellevurderte benchmark-artikler.
- **Arrangementer:** International BCI Society Meeting, 7.–10. jun. 2027, Šibenik; SfN.
- **Partnere:** CatalystNeuro for NWB-konvertering (samarbeide, ikke konkurrere); OpenBCI/BrainFlow-økosystemet.

**Første steg:** eieren gjennomfører 15–20 kundeintervjuer før betalte funksjoner bygges. Full plan: `marketing\MARKETING-PLAN.md`.

---

## Lysbilde 9. Konkurranse

| Kategori | Eksempler (fra `market\landscape.md` §2) | Hvor de stopper |
|---|---|---|
| Åpen kildekode-biblioteker for analyse | MNE, EEGLAB, braindecode, pyRiemann, SpikeInterface | Biblioteker, uten styrings- eller proveniens­tjeneste |
| Offentlige arkiver | DANDI, OpenNeuro, brainlife | Deling og akademisk regnekraft. Gratis og offentlig finansiert, så vi integrerer med dem |
| Sanntids-pipelineprodukter | NeuroPype / NeuroScale | Nærmeste kommersielle analog (gratis for akademia, startup USD 79–99 per måned). Ingen styring av nevrale data funnet |
| Konverteringstjenester | CatalystNeuro (69 laboratorier) | Rådgivning, ikke samsvarsnivå. En partner, ikke et mål |
| Regulerte dataplattformer | Flywheel | Bildediagnostikk først. Viser at farma betaler for forskningsdata på samsvarsnivå |
| HIPAA-sky | AWS (175+ kvalifiserte tjenester), Aptible | Standardinfrastruktur, uten nevrale formater eller kartlegging av nevrallovgivning |
| Vertikalt integrerte BCI-ledere | Neuralink, Synchron (Chiral-modellen) | Bygger egen programvare. **Ikke våre kjøpere** |

**Ledig rom:** nevralspesifikk styring (samtykke, sletting gjennom sporbarhetskjeden, jurisdiksjonskartlegging) og regulert evidens. At vi «ikke fant noen i denne gjennomgangen», betyr ikke at det ikke finnes noen.

---

## Lysbilde 10. Vollgrav (hva som bygger seg opp, og hva som ikke gjør det)

Dette gir **ikke** en vollgrav: HIPAA-infrastruktur (en standardvare, `market\validation.md` #2), lagring, rensealgoritmer eller SDK-kode (åpen kildekode med vilje).

Dette kan bygge seg opp over tid:
1. **Maskinlesbare regelsett (RuleSets) for nevrallovgivning.** Versjonerte regler per jurisdiksjon, gjennomgått av advokat og vedlikeholdt etter hvert som lovene endres. De driver også den offentlige lovoversikten. Blir vanskeligere å kopiere jo flere jurisdiksjoner som legges til.
2. **Lineage-grafen som autoritativt system (system of record).** Når samtykke, pipeline-kjøringer og modellversjoner ligger i én graf, kommer slettesertifikatet og FDA-evidensen derfra, og det skaper byttekostnader.
3. **Publisert evidens for reproduserbarhet.** Multiverse-resultater på offentlige datasett blir siterbare referanser.
4. **Tillitsprofil.** Open core-kode, ingen sporere på vårt eget nettsted (D9) og ærlige statusmerker.

Alle fire er **planer**. Ingen av dem finnes ennå.

---

## Lysbilde 11. Tillit og sikkerhet

Kilde: `security\STANDARDS-MAP.md` (utkast fra sikkerhetseksperten). **Ingenting her er revidert eller sertifisert.** Alle kontroller er *designet*, *planlagt* eller på *veikart*.

| Område | Tilnærming | Status |
|---|---|---|
| Applikasjonssikkerhet | OWASP ASVS 5.0 **nivå 2** som krav før lansering for alt som er eksponert mot internett. **Nivå 3** for kapitlene som beskytter nevrale data (autorisasjon, kryptografi, databeskyttelse, logging). **Full L3** for samtykkeloggen, sletting og nøkkelhåndtering | designet |
| Sikker utvikling | NIST SSDF (SP 800-218) og IEC 81001-5-1-livssyklus for komponenter som tilbys som SOUP; mål SLSA Build L2 → L3; CycloneDX SBOM per utgivelse; signerte artefakter | planlagt |
| EU-rett | Kontroller etter GDPR art. 32; beredskap for **EU Cyber Resilience Act** for SDK-ene (rapporteringspliktene har gjeldt siden 11. sep. 2026); NIS2-tilpassede leverandørkontroller for kunder | designet / planlagt |
| Kundenes innsendinger for medisinsk utstyr | Evidens til FDAs veiledning om cybersikkerhet før markedsføring (endelig, 3. feb. 2026) og EU MDR vedlegg I §17: SBOM, støttenivåer, sårbarhetsstatus | planlagt |
| Sertifiseringer | ISO/IEC 27001, deretter 27701; SOC 2 Type II når 2–3 designpartnere ber om det | **veikart** |
| Sikkerhetsgrense | Plattformen og SDK-ene **styrer aldri stimulering eller noen aktuator**. De er skrivebeskyttet mot innsamlingsmaskinvare | designet (en permanent regel) |

Å beskytte data er viktigere her enn ellers, fordi et brudd ikke kan omgjøres: «you cannot rotate a brain» – en hjerne kan ikke byttes ut som et passord (`security\STANDARDS-MAP.md` §1.1).

*Ikke juridisk eller regulatorisk rådgivning. Advokat og en regulatorisk konsulent må bekrefte hver vurdering av hva som gjelder.*

---

## Lysbilde 12. En lovlig dataressurs basert på nevrale data (oppside, ikke i basisscenarioet)

Kilde: `investor\DATA-REVENUE-STRATEGY.md`. Risikovurderingene er gjort av nfb-legal-privacy 26.09.2026. De er et utkast fra et KI-juristteam, ikke rådgivning fra advokat, og må bekreftes av advokat. Ikke juridisk rådgivning.

**Prinsipper**
- **Kundene eier dataene sine.** Ethvert bidrag til en forskningspool hos NeuroForge Bio er frivillig (opt-in), **AV som standard**, og krever eksplisitte samtykkeomfang.
- Foreslåtte nye samtykkeomfang i loggen: *intern FoU* og *fremtidig bioteknologisk/nevrobiologisk forskning*. Juristteamet har avgrenset det siste omfanget til forskning på nervesystemet, og hvert helseforskningsprosjekt må fortsatt godkjennes av REK. Omfanget *modelltrening* finnes allerede. Utkast til samtykkemaler ligger i `legal\data-agreements\CONSENT-SCOPES.*`.
- **Tilbaketrekking virker alltid.** Den videreføres gjennom lineage-grafen til avledede data og modeller.
- **Aldri en datamegler:** intet salg av data på individnivå; ingen kjøpere blant forsikringsselskaper, arbeidsgivere, annonsører eller politi og påtalemyndighet.

**Slik bygges ressursen opp**
- Frivillig pool, mot kreditter eller rabatter.
- Egne forskningsprogrammer godkjent av REK/IRB med bredt samtykke (kun ikke-invasiv EEG, ingen stimulering).
- Kuraterte offentlige datasett (OpenNeuro/DANDI, med lisenser kontrollert).
- Syntetiske data, som bare frigis etter bestått test for medlemskapsinferens (membership inference).
- Lagdelt lagring (S3 Standard USD 0,023 ned til Glacier Deep Archive USD 0,00099 per GB-måned; AWS-prisside, D).

**De beste inntektsmodellene etter risikojustert verdi** (ESTIMAT, spenn i år 5):
1. **Compute-to-data / føderert analyse** (dataene forlater aldri stedet): USD 0,1–1,5 mill.
2. **Endepunktanalyse for farma/CRO og data clean rooms:** USD 0,2–2,1 mill.
3. **Attestasjon av samtykke og proveniens** (attestasjonsrapporter, ikke sertifisering): USD 0,1–1,1 mill.
4. **Benchmarks og evalueringer på tilbakeholdte data:** USD 0,05–0,6 mill.
5. **Tilskudd og skattefradrag (ikke-utvannende):**
   - SkatteFUNN: 19 % av FoU-kostnadene.
   - Innovasjon Norge oppstartstilskudd: opptil NOK 150 000.
   - EIC Accelerator: tilskudd under EUR 2,5 mill.; Norges kvalifisering er IKKE VERIFISERT.

**Forkastet:** bruk hos forsikringsselskaper eller arbeidsgivere (risiko etter AI Act art. 5 og delstatlige lover), salg av rådata, samt annonsering, nevromarkedsføring eller bruk hos politi og påtalemyndighet.

**Oppside fra dataressursen i tillegg til basisinntekt**, år 5 (ESTIMAT): lav USD 0,13 mill. / middels USD 0,80 mill. / høy USD 2,40 mill. I modellen (`financial-model.py`, scenarioene base+data_*) er bokførte inntekter i år 5 USD 3,46 mill. / 4,14 mill. / 5,74 mill., mot USD 3,34 mill. i basisscenarioet. Kontantbeholdningen i år 5 er USD 7,1 mill. / 8,2 mill. / 10,3 mill. **Basisscenarioet holder disse inntektene utenfor.**

---

## Lysbilde 13. Trekkraft

**Før produkt.** Det finnes ingen kunder, inntekter, intensjonsavtaler, piloter eller partnerskap.

Dette finnes i dag (internt arbeid, ikke trekkraft):
- Markeds-, regulerings- og prisundersøkelser med graderte kilder (`market\`).
- En arkitekturplan for virksomheten (enterprise architecture blueprint) og byggeveiledning (`architecture\`).
- Nettsteddesign i to temaer (`design\`).
- Et beregningsbasert forskningsprogram om lukket sløyfe for somatosensorisk tilbakemelding (`research\somatosensory\`). Kun simulering, uten arbeid på mennesker.

**Milepæler de neste 90 dagene** som ville telle som trekkraft: 15–20 kundeintervjuer gjennomført; open core-SDK-en publisert; multiverse-resultater på offentlige data publisert; 3–5 designpartnere signert.

---

## Lysbilde 14. Team

**Marius Carlsson, gründer.** Bakgrunn: [EIER SKRIVER: må være faktabasert].

**Ansettelsesplan** (basisscenario, `investor\financial-model.py`, ESTIMAT):

| Ved årsslutt | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Ansatte, ekskl. gründer | 4 | 12 | 13 | 25 | 33 |

- **Første ansettelser (etter seed-runden, rundt måned 9):** 3 programvareutviklere (Rust/Python/plattform) og 1 nevrodataforsker.
- **År 2:** DevOps/sikkerhet, regulatorisk/QA, produktdesigner, kundeansvarlig selger (account executive), kundesuksess og markedsføring/utviklerrelasjoner.
- **Rådgivere som skal rekrutteres (ikke engasjert):** personvernadvokat, en regulatorisk FDA-konsulent og en nevroforsker eller klinisk rådgiver.

Antall ansatte totalt i modellen inkluderer gründeren (5, 13, 14, 26, 34). **Ingen ansettes før seed-runden er gjennomført.** Hver ansettelse krever kontanter som dekker 9 måneders prognostisert kapitalforbruk, så i år 3 settes ansettelser på pause frem til Series A.

Utviklingsverktøyene omfatter AI-assistenter for koding og research. De er verktøy, ikke teammedlemmer.

---

## Lysbilde 15. Veikart

| Når (fra finansiering) | Milepæl | Status |
|---|---|---|
| Måned 0–3 | Nettsted (klinisk tema); open core-SDK og validator; multiverse-revisjon på offentlige data | Planlagt |
| Måned 3–9 | MVP av Consent & Deletion Ledger; Startup-nivå; 3–5 designpartnere; personvernadvokat gjennomgår regelsettene | Planlagt |
| Måned 9–18 | FDA Evidence Kit og latency harness; Growth-nivå; første farmapilot; SOC 2 Type II startet når partnere ber om det | Veikart |
| År 2–3 | EU-region (GDPR); Part 11-arbeidsflyter for CNS-studier; styrt modellregister hvis kundene etterspør det | Veikart |
| År 3–5 | Skalering i USA og EU; Enterprise/Pharma-nivå; C++/Unity/Unreal-SDK-er kun ved kundeetterspørsel; frivillig forskningspool (standard AV) | Scenario |
| År 8–15 | **En forskningsgren innen bioteknologi og nevrobiologi.** Den bygger på den samtykkebaserte dataressursen og modellene våre: biomarkører, identifisering av mål (target discovery), somatosensorisk og nevroprotetisk forskning. Våtlab- eller klinisk arbeid krever REK-/etikkgodkjenning og andre tillatelser (se `SCALING-PLAN.md` §10) | Scenario |

Perspektivet for 10–15 år står i `investor\SCALING-PLAN.md`. Etter år 2 er det scenarioer, ikke prognoser.

---

## Lysbilde 16. Økonomi (ESTIMAT, basisscenario)

Kilde: `investor\financial-model.py` → `financial-model.csv`, med finansieringsløpet korrigert 26.09.2026.
- Første runde er **NOK 1 mill.** (≈ USD 105 000 med kurs 9,5063 NOK/USD, Norges Banks kurs for 25.09.2026).
- Seed-runden lukkes i måned 9. Betalt lansering skjer i måned 17.

| Modellår | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| ARR ved årsslutt (USD) | 0,00 mill. | 0,28 mill. | 1,15 mill. | 2,28 mill. | **3,63 mill.** |
| Bokførte inntekter (USD) | 0,04 mill. | 0,27 mill. | 0,92 mill. | 2,05 mill. | **3,34 mill.** |
| Bruttomargin | 36 % | 52 % | 62 % | 74 % | 74 % |
| Netto kapitalforbruk (USD) | 0,35 mill. | 1,35 mill. | 2,32 mill. | 2,66 mill. | 3,45 mill. |
| Kontantbeholdning ved årsslutt (USD) | 0,81 mill. | 3,46 mill. | 1,14 mill. | 10,48 mill. | 7,03 mill. |
| Antall ansatte (ved årsslutt) | 5 | 13 | 14 | 26 | 34 |
| Betalende kunder | 0 | 19 | 54 | 95 | 140 |

**Scenarioer, ARR ved slutten av år 5:**
- Pessimistisk (bear): USD 1,15 mill., med et finansieringsgap på −USD 1,25 mill. i måned 49.
- Basis: USD 3,63 mill.
- Optimistisk (bull): USD 7,00 mill.
- Nøktern (lean; gründerdrevet, ingen ansettelser): ingen ARR. Den forutsetter om lag én revisjon til USD 20 000 per kvartal, noe som ikke er validert.

**Oppside fra dataressursen (ikke i basis):** inntekter i år 5 på USD 3,46 mill. / 4,14 mill. / 5,74 mill. i lav / middels / høy (lysbilde 12).

**SOM-kontroll:** 36 måneder etter lansering (modellmåned 52) er basis-ARR USD 2,66 mill. med 109 kunder, mot SOM fra markedsberegningen på USD 2,4 mill. og 108 kunder.

**Største sensitiviteter** (effekt på kontantbeholdningen i år 5):
- en påslagsfaktor på 1,45×: −USD 1,45 mill.;
- seks måneders lengre byggetid: −USD 1,42 mill.;
- alle S2-kunder på Startup-nivået: −USD 0,83 mill.

**Ikke lønnsom innen år 5 i noe vekstscenario.** Kostnader det fortsatt må innhentes tilbud på: advokat, SOC 2, penetrasjonstest og regulatorisk konsulent. Lønnsgrunnlag: BLS-median USD 135 980 (A) × 1,30 (ESTIMAT).

---

## Lysbilde 17. Hva vi ber om

**Nå: en første runde på NOK 1 000 000** (≈ USD 105 000). Markedsmessig er dette en **pre-seed-runde (engleinvestering)**, ikke en Series A. En Series A kommer som regel etter at man har inntektstrekkraft. Eieren bestemmer beløp og vilkår. Se `investor\FUNDING-ROUND.md`, `dilution.py` og `ROUND-ASSUMPTIONS.md`; avtaleutkastene i `legal\` bruker de samme tallene.

**Foreslått struktur** (ESTIMAT; lavest mulig utvanning som en reell investor fortsatt kan akseptere):
- En priset aksjeemisjon (rettet emisjon) på **NOK 1 mill. til NOK 10 mill. i pre-money verdsettelse**, med pro rata-rett i neste runde. Nedre grense: NOK 8 mill. pre-money.
- Reserveløsning: et konvertibelt lån med tak (cap) på NOK 12 mill. og 20 % rabatt.

| Gründerens eierandel langs basisløpet (ESTIMAT) | Eierandel |
|---|---|
| Etter denne runden | **90,9 %** |
| Etter seed-runden: NOK 10 mill. til NOK 40 mill. pre-money, med en opsjonspool på 10 % | 63,6 % |
| Etter runde N2: USD 4,0 mill. (≈ NOK 38,0 mill.) til NOK 120 mill. pre-money | 48,3 % |
| Etter Series A: USD 12 mill. | 36,2 % |

**Hvor langt NOK 1 mill. rekker** (ingen inntekter forutsatt; `prephase-runway.csv`):

| Modus | Månedlig forbruk | Rullebane | Med tilskudd |
|---|---|---|---|
| **Nøktern:** gründer + KI-verktøy + 0,1 årsverk innleid, minimal sky | ≈ NOK 50 000 | **18 måneder** | **22 måneder** |
| **Lite team:** gründer + 0,5 årsverk innleid | ≈ NOK 114 000 | **8 måneder** | **9 måneder** |

Tilskuddene som er modellert, forutsetter at AS-et er stiftet og at søknadene innvilges, og ingen av dem er garantert:
- Innovasjon Norges oppstartstilskudd (oppstartstilskudd 1): opptil NOK 150 000.
- SkatteFUNN: 19 % av godkjente FoU-kostnader. Det utbetales via skatteoppgjøret, så pengene kommer rundt måned 21 (IKKE VERIFISERT).
- Forskningsrådet: ikke modellert, fordi programsiden ikke kunne åpnes.

**Hva runden kjøper** (før seed-runden, som må lukkes innen måned 9–10 i basisplanen):
- 15–20 kundeintervjuer, der prishypotesene testes;
- open core-SDK-en og multiverse-resultater på offentlige data, publisert;
- et varemerkesøk og en første gjennomgang fra personvernadvokat;
- rekruttering av 3–5 designpartnere;
- søknader om tilskudd.

Hvis seed-runden blir forsinket, går vi over til nøktern modus: 18–22 måneders rullebane.

**Største risikoer:**
1. Betalingsvilligheten er ikke validert.
2. Tidspunktet for seed-runden: forfasen med lite team har bare om lag 8–9 måneders rullebane, og laveste kontantbeholdning i basisplanen er om lag USD 13 000 i måned 8.
3. Regelsettene for nevrallovgivning og samtykkeomfangene må gjennomgås av advokat. Navnet trenger varemerkeklarering (Neuroforge GmbH, Tyskland).

*Begrepsliste for finansiering:* pre-seed/engleinvestering (angel); aksjeemisjon/rettet emisjon (priced round); pre-money/post-money verdsettelse; konvertibelt lån (convertible loan); frittstående tegningsrett (warrant); pro rata-rett (pro-rata right); opsjonspool (option pool). Ikke juridisk rådgivning.
