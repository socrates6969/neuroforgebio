> UTKAST – ikke juridisk rådgivning. Må gjennomgås av norsk advokat før bruk.

# Hovedavtale om abonnement (Master Subscription Agreement, MSA) – norsk oversettelse

Malversjon [0.1] · [DATO] · Gjeldende språk: **engelsk** (forslag for internasjonale kommersielle avtaler); denne norske teksten er en oversettelse. Ved motstrid går msa.en.md foran – valg for advokat (for norske kunder kan norsk velges).

**Mellom** [NeuroForge Bio AS] (FORUTSETNING: norsk aksjeselskap, **ikke stiftet ennå**), org.nr. [●], [adresse] («**NeuroForge**»), **og** [Kundens navn], [org.nr.], [adresse] («**Kunden**»). Hver for seg «Part».

**Struktur.** Denne MSA + hver signerte bestillingsskjema (Order Form) + Bilag 1 (SLA) + Bilag 2 (Sikkerhet) + Bilag 3 (Databehandleravtale, dpa.no.md) + retningslinjer for akseptabel bruk (aup.no.md) + [Bilag 4 BAA, bare hvis uttrykkelig tilbudt – PLANLAGT, tilbys ikke nå]. Rangfølge ved motstrid: (1) DPA/BAA for personopplysninger; (2) bestillingsskjema (bare for kommersielle vilkår det uttrykkelig fraviker); (3) MSA; (4) SLA; (5) AUP; (6) dokumentasjon.

## 1. Definisjoner
- **Tjenesten**: NeuroForges driftede plattform beskrevet i bestillingsskjemaet (f.eks. samtykke- og slettelogg, proveniensgraf, pipelines, modellregister) med konsoll og API-er. Status ved signering: funksjonene er **utformet/planlagt** med mindre bestillingsskjemaet oppgir dem som generelt tilgjengelige.
- **Beta-funksjoner**: funksjoner merket beta, forhåndsvisning, tidlig tilgang o.l. Unntatt fra SLA og garantier (pkt. 9.3).
- **Kundedata**: alle data som legges inn i Tjenesten av eller for Kunden, herunder nevrale signaler, opptak, metadata, samtykkeposter, pipelinedefinisjoner og modellvekter Kunden produserer.
- **Resultater (Outputs)**: resultater Tjenesten genererer fra Kundedata etter Kundens instruks (f.eks. prosesserte datasett, avledede trekk, trente modeller, slettesertifikater, provenienseksporter).
- **Aggregerte tjenestemålinger**: tekniske bruks- og ytelsesdata om driften av Tjenesten (antall API-kall, jobbtid, feilrater, lagringsvolum) **uten innhold fra Kundedata**, og som ikke identifiserer Kunden, brukere eller registrerte.
- **SDK**: NeuroForges utviklingsverktøy. Åpne deler under Apache-2.0; øvrige under plattform-/klientlisensen (sdk-licence.no.md).
- **Personopplysninger, behandlingsansvarlig, databehandler, særlige kategorier**: som i forordning (EU) 2016/679 (GDPR).
- **Nevrale data**: data generert ved måling av aktivitet i sentral- eller perifernervesystemet, herunder slik amerikanske delstatslover definerer dem.
- **Vederlag** og **Abonnementsperiode**: som i bestillingsskjemaet.

## 2. Bruksrett
2.1 På vilkårene i MSA og mot betaling gir NeuroForge Kunden en ikke-eksklusiv, ikke-overdragbar (unntatt etter pkt. 17.2) rett, uten rett til underlisens, i Abonnementsperioden til at Autoriserte brukere bruker Tjenesten til Kundens interne forskning og utvikling, innenfor bruksgrensene i bestillingsskjemaet.
2.2 **Autoriserte brukere**: Kundens ansatte, studenter og konsulenter som handler for Kunden. Kunden svarer for deres handlinger og for at påloggingsdata holdes hemmelig.
2.3 **Konsernselskaper/samarbeidspartnere**: bare hvis navngitt i bestillingsskjemaet.

