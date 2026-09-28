> UTKAST – ikke juridisk rådgivning. Må gjennomgås av norsk advokat før bruk.

# Tillegg A til databehandleravtalen: analyse der dataene ligger (A1) og endepunktsanalyse for CRO/legemiddelindustri (A12)

Versjon [0.1] · [DATO] · Tillegg til databehandleravtalen (legal\commercial\dpa.no.md, «DPA») og MSA.
Språk: engelsk versjon går foran ved motstrid [valg for advokat].

**Parter:**
- **Kunden (behandlingsansvarlig):** den som har dataene (A1), eller sponsor/CRO (A12).
- **Databehandler:** [NeuroForge Bio AS] (FORUTSETNING: norsk AS, **ikke stiftet ennå**).
- Er Kunden selv databehandler, er NeuroForge underdatabehandler.

**Rangordning:** standard personvernbestemmelser (der de brukes) > dette tillegget > DPA > MSA, for tjenestene under.

## 1. Tjenester
- **(A1) Analyse der dataene ligger («compute-to-data»).** Kundens personopplysninger blir værende i Kundens tenant eller VPC. Analytikere som Kunden har godkjent, sender inn versjonerte analyseløp (pipelines). Løpene kjøres der dataene ligger. Bare resultater som oppfyller reglene for utlevering av resultater (vedlegg A1), forlater tenanten.
- **(A12) Endepunktsanalyse for CRO/legemiddelindustri.** EEG- og nevrale endepunktsløp, robusthetsrevisjoner og sentral avlesning på sponsor- eller studiedata, utført **for Kunden**.

## 2. Bare databehandler
2.1 NeuroForge er **bare databehandler** og følger Kundens dokumenterte instrukser (DPA § 3). Instruksene for disse tjenestene er: dette tillegget, listen over godkjente analyseløp og reglene for utlevering av resultater (vedlegg A1).
2.2 **Ingen egne formål.** DPA § 3.4 og MSA § 4.3 gjelder fullt ut. NeuroForge skal ikke:
- bruke dataene eller resultatene til egne formål, egne sammenligningstester (benchmarks), forskningsdatabasen eller modelltrening;
- selge, lisensiere eller kombinere dem;
- beholde dem etter at tjenesten er avsluttet.
Ingen `nf.*`-samtykker (CONSENT-SCOPES) brukes noen gang på data under dette tillegget.
2.3 **Analytikere er ikke NeuroForges underdatabehandlere.** De er mottakere som Kunden velger. Kunden avgjør om en utlevering er lovlig: om mottakeren har eget grunnlag og unntak etter art. 9 nr. 2, om den registrerte har gitt samtykke til deling, og om amerikanske regler om «sale» gjelder. NeuroForge gjennomfører Kundens beslutninger teknisk.

## 3. Sikkerhetstiltak for analyse der dataene ligger (A1)
3.1 **Godkjenning av analyseløp.** Bare analyseløp som Kunden har godkjent, kan kjøres.
- Løpene er versjonert og har hash.
- Tiltak mot at data lekker ut [utformet]: utgående nettverk er sperret, og det kan bare skrives filer til resultatområdet.
- Et løp som endres, må godkjennes på nytt.
3.2 **Regler for utlevering av resultater** (vedlegg A1). Standardinnstillinger:
- bare aggregater;
- minst [10] personer per celle;
- ingen verdier på individnivå, ingen pseudonymer og ingen rå tidsserier;
- modellvekter bare når Kunden har godkjent det;
- eventuelt støy etter differensielt personvern (DP) med et oppgitt budsjett.
3.3 **Vilkår for analytikere** (vedlegg A2). Analytikerne skal være bundet av:
- forbud mot reidentifisering og kobling;
- bruk bare i den angitte studien;
- forbudene i KI-forordningen art. 5, blant annet følelsesgjenkjenning på arbeidsplass og i utdanning, unntatt av medisinske eller sikkerhetsmessige grunner;
- forbud mot kliniske beslutninger;
- forbud mot videresalg.
3.4 **Logging.** Hver kjøring, godkjenning og utlevering logges i revisjonsloggen (MSA bilag 2 S6).
3.5 **Anonyme resultater.** Resultater som er anonyme etter fortalepunkt 26, faller utenfor GDPR. **Kunden vurderer dette** som behandlingsansvarlig. NeuroForge gir tallgrunnlaget for vurderingen, men garanterer ikke at resultatene er anonyme.

