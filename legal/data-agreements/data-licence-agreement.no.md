> UTKAST – ikke juridisk rådgivning. Må gjennomgås av norsk advokat før bruk.

# Lisensavtale for forskningsdata (avidentifiserte nevrale datasett)

Versjon [0.1] · [DATO] · Språk: engelsk versjon går foran ved motstrid [valg for advokat; engelsk versjon: data-licence-agreement.en.md]

**Forutsetninger – malen skal ikke brukes før alle fire er oppfylt:**
- det er gjennomført en vurdering av personvernkonsekvenser (DPIA, art. 35) som dekker lisensieringen;
- datasettet er samlet inn av NeuroForge **som behandlingsansvarlig**, og samtykket omfatter **boks (ii) (forskningsdatabasen) og den separate boks (vii) «data lisensiert til selskaper»** (samtykkeskjemaet; omfang `nf.pool` + `nf.data_licence.commercial`, CONSENT-SCOPES.no.md). Akademiske mottakere som ikke betaler, bruker den akademiske delingsavtalen og boks (v);
- REK/IRB-godkjenning dekker delingen der det kreves;
- advokat har gjennomgått avtalen.

Se legal\data-agreements\RISK-MEMO.md.

**Utenfor virkeområdet – malen skal ikke brukes til:**
- identifiserbare data;
- salg eller utlevering til forbrukere eller datameglere;
- data NeuroForge behandler **som databehandler** for kunder (forbudt etter MSA/DPA § 3.4);
- helseopplysninger (PHI) fra en virksomhet som omfattes av HIPAA.

## Parter
1. **[NeuroForge Bio AS]** (FORUTSETNING: norsk AS, **ikke stiftet ennå**), org.nr. [●], [adresse] («Lisensgiver»).
2. **[Lisenstakers navn]**, [reg.nr.], [adresse], [land] («Lisenstaker»).

## 1. Definisjoner
- **Datasettet:** det avidentifiserte datasettet beskrevet i **vedlegg A**, inkludert oppdateringer og utledede delsett levert av Lisensgiver.
- **Avidentifisert:** direkte identifikatorer er fjernet og deltakerkoder er erstattet med lisensspesifikke pseudonymer. Nøkkelen oppbevares bare hos Lisensgiver. **Partene er enige om at Datasettet fortsatt er personopplysninger (pseudonymisert, art. 4 nr. 5) og sannsynligvis særlige kategorier (art. 9).** Nevrale signaler kan i seg selv identifisere personer, så risikoen for reidentifisering kan ikke settes til null.
- **Tillatt formål:** formålet angitt i vedlegg A. Det må ligge innenfor samtykkene til hver bidragsyter i Datasettet.
- **Bidragsyter:** en person som har data i Datasettet.
- **Tilbaketrekkingsvarsel:** varsel fra Lisensgivers samtykkeregister om at en bidragsyter har trukket samtykket tilbake eller endret omfanget av det.
- **Avledet materiale:** kjennetegn (features), annoteringer, statistikk, modeller og annet som er laget av Datasettet.

## 2. Roller
2.1 Hver part er **selvstendig behandlingsansvarlig** for sin egen behandling. Lisenstaker bestemmer formål og midler innenfor Tillatt formål. Partene er ikke felles behandlingsansvarlige, med mindre de inngår en ordning etter art. 26.
2.2 Lisenstaker skal ha og dokumentere **eget behandlingsgrunnlag** etter art. 6 og et unntak etter art. 9 nr. 2. Der det er relevant, gjelder også nasjonal forskningslovgivning, REK-/IRB-godkjenning og amerikansk delstatslovgivning.