## 3. Begrensninger
Kunden skal ikke (og skal ikke la andre): (a) selge, videreselge, leie ut eller drive servicebyrå med Tjenesten med mindre bestillingsskjemaet tillater det; (b) dekompilere eller foreta omvendt utvikling av lukkede komponenter, utover det ufravikelig lov tillater (**UVERIFISERT**); (c) omgå sikkerhet eller bruksgrenser; (d) bruke konfidensiell informasjon fra NeuroForge til å bygge et konkurrerende produkt; (e) bruke Tjenesten i strid med AUP, pkt. 10 eller pkt. 11; (f) laste opp skadevare.

## 4. Kundedata og Resultater – eierskap
4.1 **Kunden eier sine data.** Mellom Partene beholder Kunden (eller dennes lisensgivere og de registrerte) alle rettigheter til Kundedata og **Resultater**. NeuroForge får ikke eiendomsrett.
4.2 **Begrenset lisens til NeuroForge.** Kunden gir NeuroForge en ikke-eksklusiv, verdensomspennende, vederlagsfri lisens i avtaletiden (og perioden i pkt. 15) til å lagre, kopiere, overføre, behandle og vise Kundedata **bare så langt det trengs for å levere, sikre og gi støtte for Tjenesten**, i samsvar med Kundens dokumenterte instrukser og databehandleravtalen.
4.3 **Ingen trening på Kundedata.** NeuroForge skal **ikke** bruke Kundedata eller Resultater (herunder nevrale data, avledede trekk og modellvekter) til å trene, finjustere, evaluere eller forbedre NeuroForges eller tredjeparts modeller eller produkter, og skal ikke selge, lisensiere eller dele Kundedata, **med mindre Kunden gir et eget, spesifikt, skriftlig samtykke (opt-in)** signert av en autorisert representant, som angir datasett, formål, avidentifisering, varighet og tilbakekall. Samtykkeomfang i Tjenesten (f.eks. «modelltrening») erstatter ikke dette.
4.3a **Forskningspool (valgfritt, PLANLAGT; standard AV).** Kunden kan velge å bidra med avidentifiserte kopier av utvalgte datasett til NeuroForges forskningspool ved å signere **tilleggsavtalen om forskningspool** (research-pool-addendum.no.md), som er det skriftlige samtykket etter pkt. 4.3. Hovedvilkår: bare data fra personer som har krysset av for tilsvarende samtykkebokser (forskningspool / intern KI-trening / lisensiert modelltrening / fremtidig forskning / partnerdeling / datalisensiering – boks (ii)–(vii) i legal\data-agreements\contributor-consent.no.md; omfang etter legal\data-agreements\CONSENT-SCOPES.no.md) kopieres; Kunden beholder eiendomsretten og NeuroForge får en begrenset lisens bare for disse formålene; Kunden garanterer samtykkene; tilbaketrekking når som helst per datasett eller person via samtykkeloggen (sletting i poolen, `retrain_required` på modeller, ingen sertifisert «unlearning», allerede delte kopier kan ikke kalles tilbake); ikke salg av identifiserbare data; motytelsen er **tjenestekreditter, ikke penger**, og gitte kreditter tilbakeføres ikke ved tilbaketrekking [forhandlingsbart]. Avidentifiserte nevrale data behandles fortsatt som personopplysninger. Poolen er planlagt åpnet i måned 18–30 (ESTIMAT); inntil da tilbys ikke valget.
4.4 **Aggregerte tjenestemålinger.** NeuroForge kan samle inn og bruke slike målinger bare for å drifte, sikre, fakturere og forbedre ytelse og pålitelighet, og publisere aggregert statistikk som ikke med rimelighet kan knyttes til Kunden, brukere eller registrerte. Målingene skal aldri omfatte signalinnhold, avledede trekk, modellvekter, pseudonymer eller samtykkeinnhold. [Forhandlingsbart: Kunden kan kreve ingen publisering.]
4.5 **Kundens ansvar.** Kunden svarer for at Kundedata er riktige og lovlige, og for å ha alle rettigheter, samtykker, godkjenninger og behandlingsgrunnlag (se pkt. 10).
4.6 **Valgfri KI-assistent («spør dataene dine») – PLANLAGT.** (a) Assistenten er valgfri per leietaker, **AV som standard**, og kan bare slås på av en administrator hos leietakeren. Kunden kan slå den av når som helst. (b) Når den er på, sendes bare metadata og proveniens (studie-/datasettbeskrivelser, pipeline- og proveniensgrafinformasjon, kanalklassifiseringer) og brukerens spørsmål til en tredjeparts leverandør av KI-modeller, etter planen Anthropic (underdatabehandler etter DPA vedlegg III). Den sender **aldri** rå nevrale signaler eller direkte identifikatorer. Feltene styres av en tillatelsesliste, og person-ID-er, fritekst og kliniske felt sladdes på serversiden. (c) Kundedata som sendes til assistenten, brukes ikke til å trene NeuroForges eller leverandørens modeller (pkt. 4.3). (d) Svarene er maskingenererte, **kan være feil eller ufullstendige**, og er **ikke medisinske, juridiske eller regulatoriske råd**. Kunden må kontrollere svarene før de brukes, og skal ikke bruke dem til kliniske beslutninger (pkt. 10.1). Så lenge assistenten er i beta, er den unntatt SLA og garantien i pkt. 9.1.

