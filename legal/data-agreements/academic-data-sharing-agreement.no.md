> UTKAST – ikke juridisk rådgivning. Må gjennomgås av norsk advokat før bruk.

# Avtale om deling av forskningsdata med akademiske partnere

Versjon [0.1] · [DATO] · Språk: engelsk versjon går foran ved motstrid [valg for advokat; for avtaler med norske institusjoner kan norsk velges]

**Virkeområde:** deling av pseudonymiserte/avidentifiserte forskningsdata mellom NeuroForge og en akademisk institusjon, i én eller begge retninger, til ikke-kommersiell forskning. Avtalen dekker:
- **(A10) forskningssamarbeid og felles publikasjoner** (punkt 1–12);
- **(A7) lukkede testsett for sammenligningstester (benchmarks)** (punkt 13).

**Data fra NeuroForges forskningsdatabase** kan bare deles etter denne avtalen for deltakere som har samtykket til **boks (ii) `nf.pool` og boks (v) `nf.share.research_partner`** (contributor-consent.*; CONSENT-SCOPES.*). Er prosjektet helseforskning, kreves i tillegg **boks (iv) `nf.research.future_neuro`**, med registrert prosjektpost og REK/IRB-referanse.

Avtalen gjelder **ikke**:
- data NeuroForge behandler som databehandler for kunder. Da må kunden inngå egen avtale, og NeuroForge er ikke part som dataleverandør;
- kommersiell lisensiering (bruk data-licence-agreement.*);
- identifiserbare data.

En vurdering av personvernkonsekvenser (DPIA, art. 35) skal være gjort før første overføring (RISK-MEMO § 9).

## Parter
1. **[NeuroForge Bio AS]** (FORUTSETNING: norsk AS, **ikke stiftet ennå**), org.nr. [●], [adresse] («NeuroForge»).
2. **[Universitet / institutt]**, org.nr. [●], [adresse], representert ved [●] («Institusjonen»). Prosjektleder: [navn].

## 1. Prosjekt og formål
1.1 Prosjektet: [tittel], beskrevet i **vedlegg 1** (forskningsspørsmål, data, metode, varighet).
1.2 **Formålsbegrensning.** Delte data kan **bare** brukes i Prosjektet. De kan ikke brukes til formål som er uforenlige med bidragsyternes samtykker eller med etikkgodkjenningen. Nye formål krever skriftlig endring av avtalen, og nytt samtykke eller ny godkjenning der det kreves.

## 2. Roller – velg ETT alternativ [advokat bekrefter ut fra faktum]
☐ **Alternativ A – Selvstendige behandlingsansvarlige.** Hver part bestemmer selv hvorfor og hvordan den behandler dataene den mottar. Hver part er selvstendig behandlingsansvarlig og har ansvar for eget behandlingsgrunnlag, informasjon og sikkerhet. **Standardvalg ved enveis deling.**

☐ **Alternativ B – Felles behandlingsansvarlige (art. 26).** Brukes når partene **sammen fastsetter formål og midler**, for eksempel ved en studie med felles protokoll og felles database. Partene fastsetter da ansvarsfordelingen i en ordning i **vedlegg 2**:
- hvem som informerer de registrerte (art. 13/14);
- hvem som håndterer henvendelser, og hvem som er kontaktpunkt;
- hvem som gjør DPIA;
- hvem som melder avvik;
- hvem som har REK-godkjenningen.

Hovedinnholdet i ordningen skal gjøres tilgjengelig for de registrerte. **De registrerte kan utøve rettighetene sine overfor hver av de behandlingsansvarlige**, uansett hva ordningen sier (art. 26 nr. 3).

☐ **Alternativ C – Databehandler.** Behandler én part data bare etter instruks fra den andre (for eksempel når NeuroForge lagrer Institusjonens data), brukes databehandleravtalen (legal\commercial\dpa.*) i stedet.