## 3. Lisens
3.1 Lisensgiver gir Lisenstaker en **ikke-eksklusiv, ikke-overførbar, ikke-underlisensierbar, tilbakekallelig** rett til å bruke Datasettet til Tillatt formål, i avtaleperioden, på de stedene og av de navngitte personene som står i vedlegg B.
3.2 **Tillatt bruk** (bare innenfor samtykkene):
- a) vitenskapelig forskning;
- b) utvikling og validering av Lisenstakers egne metoder eller produkter, **bare** der alle bidragsytere har krysset av for boks (vii) (`nf.data_licence.commercial`);
- c) trening av Lisenstakers egne modeller, **bare** der alle bidragsytere har krysset av for boks (vii). Boks (iii) gjelder bare NeuroForges interne trening, og boks (vi) gjelder bare modeller NeuroForge har trent og lisensierer ut. Ingen av dem gir grunnlag for denne avtalen.

3.3 **Forbudt bruk.** Lisenstaker skal ikke selv gjøre, eller la andre gjøre, noe av dette:
- a) **reidentifisere** eller forsøke å reidentifisere bidragsytere, **koble** Datasettet med andre data for å skille ut en person, eller kontakte en bidragsyter;
- b) selge, leie ut, **videreselge**, underlisensiere, publisere eller på annen måte utlevere data på individnivå, eller avledet materiale som gjør det mulig å skille ut en person;
- c) bruke Datasettet til praksis som er forbudt etter **KI-forordningen art. 5**, blant annet følelsesgjenkjenning på arbeidsplass eller i utdanning (unntatt av medisinske eller sikkerhetsmessige grunner), manipulerende eller subliminale teknikker, og biometrisk kategorisering som utleder sensitive egenskaper. Dette gjelder uansett hvor Lisenstaker er etablert;
- d) ta **kliniske beslutninger**, stille diagnose eller behandle enkeltpersoner, eller styre stimulering eller utstyr;
- e) treffe beslutninger om enkeltpersoners arbeid, utdanning, forsikring, kreditt eller bolig, eller bruke Datasettet til politiformål, overvåking eller «løgndeteksjon»;
- f) bruke Datasettet til reklame, markedsføringsprofiler eller salg til forbrukere eller datameglere;
- g) gå utover Tillatt formål eller bidragsyternes samtykker slik Lisensgiver har varslet dem.

## 4. Lisensgivers garantier
4.1 Lisensgiver garanterer, etter beste kunnskap og etter rimelig kontroll av samtykkeregisteret, at:
- a) hver bidragsyter har samtykket til utlevering til Lisenstakers mottakerkategori og til Tillatt formål;
- b) samtykkeversjoner og -omfang er registrert og oppsummert i vedlegg A;
- c) etikkgodkjenningene i vedlegg A er innhentet;
- d) Datasettet er avidentifisert som beskrevet i vedlegg A, og det er gjort en vurdering av risikoen for reidentifisering [referanse].
4.2 Ellers leveres Datasettet «som det er». Det gis ingen garanti for riktighet, egnethet eller klinisk gyldighet.

## 5. Lisenstakers plikter
5.1 **Sikkerhet.** Lisenstaker skal beskytte Datasettet med tiltak som minst tilsvarer Lisensgivers sikkerhetsbilag (MSA bilag 2 / DPA vedlegg II, S1–S16). Det omfatter blant annet:
- kryptering ved lagring og overføring;
- rollebasert tilgang begrenset til personene i vedlegg B;
- logging av tilgang;
- ingen kopier på private enheter;
- ingen opplasting til tredjeparts KI-tjenester som lagrer eller trener på innholdet.

5.2 **Videreoverføring.** Lisenstaker kan ikke overføre Datasettet eller gi tilgang til det utenfor egen organisasjon. Databehandlere (f.eks. skylagring) kan bare brukes med avtale etter art. 28 og Lisensgivers skriftlige forhåndssamtykke. **Overføring utenfor EØS** krever også Lisensgivers skriftlige forhåndssamtykke og et gyldig overføringsgrunnlag etter kapittel V, f.eks. Kommisjonens standard personvernbestemmelser (art. 46 nr. 2 bokstav c). [Modul (behandlingsansvarlig til behandlingsansvarlig, modul 1) bekreftes av advokat. **UVERIFISERT**: teksten til beslutning 2021/914 er ikke åpnet.]