## 5. NeuroForges immaterielle rettigheter
5.1 NeuroForge og lisensgivere beholder alle rettigheter til Tjenesten, SDK, dokumentasjon, pipelinemaler, regelsett og forbedringer (unntatt Kundedata og Resultater).
5.2 **Tilbakemeldinger** kan NeuroForge bruke fritt, forutsatt at de ikke inneholder Kundedata eller Kundens konfidensielle informasjon, og at Kunden ikke navngis som kilde uten samtykke.
5.3 Åpen kildekode reguleres av egne lisenser (sdk-licence.no.md).

## 6. Konfidensialitet
6.1 «Konfidensiell informasjon» er ikke-offentlig informasjon som er merket konfidensiell eller som med rimelighet må forstås slik. Kundedata er Kundens konfidensielle informasjon.
6.2 Mottakeren skal bare bruke den for å oppfylle MSA, beskytte den med minst rimelig aktsomhet og bare gi den til personell og rådgivere med tilsvarende taushetsplikt og tjenstlig behov.
6.3 Unntak: offentlig kjent uten brudd, allerede kjent, selvstendig utviklet eller lovlig mottatt fra tredjepart. Pålagt utlevering etter lov eller rettsavgjørelse er tillatt med varsel (der lovlig) og samarbeid om å begrense den.
6.4 Plikten gjelder i [5] år etter opphør; for forretningshemmeligheter og Kundedata så lenge de er det.

## 7. Sikkerhet
NeuroForge skal gjennomføre tiltakene i **Bilag 2**. Bilaget beskriver **utformede/planlagte tiltak**; NeuroForge påberoper seg **ingen** sertifisering (SOC 2, ISO 27001, HITRUST o.l.) før en rapport foreligger og er oppført i bestillingsskjemaet. Tiltak kan oppdateres så lenge beskyttelsesnivået ikke reduseres vesentlig.

## 8. Vederlag, betaling og avgifter
8.1 Kunden betaler Vederlaget i bestillingsskjemaet, fakturert [årlig forskuddsvis], forfall [30] dager netto.
8.2 Forsinkelsesrente etter forsinkelsesrenteloven (**UVERIFISERT**) [eller [●] % for utenlandske kunder]. Etter [15] dagers skriftlig varsel kan NeuroForge stanse Tjenesten for ubestridte forfalte beløp (ikke sletting; pkt. 15 gjelder).
8.3 **Avgifter.** Vederlag er eksklusive merverdiavgift. For norske kunder tillegges MVA med gjeldende sats [i dag 25 % – **UVERIFISERT**]. For næringskunder utenfor Norge faktureres uten MVA der reglene om omvendt avgiftsplikt/leveringssted tillater det, og Kunden beregner lokal avgift selv [**UVERIFISERT** – regnskapsfører bekrefter]. Kildeskatt: Kunden bruttoberegner med mindre skatteavtalefritak er dokumentert.
8.4 Prisendring ved fornyelse med [60] dagers varsel; tak [●] % [forhandlingsbart].