## 3. Rettslig grunnlag og etikk
3.1 Parten som leverer data, garanterer at:
- a) dataene er samlet inn lovlig, med grunnlag i art. 6 og et unntak i art. 9 nr. 2. Det vil si enten uttrykkelig samtykke som dekker deling med mottakeren til Prosjektet (art. 9 nr. 2 bokstav a; for data fra NeuroForges forskningsdatabase boks (ii) og (v), og (iv) ved helseforskning), eller forskningsunntaket etter art. 9 nr. 2 bokstav j og art. 89 nr. 1 sammen med nasjonal rett. I Norge er det personopplysningsloven § 9, med interesseavveining og drøfting med personvernombud eller DPIA på forhånd;
- b) nødvendige **etikkgodkjenninger** finnes: REK-godkjenning etter helseforskningsloven § 9 for medisinsk og helsefaglig forskning, eller [IRB / annet]. Referansene står i vedlegg 1.
3.2 Mottakeren bekrefter at bruken i Prosjektet er dekket av eget behandlingsgrunnlag og av godkjenningene. Datatilsynet påpeker at REK-godkjenning alene ikke er behandlingsgrunnlag.

## 4. Personvernplikter
4.1 **Dataminimering.** Bare feltene i vedlegg 1 deles. Direkte identifikatorer deles aldri. Kodenøkler blir værende hos parten som leverer dataene.
4.2 **Ingen reidentifisering.** Mottakeren skal ikke reidentifisere eller forsøke å reidentifisere noen, koble data for å skille ut en person, eller kontakte de registrerte. Unntak gjelder bare kontakt gjennom parten som leverte dataene, og med etikkgodkjenning.
4.3 **Sikkerhet.** Tiltakene skal passe for særlige kategorier av personopplysninger og minst omfatte:
- kryptering ved lagring og overføring;
- tilgang bare for navngitte personer i Prosjektet (vedlegg 3), med logging av tilgang;
- sikker sletting;
- ingen opplasting til eksterne KI-tjenester som lagrer eller trener på dataene.
NeuroForges referansetiltak er MSA bilag 2 / DPA vedlegg II (utformet/planlagt; ingen sertifisering hevdes).
4.4 **Videre deling.** Data deles ikke videre med tredjeparter uten skriftlig forhåndssamtykke fra parten som leverte dem, og uten en skriftlig avtale som beskytter minst like godt som denne. **Salg eller kommersiell lisensiering er ikke tillatt.**
4.5 **De registrertes rettigheter.** Partene bistår hverandre og videresender henvendelser innen [5] virkedager.
4.6 **Avvik.** Den andre parten skal varsles uten ugrunnet opphold og senest [24] timer etter at man ble kjent med avviket. Hver behandlingsansvarlig melder selv til Datatilsynet og de registrerte (art. 33/34, ikke åpnet: **UVERIFISERT**). Under alternativ B følger ansvaret vedlegg 2.

## 5. Tilbaketrekking av samtykke og sletting
5.1 Parten som leverte dataene, varsler om tilbaketrekking. For NeuroForge skjer det med tilbaketrekkingsvarsel fra samtykkeregisteret, som angir de berørte prosjektpseudonymene (art. 17 nr. 1 bokstav b og art. 19).
5.2 Innen [30] dager skal mottakeren slette de aktuelle dataene, stanse bruken av dem og bekrefte slettingen skriftlig.
- Trente modeller trenes på nytt uten dataene, eller tas ut av bruk. **Sertifisert «avlæring» (machine unlearning) loves ikke.**
- Publiserte resultater trenger ikke trekkes tilbake.
- Forskningsunntaket i art. 17 nr. 3 bokstav d brukes bare etter skriftlig avtale og i tråd med helseforskningsloven § 16 (retten til å kreve sletting innen 30 dager).

## 6. Publisering
6.1 Institusjonen beholder sin akademiske frihet til å publisere resultater fra Prosjektet.
6.2 Publikasjoner kan **bare inneholde aggregerte eller avidentifiserte resultater som ikke gjør det mulig å skille ut en person**. Nevrale data på individnivå publiseres ikke, med mindre alt dette er oppfylt:
- det er uttrykkelig samtykket til;
- etikkomiteen har godkjent det;
- det er gjort en dokumentert vurdering av reidentifiseringsrisikoen;
- parten som leverte dataene, har samtykket skriftlig.
6.3 **Gjennomgang.** Parten som leverte dataene, får et utkast [30] dager før innsending, **bare** for å kontrollere personopplysninger og egen konfidensiell informasjon. Publisering kan ikke stanses av andre grunner. Fristen kan forlenges én gang med [30] dager for å beskytte patenterbare resultater [valg for eier/Institusjon].
6.4 Publikasjonen skal oppgi datakilden og etikkreferansene.