5.3 **Rettigheter.** Lisenstaker bistår Lisensgiver med å besvare bidragsyteres henvendelser, og videresender henvendelser den mottar innen [5] virkedager.

5.4 **Publisering.** Lisenstaker kan bare publisere aggregerte resultater som ikke gjør det mulig å skille ut en person. Publikasjonen skal henvise til Datasettet og etikkgodkjenningene.

## 6. Tilbaketrekking og sletting
6.1 Lisensgiver sender **tilbaketrekkingsvarsel** gjennom samtykkeregisteret, med de berørte lisenspseudonymene. Dette gjennomfører den behandlingsansvarliges plikt til å varsle mottakere (art. 19) og retten til sletting etter tilbaketrekking (art. 17 nr. 1 bokstav b).

6.2 Innen **[30] dager** etter et tilbaketrekkingsvarsel skal Lisenstaker:
- a) slette bidragsyterens data i alle kopier, også i sikkerhetskopier når de roteres. Sikkerhetskopier skal ikke gjenopprettes til bruk i mellomtiden;
- b) stanse bruken av dataene i pågående analyser;
- c) for trente modeller: **trene på nytt uten bidragsyteren**, eller slutte å bruke de berørte modellversjonene, ved neste planlagte trening og senest etter [90] dager. Partene er innforstått med at **sertifisert «avlæring» (machine unlearning) ikke finnes og ikke loves**;
- d) sende et signert **slettebevis** som viser hva som er gjort.

6.3 Aggregerte resultater som allerede er publisert, trenger ikke trekkes tilbake. Unntaket for forskning i art. 17 nr. 3 bokstav d kan gjelde i enkelttilfeller, men bare etter skriftlig bekreftelse fra Lisensgiver.

6.4 Ved utløp eller oppsigelse skal Lisenstaker slette Datasettet og alt avledet materiale på individnivå innen [30] dager, og bekrefte slettingen. Aggregerte resultater og modeller som er trent på nytt etter 6.2, kan beholdes [valg for advokat/eier].

## 7. Avvik
Lisenstaker skal varsle Lisensgiver **uten ugrunnet opphold, og senest [24] timer etter at Lisenstaker ble kjent med** et brudd på personopplysningssikkerheten eller mistanke om reidentifisering. Partene samarbeider slik at hver behandlingsansvarlig kan oppfylle sine plikter etter art. 33 og 34.

## 8. Revisjon
Lisenstaker skal føre logg over tilgang og bruk. Lisensgiver, eller en uavhengig revisor med taushetsplikt, kan kontrollere etterlevelsen én gang per [12] måneder, eller etter et avvik. Varselfristen er [30] dager, og [5] dager etter et avvik.

## 9. Vederlag
[Beløp / kostnadsdekning] etter vedlegg C. [Valg for eier. Advokat vurderer om vederlag gjør avtalen til et «sale» etter amerikansk delstatslovgivning. I så fall kreves boks (vii), som nevner «salg», for bidragsytere i USA; se RISK-MEMO § 5.]

## 10. Varighet og opphør
10.1 Avtalen varer i [24] måneder fra signering, med mindre den avsluttes tidligere.
10.2 Lisensgiver kan heve avtalen **med umiddelbar virkning** hvis Lisenstaker bryter punkt 3.3, 5 eller 7, eller hvis videre deling blir ulovlig eller går utover samtykket. Hver part kan si opp avtalen med [90] dagers varsel.
10.3 Punktene 3.3, 5, 6, 7, 8, 11 og 13 gjelder også etter opphør.