## 9. Garantier og ansvarsfraskrivelser
9.1 NeuroForge garanterer i Abonnementsperioden at (a) generelt tilgjengelige funksjoner i det vesentlige virker i samsvar med gjeldende dokumentasjon, og (b) sikkerheten i Bilag 2 ikke reduseres vesentlig. Beføyelse: NeuroForge retter innen rimelig tid; lykkes ikke det innen [30] dager kan Kunden si opp berørt bestillingsskjema og få forholdsmessig refusjon av forskuddsbetalt, ubrukt vederlag. [I tillegg servicekreditter etter Bilag 1.]
9.2 Hver Part garanterer at den har fullmakt til å inngå MSA.
9.3 **Fraskrivelse.** Utover det som uttrykkelig står, leveres Tjenesten, SDK, Beta-funksjoner, gratis-/akademiske nivåer og Resultater «som de er». NeuroForge garanterer ikke feilfri eller uavbrutt drift, at Resultater (artefaktfjerning, klassifiseringer, modellprediksjoner, jurisdiksjonsklassifisering i regelmotoren) er riktige eller egnet til kliniske, regulatoriske eller juridiske formål, eller at regelsettene gjenspeiler gjeldende rett. Regelsett har `review_status`; oppføringer som ikke er merket «counsel-reviewed» er utkast. Så langt loven tillater, fraskrives underforståtte garantier.

## 10. Regulatorisk forbehold og Kundens etterlevelse
10.1 **Ikke-medisinsk forskningsprogramvare.** Tjenesten er utformet som forsknings- og utviklingsprogramvare for lagring, konvertering, behandling, revisjon og styring av nevrale data. Den er **ikke** medisinsk utstyr, er **ikke** beregnet på diagnose, forebygging, overvåking, prediksjon, prognose, behandling eller lindring av sykdom eller skade, og skal **ikke** brukes til eller som støtte for kliniske beslutninger om enkeltpasienter eller til å styre stimulering eller utstyr i lukket sløyfe. [MDR 2017/745 art. 2 nr. 1 – **UVERIFISERT**.]
10.2 **Kundens produktregulering.** Bruker Kunden Tjenesten, SDK eller Resultater i eller for medisinsk utstyr eller annet regulert produkt (herunder BCI), er **Kunden** som produsent alene ansvarlig for alle regulatoriske plikter (FDA 510(k)/De Novo/PMA/IDE, MDR, IEC 62304-lignende livssyklus, klinisk evaluering, markedsovervåking). NeuroForge kan levere dokumentasjon (SBOM, versjonsnotater, sporbarhetseksport) som leverandør av hyllevare/SOUP; det gjør ikke NeuroForge til produsent, og dokumentasjonen leveres «som den er» med mindre egen kvalitetsavtale inngås.
10.3 **Etikk og godkjenninger.** Kunden skal innhente og opprettholde nødvendige godkjenninger fra REK/etikkomité/IRB og eventuelt myndigheter for studier hvis data behandles i Tjenesten.
10.4 **Samtykke og behandlingsgrunnlag.** Kunden er behandlingsansvarlig (eller handler for denne) og innestår for gyldig grunnlag etter GDPR art. 6 **og** unntak etter art. 9 nr. 2 der særlige kategorier inngår (f.eks. helseopplysninger, eller data som behandles for å entydig identifisere en person), og for at nødvendig informasjon er gitt. Der amerikanske delstatslover behandler nevrale data som sensitive (f.eks. Colorado HB24-1058, California SB 1223, Connecticut Public Act 25-113, Montana SB 163) er Kunden ansvarlig for eventuelle opt-in-samtykker, retten til å begrense bruk og øvrig gjeldende lov (også HIPAA der Kunden er «covered entity» eller «business associate» – se pkt. 10.6).
10.4a **Nevrale data er ikke anonyme.** Kunden erkjenner at pseudonymiserte eller avidentifiserte nevrale opptak fortsatt er personopplysninger (risiko for reidentifisering); partene skal ikke kalle dem «anonymiserte» (DPA pkt. 13.4).
10.5 **Verktøy, ikke garanti for etterlevelse.** Samtykkelogg, regelmotor, sletting og sertifikater er verktøy. Bruk av dem gjør ikke i seg selv Kunden etterlevende, og NeuroForge gir ikke juridisk rådgivning.
10.6 **HIPAA.** Kunden skal ikke laste opp PHI (HIPAA) uten at en BAA er signert av begge. **BAA er PLANLAGT og tilbys ikke nå.**
10.7 **EUs KI-forordning.** Kunden skal ikke bruke Tjenesten, SDK eller Resultater til praksis forbudt etter artikkel 5 i forordning (EU) 2024/1689, herunder utledning av følelser på arbeidsplassen eller i utdanningsinstitusjoner (unntatt av medisinske eller sikkerhetsmessige grunner), manipulerende eller subliminale teknikker, eller biometrisk kategorisering som utleder sensitive egenskaper. Bruksbegrensningsflagg i modellregisteret skal respekteres. Kunden svarer for egne plikter som tilbyder eller idriftsetter. [**UVERIFISERT** mot EUR-Lex.]

