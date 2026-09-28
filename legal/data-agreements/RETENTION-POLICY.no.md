> UTKAST – ikke juridisk rådgivning. Må gjennomgås av norsk advokat før bruk.

# Retningslinjer for lagring og sletting av data

Versjon [0.1] · 2026-09-26 · Eier: Marius Carlsson · [NeuroForge Bio AS] (FORUTSETNING: norsk AS, **ikke stiftet ennå**)
Språk: den norske versjonen går foran ved motstrid [valg for advokat] · Engelsk versjon: RETENTION-POLICY.en.md
Status: retningslinjene gjelder **utformede/planlagte systemer**. Ingenting her er i drift.

## 1. Prinsipper
1. **Lagringsbegrensning.** Personopplysninger skal ikke oppbevares i identifiserbar form lenger enn nødvendig. Lengre lagring er bare tillatt når opplysningene **utelukkende** brukes til vitenskapelig forskning, og da med garantier etter art. 89 nr. 1 (art. 5 nr. 1 bokstav e).
2. **To roller, to sett regler.**
   - **Kundedata:** NeuroForge er **databehandler**. Kunden bestemmer lagringstiden. Vi sletter etter instruks og når avtalen opphører (DPA § 11; MSA § 15.2).
   - **Data i forskningsdatabasen** (boks (ii)–(viii)): NeuroForge er **behandlingsansvarlig**, og disse retningslinjene gjelder.
3. **Pseudonymiserte data er personopplysninger** (fortalepunkt 26). Data går bare ut av disse reglene hvis de består en dokumentert anonymiseringstest (punkt 4).
4. **Ærlig sletting.**
   - Krypto-sletting: vi ødelegger krypteringsnøkkelen, slik at kopier blir uleselige.
   - Modeller trenes på nytt uten dataene. De «avlæres» ikke.
   - Data som allerede er eksportert ut av plattformen, kan vi ikke hente tilbake selv. Vi følger dem opp med krav i avtalen (BLUEPRINT §8.4).

## 2. Lagringstider

| # | Kategori | Rolle | Lagringstid | Ved utløp | Grunnlag / merknad |
|---|---|---|---|---|---|
| 1 | **Rå nevrale signaler i kundens tenant** | Databehandler | Som kunden stiller inn. Ved avtaleslutt: [30] dager til å hente ut data, sletting i produksjon innen [30] nye dager, og sikkerhetskopier gjort uleselige ved sletting av nøkler og utløpt innen [35] dager (ESTIMAT) | Sletting og krypto-sletting; bekreftelse på forespørsel | DPA § 11; MSA § 15.2 |
| 2 | **Rå nevrale signaler i NeuroForges forskningsdatabase** (boks ii) | Behandlingsansvarlig | Til deltakeren trekker tilbake (ii), og høyst **[10] år etter siste økt** [eier/REK fastsetter]. Behovet vurderes på nytt hvert [2]. år | Sletting og ødeleggelse av deltakernøkkelen | Art. 5 nr. 1 bokstav e. Bare så lenge et forskningsomfang ((ii) eller (iv)) gjelder |
| 3 | **Avledede kjennetegn, embeddings og annoteringer** | Som kilden | **Aldri lenger enn kilden** (arveregel, BLUEPRINT §8.2) | Slettes i samme slettejobb som kilden | Kjennetegn som kan kobles til en person, er personopplysninger |
| 4 | **Aggregater med flere deltakere** | Som kilden | Så lenge kilden lagres. Trekker en deltaker seg: aggregatet merkes utdatert og **kjøres på nytt uten deltakeren**, eller markeres som slettet | Ny kjøring eller merking som slettet | BLUEPRINT §8.4 |
| 5 | **Anonymiserte data** (bestått test, punkt 4) | Utenfor GDPR | Ingen grense | Testrapporten lagres sammen med dataene | Fortalepunkt 26. Nevrale data kan sjelden anonymiseres |
| 6 | **Poster i samtykkeregisteret** | Behandlingsansvarlig / databehandler | Så lenge data behandles på grunnlag av samtykket, **pluss [5] år** [advokat vurderer foreldelse; **UVERIFISERT**]. Etter tilbaketrekking beholdes bare en minimal post: pseudonym, omfang, tidspunkt og hash av slettebeviset | Sletting, eller reduksjon til minimalt bevis | Art. 7 nr. 1 (plikt til å kunne påvise samtykke); art. 17 nr. 3 bokstav e (rettskrav) |
| 7 | **Revisjonslogger** (WORM, hash-kjedet) | Behandlingsansvarlig for egne logger | **[3] år** som standard; **[minst 6] år** for kunder med BAA (MSA bilag 2 S6) [HIPAA **UVERIFISERT**] | Utløp etter objektlås-regler | Sikkerhet (art. 32). **Ingen signaldata eller direkte identifikatorer** |
| 8 | **Applikasjons- og driftslogger** | Behandlingsansvarlig | [90] dager (ESTIMAT) | Sletting | Bare godkjente felter logges; ingen signaldata |
| 9 | **Sikkerhetskopier** | Som kilden | Rotasjon på høyst [35] dager (ESTIMAT). Når en deltakers nøkkel er ødelagt, er dataene i kopiene **uleselige med en gang** og kan ikke gjenopprettes | Krypto-sletting og naturlig utløp | BLUEPRINT §8.4; DPA § 11.1 |
| 10 | **Trente modeller** (punkt 5) | Behandlingsansvarlig (databasen) / kunden (tenant) | Så lenge modellen er i bruk og alle deltakerne som den er trent på, fortsatt har gitt samtykke ((iii) eller (vi)) | `retrain_required` → ny trening → gammel versjon tas ut innen [90] dager | Ingen sertifisert «avlæring» |
| 11 | **Kopier hos lisenstakere og partnere** | Mottakerne (selvstendig ansvarlige) | Slettes **innen [30] dager** etter varsel om tilbaketrekking, og ved avtaleslutt | Slettebevis til NeuroForge | Art. 19; datalisens § 6; akademisk delingsavtale § 5 |
| 12 | **Kontaktopplysninger** (boks viii) | Behandlingsansvarlig | Til samtykket trekkes tilbake, eller [5] år uten kontakt | Sletting | Samtykke |
| 13 | **Avtaler og regnskapsmateriale** | Behandlingsansvarlig | **Bokføringsloven § 13:** årsregnskap, spesifikasjoner, dokumentasjon av bokførte opplysninger og revisors brev til styret: **5 år etter regnskapsårets slutt**. Avtaler, korrespondanse med vesentlige tilleggsopplysninger, pakksedler og prislister: **3 år og 6 måneder** | Sletting | Loven sier «oppbevares i Norge». Når oppbevaring i utlandet er tillatt (bokføringsforskriften), er **UVERIFISERT**. Lagring i AWS USA er i konflikt med kravet hvis ingen unntak gjelder |
| 14 | **Data fra nettstedet** | Behandlingsansvarlig | Etter personvernerklæringen: forespørselslogger [30] dager; listen for tidlig tilgang til avmelding eller [24] måneder | Sletting | legal\website\privacy-policy.* |