## 11. Ansvar
11.1 Hver part er ansvarlig for egen behandling som behandlingsansvarlig. Ansvaret etter art. 82 er ikke begrenset.
11.2 Lisenstaker holder Lisensgiver skadesløs for krav, gebyrer og kostnader som skyldes Lisenstakers brudd på punkt 3.3 eller 5.
11.3 Ellers er hver parts ansvar begrenset til [det høyeste av vederlaget for 12 måneder eller NOK [●]]. Begrensningen gjelder **ikke** brudd på punkt 3.3 (reidentifisering, videresalg, forbudt bruk), forsett eller grov uaktsomhet, eller der ufravikelig lov sier noe annet (avtaleloven § 36).

## 12. Konfidensialitet
Datasettet og vedlegg A er Lisensgivers konfidensielle informasjon.

## 13. Lovvalg og verneting
Norsk rett gjelder. Oslo tingrett er avtalt verneting. [Voldgift som alternativ, som i MSA: valg for advokat.]

## Signatur
Skal ikke signeres før forutsetningene øverst er oppfylt. [Navn, stilling, dato] × 2.

---
### Vedlegg A – Datasett og samtykker
| Punkt | Innhold |
|---|---|
| Navn / versjon / hash | [●] |
| Modaliteter, kanaler, samplingsrate, avledede kjennetegn | [●] |
| Antall bidragsytere; jurisdiksjoner (EØS / CO / CA / CT / MT / annet) | [●] |
| Samtykkeversjon(er) + hash; samtykker som finnes for **alle** (boks (ii) `nf.pool` og (vii) `nf.data_licence.commercial` kreves; list andre som finnes) | [●] |
| Etikkgodkjenning (REK-ref. [●] / IRB-ref. [●]) | [●] |
| Avidentifiseringsmetode; ref. til vurdering av reidentifiseringsrisiko | [●] |
| Tillatt formål (spesifikt) | [●] |
| DPIA-referanse | [●] |

### Vedlegg B – Lisenstakers lokasjoner, navngitte personer, sikkerhetskontakt
[●]

### Vedlegg C – Vederlag
[●]

## Hjemmel / Legal basis
- Personvernforordningen, norsk tekst på Lovdata (åpnet 2026-09-26):
  - art. 4: https://lovdata.no/lov/2018-06-15-38/gdpr/a4
  - art. 9: https://lovdata.no/lov/2018-06-15-38/gdpr/a9
  - art. 17: https://lovdata.no/lov/2018-06-15-38/gdpr/a17
  - art. 19: https://lovdata.no/lov/2018-06-15-38/gdpr/a19
  - art. 26: https://lovdata.no/lov/2018-06-15-38/gdpr/a26
  - art. 28: https://lovdata.no/lov/2018-06-15-38/gdpr/a28
  - art. 35: https://lovdata.no/lov/2018-06-15-38/gdpr/a35
  - art. 46: https://lovdata.no/lov/2018-06-15-38/gdpr/a46
  - Art. 33, 34 og 82 er ikke åpnet: **UVERIFISERT**.
- Standard personvernbestemmelser (EU) 2021/914: **UVERIFISERT**. KI-forordningen art. 5: **UVERIFISERT** (EUR-Lex lastet ikke), jf. market\regulation.md §5.
- Connecticut PA 25-113: https://www.cga.ct.gov/2025/ACT/PA/PDF/2025PA-00113-R00SB-01295-PA.PDF (åpnet 2026-09-26).
- California SB 1223: https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202320240SB1223 (åpnet 2026-09-26).
- Avtaleloven § 36: https://lovdata.no/dokument/NL/lov/1918-05-31-4/KAPITTEL_3 (åpnet 2026-09-26 av nfb-legal-commercial).
- Helseforskningsloven § 9: https://lovdata.no/dokument/NL/lov/2008-06-20-44 (åpnet 2026-09-26).
- Produktfakta: BLUEPRINT.md §8.3–8.4; DPA § 3.4.