## 11. Eksportkontroll og sanksjoner
11.1 Partene skal overholde gjeldende eksportkontroll- og sanksjonsregler, herunder eksportkontrolloven med forskrifter, forordning (EU) 2021/821 (flerbruk) slik den gjelder i Norge [**UVERIFISERT**], og EUs, FNs, Norges, Storbritannias og USAs sanksjoner så langt de gjelder.
11.2 Kunden innestår for at verken den eller Autoriserte brukere befinner seg i, eller eies/kontrolleres fra, et land under omfattende sanksjoner eller står på sanksjonslister, og skal ikke eksportere eller gi tilgang i strid med reglene. Kryptografisk funksjonalitet kan være flerbruksregulert [klassifisering **UVERIFISERT**].
11.3 NeuroForge kan straks stanse tilgang der det er nødvendig for å overholde reglene.

## 12. Ansvarsbegrensning
12.1 **Indirekte tap** (tapt fortjeneste, omsetning, goodwill, forventede besparelser) erstattes ikke, heller ikke datatap utover pkt. 12.3 [forhandlingsbart].
12.2 **Alminnelig tak.** Hver Parts samlede ansvar per 12-månedersperiode er begrenset til **vederlaget betalt og som skal betales de siste 12 månedene** før ansvarsgrunnlaget oppsto [gratis-/akademisk nivå: [EUR 1 000] – ESTIMAT/forhandlingsbart].
12.3 **Forhøyet tak for personvern.** For brudd på pkt. 6 (for Kundedata), pkt. 7/Bilag 2 eller databehandleravtalen er NeuroForges samlede ansvar begrenset til **[3] × vederlaget de foregående 12 månedene** [eller EUR [●] om høyere] – **forhandlingsbart**; omfatter rimelige kostnader til varsling av registrerte og myndigheter og gjenoppretting fra sikkerhetskopi.
12.4 **Ubegrenset:** (a) grov uaktsomhet eller forsett; (b) Kundens betalingsplikt; (c) skadesløsholdelse etter pkt. 13 [forhandlingsbart, ofte eget tak]; (d) Kundens brudd på pkt. 3, 10.7 eller 11; (e) ansvar som ikke kan begrenses etter ufravikelig lov.
12.5 **Ufravikelig lov.** Begrensningene gjelder bare så langt loven tillater og kan lempes etter avtaleloven § 36. Overtredelsesgebyr ilagt en Part bæres av denne, med mindre det skyldes den andre Partens brudd [advokat: regress for GDPR-gebyr].

## 13. Skadesløsholdelse
13.1 **NeuroForge** forsvarer Kunden mot tredjepartskrav om at Tjenesten (unntatt åpen kildekode, Kundedata og kombinasjoner NeuroForge ikke har levert) krenker immaterielle rettigheter, og betaler rettskraftig tilkjent eller forlikt beløp. NeuroForge kan skaffe fortsatt bruksrett, endre Tjenesten eller si opp mot refusjon av ubrukt forskudd.
13.2 **Kunden** forsvarer NeuroForge mot tredjepartskrav (også fra registrerte eller myndigheter) som skyldes Kundedata, manglende grunnlag/samtykke/godkjenning, brudd på AUP, pkt. 10 eller 11, eller Kundens regulerte produkter.
13.3 **Fremgangsmåte:** straks skriftlig varsel, full kontroll over forsvar og forlik for den som holder skadesløs (ingen innrømmelse på den andres vegne uten samtykke), rimelig samarbeid for dennes regning.