## 7. Overføring utenfor EØS
Delte data overføres ikke ut av EØS uten skriftlig samtykke fra parten som leverte dem, og et gyldig overføringsgrunnlag etter kapittel V (beslutning om tilstrekkelig beskyttelsesnivå, eller Kommisjonens standard personvernbestemmelser etter art. 46 nr. 2 bokstav c).
- **Modulvalg (modul 1, behandlingsansvarlig til behandlingsansvarlig) og klausulvalg: UVERIFISERT.** Teksten til beslutning (EU) 2021/914 er ikke åpnet.
- NeuroForges plattform kjører i en **AWS-region i USA ved oppstart; EU-region er planlagt** (D4). Et prosjekt som krever lagring bare i EØS, bør ikke bruke plattformen før EU-regionen finnes, eller må bruke standard personvernbestemmelser og en vurdering av overføringen (TIA).
- Helseforskningsloven § 29 krever REK-godkjenning for å sende **humant biologisk materiale** ut av Norge. Denne avtalen gjelder **bare data**.

## 8. Immaterielle rettigheter
- Hver part beholder sine bakgrunnsrettigheter og sine datasett.
- Resultater tilhører [parten som skaper dem / partene i fellesskap: valg for advokat].
- NeuroForges SDK med åpen kildekode forblir under Apache-2.0.
- Ingen av partene får lisens til den andres data utover Prosjektet.

## 9. Kostnader
Det betales ikke for dataene. Hver part dekker egne kostnader [med mindre vedlegg 1 sier noe annet]. *(Vederlagsfri deling holder også avtalen utenfor definisjonene av «sale» i amerikanske delstatslover. Advokat bekrefter dette for data fra USA.)*

## 10. Varighet, tilbakelevering og sletting
10.1 Avtalen varer til Prosjektets sluttdato i vedlegg 1, pluss [3] måneder.
10.2 Ved slutt eller oppsigelse skal mottakeren levere tilbake eller slette alle delte data og avledninger på individnivå innen [30] dager, etter valg fra parten som leverte dem, og bekrefte dette skriftlig. Unntak: oppbevaring som loven eller etikkgodkjenningen krever (for eksempel for etterprøving av forskningen) i [●] år. Dataene skal da sikres og ikke brukes videre.
10.3 Hver part kan si opp avtalen med [60] dagers varsel, eller straks ved vesentlig brudd på punkt 4–5.
10.4 Punktene 4, 5, 6.2, 10.2 og 11 gjelder også etter opphør.

## 11. Ansvar
- Hver part er ansvarlig for egen behandling. Ansvaret etter art. 82 er ikke begrenset.
- Under alternativ B fordeles ansvaret i vedlegg 2, uten å begrense de registrertes rettigheter (art. 26 nr. 3).
- Ellers gjelder ansvaret bare direkte tap, begrenset til [NOK ●]. Begrensningen gjelder ikke brudd på punkt 4.2 eller 4.4, forsett eller grov uaktsomhet (avtaleloven § 36).
- [Offentlige institusjoner: sjekk lovbestemte grenser for skadesløsholdelse – **UVERIFISERT**.]

## 12. Lovvalg og verneting
Norsk rett gjelder. Oslo tingrett er verneting. [For utenlandske institusjoner: advokat vurderer institusjonens hjemlands rett eller voldgift.]