## 3. Pseudonymisert eller anonymisert
- **Pseudonymisert:** direkte identifikatorer er fjernet, og kodenøkkelen oppbevares for seg (art. 4 nr. 5). Dataene er **fortsatt personopplysninger**, og hele GDPR gjelder.
- **Anonymisert:** personen kan ikke identifiseres, vurdert ut fra alle midler som med rimelig sannsynlighet kan tas i bruk, for eksempel utskilling («singling out») (fortalepunkt 26).
- **Å slette pseudonymnøkkelen gjør ikke dataene anonyme.** Nevrale signaler kan i seg selv identifisere en person (EEG brukes som biometri). Å ødelegge **krypteringsnøkkelen** er noe annet: da blir dataene uleselige, og det virker i praksis som sletting.

## 4. Anonymiseringstest
Før data flyttes til kategori 5, må det gjøres en dokumentert vurdering etter fortalepunkt 26. Vurderingen skal inneholde:
- a) test av utskilling og kobling, inkludert en biometrisk EEG-matcher mot andre opptak av de samme personene;
- b) for syntetiske data: test av om enkeltpersoner kan påvises i treningsdataene (membership inference) og test av nærmeste post;
- c) test av om egenskaper ved personer kan utledes.

Tersklene fastsettes i DPIA-en. Er det tvil, forblir dataene pseudonymiserte.

## 5. KI-modeller når samtykket trekkes tilbake
1. Provenansgrafen registrerer hvilke deltakerpseudonymer som inngikk i hvilken modellversjon.
2. Tilbaketrekking av (ii), (iii) eller (vi) merker alle berørte versjoner `retrain_required`, og modelleierne varsles.
3. **Utrulling stanses.** Nye utrullinger av merkede versjoner sperres. Sperren er standard for forskningsdatabasen. Eksisterende utrullinger kan brukes til den nye versjonen er klar, men høyst i [90] dager.
4. **Ny trening uten deltakeren.** Med **SISA** (trening i delmengder, «shards») trenes bare den berørte delen på nytt. Det er ikke sertifisert «avlæring».
5. Gamle versjoner slettes innen [90] dager etter at en ny versjon er tatt i bruk.
6. **Vi lover ikke sertifisert «avlæring».** Løftet er: «trent på nytt uten deltakeren; her er provenansbeviset og slettebeviset».
7. **Modeller som allerede er lisensiert ut:** lisenstaker får varsel og ny versjon, og må slutte å bruke den gamle innen [90] dager. Kopier kan ikke hentes tilbake teknisk.

## 6. Ansvar og gjennomgang
- Dataforvalteren [rolle] kjører slettejobbene, signerer slettebevis og går gjennom retningslinjene **hvert år**.
- Advokat godkjenner tallene i hakeparentes.
- **Rettslig pålegg om bevaring** (tvist eller pålegg fra myndighet): slettingen utsettes bare for de berørte dataene. Utsettelsen logges og vurderes på nytt hver [3]. måned.

## Hjemmel / Legal basis
- **Personvernforordningen, offisiell engelsk tekst** fra Publikasjonskontoret: http://publications.europa.eu/resource/celex/32016R0679 (åpnet 2026-09-26). Brukt for fortalepunkt 26, art. 5 nr. 1 bokstav e, art. 7 nr. 1, art. 17 nr. 3 bokstav e og art. 89 nr. 1.
- **Personvernforordningen, norsk tekst på Lovdata** (åpnet 2026-09-26):
  - art. 4: https://lovdata.no/lov/2018-06-15-38/gdpr/a4
  - art. 17: https://lovdata.no/lov/2018-06-15-38/gdpr/a17
  - art. 19: https://lovdata.no/lov/2018-06-15-38/gdpr/a19
- **Bokføringsloven § 13:** https://lovdata.no/lov/2004-11-19-73/§13 (åpnet 2026-09-26). Bokføringsforskriften om oppbevaring i utlandet er **UVERIFISERT**.
- **Ikke åpnet, UVERIFISERT:** foreldelsesloven og HIPAAs krav til hvor lenge dokumentasjon skal oppbevares.
- **Produktfakta:** BLUEPRINT.md §8.1, §8.2 og §8.4; DPA § 11; MSA § 15.2 og bilag 2 S6.
- **SISA:** arXiv:1912.03817.