## 14. Varighet, suspensjon og oppsigelse
14.1 MSA løper til alle bestillingsskjemaer er avsluttet. Hvert bestillingsskjema fornyes med [12] måneder om ikke en Part sier opp med [60] dagers varsel før periodens slutt.
14.2 Hevning ved vesentlig mislighold som ikke er rettet innen [30] dager etter skriftlig varsel, eller straks ved insolvens/konkurs [håndhevbarhet – **UVERIFISERT**].
14.3 NeuroForge kan stanse tilgang for å avverge overhengende skade, ved alvorlig AUP-brudd eller etter pkt. 11.3, med varsel når mulig og avgrenset i omfang og tid.
14.4 **Bytte av leverandør (EUs dataforordning).** Der forordning (EU) 2023/2854 kapittel VI gjelder, kan Kunden si opp med høyst **to måneders** varsel for å bytte leverandør eller gå til egen infrastruktur; pkt. 15.3 gjelder. [Gjennomføring i Norge via EØS og unntak for beta/ikke-produksjon og skreddersydde tjenester (art. 31) – **UVERIFISERT**.]
14.5 Ved hevning grunnet NeuroForges mislighold refunderes ubrukt forskudd. Pkt. 4, 5, 6, 8 (utestående), 12, 13, 15 og 16 gjelder etter opphør.

## 15. Tilbakelevering, sletting og bytteassistanse
15.1 **Eksport når som helst** i dokumenterte, vanlige, maskinlesbare formater (BIDS/NWB, PROV-JSON/OpenLineage, CSV/JSON, opprinnelige filformater) [utformet/planlagt].
15.2 **Etter opphør.** I **[30]** dager (hentefrist; minst 30 dager der dataforordningen gjelder) kan Kunden eksportere; deretter sletter NeuroForge Kundedata fra produksjonssystemer innen **[30]** nye dager, og data i sikkerhetskopier gjøres uleselige ved destruksjon av leietaker- og subjektnøkler (kryptografisk sletting) og utløper med kopisyklusen [≤ [35] dager – ESTIMAT]. Skriftlig bekreftelse på forespørsel. Lovpålagt oppbevaring (f.eks. fakturaer) unntatt.
15.3 **Bytteassistanse** med overføring av data og digitale eiendeler, herunder dokumentasjon av formater, i en overgangsperiode på inntil **30 dager** (kan forlenges med begrunnelse når teknisk umulig). Byttegebyr: [ingen] / [høyst direkte kostnader frem til 12. januar 2027, deretter ingen] der dataforordningen gjelder [**UVERIFISERT**].
15.4 **Ærlige begrensninger.** Sletting etter tilbaketrekking skjer som utformet: rådata og data knyttet til én person slettes og nøkler destrueres; aggregerte artefakter kjøres på nytt eller gravlegges etter leietakers policy; **trente modeller merkes `retrain_required` og trenes på nytt uten personen (ingen sertifisert «unlearning» tilbys)**; og **data eller Resultater som allerede er eksportert ut av Tjenesten kan ikke kalles tilbake** – de listes for Kundens oppfølging.

## 16. Lovvalg og tvister
16.1 **Norsk rett**, uten lovvalgsregler og CISG.
16.2 Forhandlinger i god tro mellom ledelsen i [30] dager; deretter **Oslo tingrett** som eksklusivt verneting.
16.3 **Alternativer for advokat:** (a) for kunder i USA eller utenfor Luganokonvensjonen: voldgift i [Oslo] etter reglene til [Oslo Chamber of Commerce Arbitration Institute] eller [ICC], engelsk språk, én voldgiftsdommer – enklere fullbyrdelse etter New York-konvensjonen [**UVERIFISERT**]; (b) kundens hjemrett for store kunder; (c) offentlige kunder kan kreve egne vilkår (f.eks. SSA).
16.4 Midlertidig forføyning kan begjæres ved enhver kompetent domstol.