## 13. Lukkede testsett for sammenligningstester (A7) – valgfritt bilag
13.1 **Formål.** Institusjonen sender inn metoder, for eksempel dekodere eller analyseløp, som testes på et lukket testsett. Institusjonen får aldri testdataene. Bidrar Institusjonen selv med testsettet, lagrer NeuroForge det uten å utlevere det.
13.2 **Data.**
- a) **Åpne spor:** bare datasett med lisens som tillater bruken, for eksempel CC0 eller CC-BY-4.0, med kreditering etter lisensen. Inneholder dataene opplysninger om personer i EU/EØS, gjelder GDPR likevel. En opphavsrettslisens avgjør ikke personvernspørsmålet.
- b) **Lukkede spor:** bare data fra NeuroForges forskningsdatabase der deltakerne har samtykket til boks (ii) og (iv) (og (v) hvis Institusjonen bidrar med data eller er medeier av sporet), eller Institusjonens egne data der Institusjonen garanterer at den har behandlingsgrunnlag og etikkgodkjenning.
13.3 **Bare analyse der dataene ligger.**
- Innsendte metoder kjøres i NeuroForges miljø.
- Bare poengsummer og aggregerte mål utleveres, etter reglene om minste cellestørrelse og forbud mot data på individnivå i vedlegg A1 til dpa-addendum-compute-to-data-cro.
- Forsøk på å hente ut testdata, for eksempel ved å kode dem inn i resultatene, fører til diskvalifisering og regnes som brudd på punkt 4.2.
13.4 **Ordbruk.** Resultatlister og rapporter kalles «evalueringsrapporter», **aldri «sertifisert» eller «validert»**. De inneholder ingen kliniske påstander.
13.5 **Tilbaketrekking.** Trekker en deltaker seg, fjernes dataene fra testsettet. Berørte resultater beregnes på nytt eller merkes. Resultater som allerede er publisert, kan stå med en merknad.
13.6 **Sponsorer.** En sponsor finansierer et spor, men får ikke tilgang til testdataene og har ingen innflytelse på poenggivingen. Institusjonens akademiske frihet (punkt 6.1) gjelder også for publisering av funn fra sammenligningstestene.

## Signatur
[Navn, stilling, dato] × 2 – signeres ikke før etikkgodkjenninger og DPIA foreligger.

---
### Vedlegg 1 – Prosjektbeskrivelse, datafelt, etikkreferanser, datoer
### Vedlegg 2 – Ordning etter art. 26 (bare alternativ B): ansvarstabell (informasjon, henvendelser, kontaktpunkt, DPIA, avvik, REK, sikkerhet, lagringstid)
### Vedlegg 3 – Navngitte personer i Prosjektet og sikkerhetskontakter

## Hjemmel / Legal basis
- Personvernforordningen, norsk tekst på Lovdata (åpnet 2026-09-26):
  - art. 9: https://lovdata.no/lov/2018-06-15-38/gdpr/a9
  - art. 17: https://lovdata.no/lov/2018-06-15-38/gdpr/a17
  - art. 19: https://lovdata.no/lov/2018-06-15-38/gdpr/a19
  - art. 26: https://lovdata.no/lov/2018-06-15-38/gdpr/a26
  - art. 28: https://lovdata.no/lov/2018-06-15-38/gdpr/a28
  - art. 35: https://lovdata.no/lov/2018-06-15-38/gdpr/a35
  - art. 46: https://lovdata.no/lov/2018-06-15-38/gdpr/a46
  - art. 89: https://lovdata.no/lov/2018-06-15-38/gdpr/a89
  - Art. 13, 14, 33, 34 og 82: **UVERIFISERT**.
- Personopplysningsloven § 9: https://lovdata.no/lov/2018-06-15-38/§9 (åpnet 2026-09-26).
- Helseforskningsloven §§ 2, 4, 9, 16, 29: https://lovdata.no/dokument/NL/lov/2008-06-20-44 (åpnet 2026-09-26).
- Datatilsynet, helse- og forskningsprosjekter: https://www.datatilsynet.no/personvern-pa-ulike-omrader/forskning-helse-og-velferd/helse-og-forskningsprosjekter/ (åpnet 2026-09-26).
- Standard personvernbestemmelser (EU) 2021/914: **UVERIFISERT**.
- Avtaleloven § 36: https://lovdata.no/dokument/NL/lov/1918-05-31-4/KAPITTEL_3 (åpnet 2026-09-26 av nfb-legal-commercial).
- Produktfakta: BLUEPRINT.md §8.3–8.4; DECISIONS.md D4, D6.