## 4. Sikkerhetstiltak for CRO/legemiddelindustri (A12)
4.1 **Godkjenninger er Kundens ansvar.** Kunden garanterer at studien har de godkjenningene og samtykkene som dekker NeuroForges behandling: REK etter helseforskningsloven § 9 ved norsk helseforskning, og IRB eller myndighet ellers. Regler for kliniske studier (CTR / nasjonal rett) er **UVERIFISERT** i dette utkastet.
4.2 **Ingen PHI før BAA.** Kunden skal ikke laste opp helseopplysninger som er beskyttet etter HIPAA (PHI), før partene har signert en BAA. NeuroForges **BAA er PLANLAGT, ikke tilgjengelig**. Frem til da skal data fra virksomheter som omfattes av HIPAA, avidentifiseres av Kunden før opplasting. Kunden er ansvarlig for metoden (45 CFR 164.514: **UVERIFISERT**).
4.3 **Ingen kliniske påstander.** Resultatene er forsknings- og studieanalyser. De er ikke diagnose eller behandling av enkeltpersoner (MSA § 10.1; AUP § 5).
4.4 **Part 11 / GCP.** Kontrollene er [utformet/planlagt], og det hevdes ikke at de oppfyller kravene. Kunden validerer systemet for sin egen bruk.
4.5 **Atskillelse.** Blindede og ublindede data holdes i atskilte arbeidsområder, og det samme gjelder data fra ulike sponsorer.

## 5. Sikkerhet, avvik, overføring og sletting
5.1 **Sikkerhet:** DPA vedlegg II / MSA bilag 2 (S1–S16) gjelder. Tiltakene er utformet eller planlagt, og ingen sertifisering hevdes. Art. 32 nr. 1 bokstav a nevner «pseudonymisering og kryptering av personopplysninger» (verifisert tekst, sitert i security\STANDARDS-MAP.md §5.3).
5.2 **Avvik:** Kunden varsles «uten ugrunnet opphold» (art. 33 nr. 2), med mål om **[24] timer etter at avviket er bekreftet**. Det gir Kunden tid til å overholde fristen på 72 timer (art. 33 nr. 1) (DPA § 8).
5.3 **Overføring:** AWS i USA ved oppstart; EU-region er planlagt (D4). Overføringer følger DPA § 10. Modul [2/3] bekreftes av advokat.
5.4 **Sletting:** DPA § 11 gjelder. Arbeidsmiljøet (containere og midlertidige filer) slettes etter hver kjøring. Resultater som lagres for Kunden, følger Kundens lagringstid.

## 6. Revisjon og ansvar
DPA § 12 og § 14 gjelder, og det samme gjør ansvarstaket for personvern (MSA § 12.3). Brudd på punkt 2.2 (bruk til egne formål) er uten ansvarsgrense [valg for advokat].

---
### Vedlegg A1 – Regler for utlevering av resultater (fylles ut av Kunden)
| Innstilling | Standard | Kundens valg |
|---|---|---|
| Minste antall personer per celle | [10] | [●] |
| Resultater på individnivå | Sperret | [●] |
| Pseudonymer i resultatene | Sperret | [●] |
| Utlevering av modellvekter | Sperret, med mindre det er godkjent per analyseløp | [●] |
| DP-budsjett per analytiker per [periode] | Av / [●] | [●] |
| Hvem godkjenner (roller) | data-steward | [●] |

### Vedlegg A2 – Klausuler Kunden skal ta inn i vilkårene for analytikere
1. Ingen reidentifisering, kobling eller kontakt med de registrerte.
2. Bruk bare i [studien]. Ingen videresalg eller utlevering av resultater på individnivå.
3. Ingen praksis som er forbudt etter KI-forordningen art. 5, og ingen kliniske beslutninger.
4. Varsel om avvik til Kunden innen [24] timer.
5. Sletting av resultatene ved studieslutt, med slettebevis.

## Hjemmel / Legal basis
- **Personvernforordningen, offisiell engelsk tekst** (Publikasjonskontoret, http://publications.europa.eu/resource/celex/32016R0679, åpnet 2026-09-26): fortalepunkt 26 og art. 33 nr. 1.
- **Personvernforordningen art. 28, norsk tekst** (Lovdata, åpnet 2026-09-26): https://lovdata.no/lov/2018-06-15-38/gdpr/a28
- **Personvernforordningen art. 32 nr. 1 bokstav a og art. 33 nr. 2:** tekst sitert av nfb-security i security\STANDARDS-MAP.md §5.3 (kilde https://publications.europa.eu/resource/celex/32016R0679, åpnet 2026-09-26; nfb-security har godkjent gjenbruk).
- **KI-forordningen art. 5 nr. 1 bokstav f** (offisiell tekst, http://publications.europa.eu/resource/celex/32024R1689, åpnet 2026-09-26).
- **Helseforskningsloven § 9:** https://lovdata.no/dokument/NL/lov/2008-06-20-44 (åpnet 2026-09-26).
- **UVERIFISERT:** HIPAA 164.514, CTR, Part 11 og valg av modul i standard personvernbestemmelser.
- **Avtalegrunnlag:** DPA, MSA, BAA (PLANLAGT), BLUEPRINT §8, D4.