## 17. Alminnelige bestemmelser
17.1 **Force majeure** (ikke betalingsplikt); rett til oppsigelse etter > [60] dager.
17.2 **Overdragelse** krever samtykke, unntatt til etterfølger ved fusjon eller salg av vesentlig virksomhet, med varsel.
17.3 **Underleverandører** kan brukes; NeuroForge svarer for dem; underdatabehandlere etter databehandleravtalen.
17.4 **Omtale og påstander**: ikke bruk av den andres navn/logo uten skriftlig samtykke. Ingen av partene skal i avtaler eller markedsføring omtale Tjenesten som medisinsk utstyr, klinisk validert, eller sertifisert/i samsvar med en sikkerhets- eller personvernstandard (f.eks. «HIPAA-compliant», «SOC 2-sertifisert») før det er sant og dokumentert.
17.5 **Varsler** skriftlig til adressene i bestillingsskjemaet; e-post holder for driftsvarsler.
17.6 **Hele avtalen**; endringer bare skriftlig signert av begge; innkjøpsvilkår/klikkvilkår gjelder ikke.
17.7 Delvis ugyldighet, ingen avkall, selvstendige parter, ingen tredjepartsrettigheter (unntatt etter DPA/SCC).
17.8 Elektronisk signering og signering i flere eksemplarer tillatt.

---
## Bilag 2 – Sikkerhet (utformede/planlagte tiltak; ingen sertifiseringer påberopes)
Kilder: architecture\BLUEPRINT.md §8 og innspill fra nfb-security (legal\commercial\_security-input.md; SEC-IDer i security\SECURITY-REQUIREMENTS.md), 2026-09-26. NeuroForge holder bilaget oppdatert og opplyser ved oppstart hvilke tiltak som er i produksjon.

| # | Område | Forpliktelse (utformet med mindre annet står) |
|---|---|---|
| S1 | Kryptering under overføring | TLS 1.3 på plattformendepunkter; eldre versjoner avvises (utformet; SEC-030). |
| S2 | Kryptering ved lagring | AES-256-GCM konvoluttkryptering; nøkler i sky-KMS i hierarki rot → leietakernøkkel → egen nøkkel per registrert (utformet; SEC-030, SEC-031). |
| S3 | Nøkkelforvaltning | Rotasjon minst årlig og ved mistanke om kompromittering; sletting av nøkler krever ventetid og to-personsgodkjenning unntatt i kundeinitiert slettejobb; kryptografisk sletting gjør alle kopier, også sikkerhetskopier, uleselige (utformet; SEC-033, SEC-034, SEC-123). |
| S4 | Tilgangsstyring | SSO med MFA for alle; phishing-resistente autentikatorer (passkeys/WebAuthn) for administratorer; ikke SMS; minste privilegium; leietakerisolasjon i applikasjon, database (radnivå) og nøkler; fireøyneprinsipp for råeksport av sensitive data (utformet; SEC-010–025). Egen instans/VPC: veikart. |
| S5 | Personelltilgang | Ingen stående tilgang til produksjonsdata for NeuroForge-ansatte; nødtilgang tidsbegrenset (≤ 4 t), begrunnet, varslet og logget; kvartalsvis tilgangsgjennomgang (utformet; SEC-025, SEC-114). Taushetserklæring for alle. |
| S6 | Logging og revisjon | Tilføyingslogg med hashkjede på WORM-lagring for autentisering, all lesing/eksport, administratorhandlinger, samtykkeendringer, nøkkeloperasjoner og slettinger; lagring [3] år som standard og [minst 6] år for BAA-kunder [bekreftes juridisk]; applikasjonslogger uten signaldata, identifikatorer og fritekst; Kundens revisorrolle kan eksportere og verifisere loggen (utformet; SEC-100, SEC-101, SEC-105, SEC-147). |
| S7 | Varsling av hendelser/brudd | Varsel til Kunden om brudd på personopplysningssikkerheten eller vesentlig sikkerhetshendelse uten ugrunnet opphold og **i alle tilfeller innen [24] timer etter bekreftelse**, med minsteinnhold etter security\INCIDENT-RESPONSE.md §6 og oppdateringer (DPA pkt. 8). Art. 33 nr. 2 krever bare «uten ugrunnet opphold»; 24 t gir behandlingsansvarlige mulighet til å rekke 72 t og NIS2-kunder sitt 24 t-tidlig varsel. |
| S8 | Sårbarhetshåndtering | Mål (ikke garanti) for retting av bekreftede sårbarheter: **14 dager (kritisk), 30 dager (høy), 90 dager (middels)**; varsler med SBOM/VEX; forhåndsvarsel til kunder som bygger NeuroForge-komponenter inn i medisinsk utstyr (planlagt; SEC-131, SEC-132). Ansvarlig varsling: [security@neuroforge.bio]. |
| S9 | Sikkerhetstesting | Automatisert sikkerhetstesting ved hver kodeendring (planlagt; SEC-111). Uavhengig inntrengningstest før første behandling av Kundedata i produksjon og deretter årlig: **veikart (krever eierbudsjett)**; sammendrag under NDA (SEC-110). |
| S10 | Sikkerhetskopi og gjenoppretting | PITR for metadata (≥ 14 dager); kopier i egen konto/region; kvartalsvise øvelser; RPO ≤ 15 min (metadata) og RTO ≤ 8 t er **mål, ikke forpliktelser**; gjenoppretting gjeninnfører aldri slettede personer (planlagt; SEC-120, SEC-122, SEC-124). |
| S11 | Miljøer | Ekte Kundedata bare i produksjon; utvikling og test bruker syntetiske eller offentlige data (utformet; SEC-071). |
| S12 | Programvareforsyningskjede | Signerte utgivelser (Sigstore), SLSA-proveniens og CycloneDX SBOM per versjon; oppgitt støtteperiode per SDK-versjon på minst [5] år (CRA-standard – planlagt; SEC-081–083, SEC-134); SBOM + VEX tilgjengelig for Kunden for hver versjon den bruker. |
| S13 | Drift | AWS [USA-region] ved lansering; EU-region planlagt (D4). PHI bare på BAA-dekkede tjenester når BAA finnes (planlagt). |
| S14 | Sikkerhetsmessig bruksforbud | Tjenesten, SDK-er og modeller skal ikke brukes til å styre stimulering, nevromodulering eller aktuatorer, eller i sanntids sikkerhetskritiske sløyfer; kvitteringer fra Tjenesten har ingen tidsgaranti (SEC-090–094). |
| S15 | Slettingens omfang | Gjelder data NeuroForge har; tidligere eksport kan ikke kalles tilbake (listes på slettesertifikatet); trente modeller merkes og trenes på nytt eller blokkeres; «unlearning» er ikke sertifisert. |
| S16 | Sertifiseringer | NeuroForge har **ingen** sikkerhetssertifisering eller tredjepartsattestasjon ved ikrafttredelse. SOC 2 Type II og ISO/IEC 27001 er på veikartet. |

## Hjemmel / Legal basis
Se msa.en.md (samme kildeliste): avtaleloven § 36 (https://lovdata.no/dokument/NL/lov/1918-05-31-4/KAPITTEL_3, åpnet 2026-09-26); personopplysningsloven (https://lovdata.no/dokument/NL/lov/2018-06-15-38, åpnet 2026-09-26); eksportkontrolloven (https://lovdata.no/dokument/NL/lov/1987-12-18-93, åpnet 2026-09-26); dataforordningen (EU) 2023/2854 (https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R2854, åpnet 2026-09-26, bare sammendrag – ordlyd **UVERIFISERT**); Colorado HB24-1058 (https://leg.colorado.gov/bills/hb24-1058, åpnet 2026-09-26). **UVERIFISERT**: GDPR-ordlyd (EUR-Lex lastet ikke), KI-forordningen art. 5, MDR art. 2 nr. 1, forordning 2021/821, forsinkelsesrenteloven, merverdiavgiftsloven, tvisteloven, New York-konvensjonen, CA/CT/MT-lover.
