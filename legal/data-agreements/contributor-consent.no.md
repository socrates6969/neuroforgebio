> UTKAST – ikke juridisk rådgivning. Må gjennomgås av norsk advokat før bruk.

# Samtykkeskjema for bidragsytere av data

Versjon [0.2] · [DATO] · Hash for samtykkedokumentet: [lagres i samtykkeregisteret] · Språk: [norsk går foran for norske deltakere – valg for advokat]

**Etikkgodkjenning:** [REK-ref. ●] / [IRB-ref. ●]. *Skjemaet skal ikke brukes før godkjenningen finnes og nummeret er fylt inn.*

**To ulike virksomheter kan bruke dataene dine. Hver av dem har ansvaret («behandlingsansvarlig») bare for sin egen del:**
- **Studiearrangøren:** [Kunde / studiearrangør], org.nr. [●], [adresse], kontakt [●]. Har ansvaret for boks (i).
- **NeuroForge Bio:** [NeuroForge Bio AS] (FORUTSETNING: norsk AS, ikke stiftet ennå), org.nr. [●], [adresse], kontakt [privacy@neuroforge.bio], [telefon]. Har ansvaret for boks (ii)–(viii).

[Personvernombud: [navn, e-post] / ikke utnevnt – advokat bekrefter]

> **Merknad til den som bruker skjemaet (slettes før bruk):**
> - Boks (ii)–(viii) gir NeuroForge en **ny og selvstendig rolle som behandlingsansvarlig**. De kan bare tilbys når alt dette er på plass:
>   - a) studiearrangøren har signert **tillegget om forskningsdatabasen** (Research Pool Addendum, det skriftlige samtykket etter MSA § 4.3);
>   - b) NeuroForge har gjort en vurdering av personvernkonsekvenser (DPIA) for databasen (RISK-MEMO § 9);
>   - c) REK/IRB har godkjent databasen, der det er helseforskning.
> - Ellers slettes boks (ii)–(viii), og skjemaet gjelder bare studien.
> - Hver boks lagres som et eget omfang i samtykkeregisteret og kan trekkes tilbake for seg. Omfangs-ID-ene står i CONSENT-SCOPES.no.md: (i) `study.*`, (ii) `nf.pool` + `nf.internal_rnd`, (iii) `nf.model_training.internal`, (iv) `nf.research.future_neuro`, (v) `nf.share.research_partner`, (vi) `nf.model_training.licensed`, (vii) `nf.data_licence.commercial`, (viii) `nf.recontact`. Kundens side av avtalen står i legal\commercial\research-pool-addendum.no.md.
> - **Bare voksne (18+).** Etter helseforskningsloven § 17 kan 16–18-åringer i noen tilfeller samtykke selv. Vi utelukker likevel alle under 18, med mindre REK/IRB har godkjent en egen prosess.
> - Mål: skal kunne leses av en elev på ungdomsskolen.
> - Grensene for bredt samtykke står i BROAD-CONSENT-ASSESSMENT.md.

---

## Del 1 – Kort fortalt (les dette først)

- Vi ber om å få **måle signaler fra nervesystemet ditt**, for eksempel hjernebølger (EEG) eller muskelsignaler (EMG), til [studiearrangørens] studie.
- **Det er frivillig å være med.** Du kan si nei, eller slutte senere, uten å si hvorfor. Det påvirker ikke [behandlingen / jobben / studiene dine].
- Navnet ditt og andre opplysninger som viser hvem du er, fjernes. **Men signaler fra hjernen og nervene kan være like personlige som et fingeravtrykk.** Vi kan ikke love at ingen noen gang kan finne ut at dataene er dine.
- **Du bestemmer hver bruk for seg i del 3.** Alle bokser er tomme fra start. Lar du en boks stå tom, blir dataene ikke brukt til det boksen gjelder.
- Du kan **trekke tilbake hver boks når som helst**, én eller alle. Da slettes dataene som ble brukt til det formålet. Kopier som allerede er delt, og resultater som allerede er publisert, **kan ikke** hentes tilbake (del 2, punkt 7).
- **Ingen selger dataene dine til vanlige forbrukere, annonsører eller datameglere.**

## Del 2 – Mer informasjon

### 1. Hva som samles inn
- **Signaler:** [EEG / EMG / annet], ca. [●] minutter per økt, [●] økter.
- **Om målingen:** dato, utstyr, innstillinger og oppgavene du gjorde.
- **Om deg:** aldersgruppe, [kjønn], [høyre-/venstrehendt], [helseopplysninger du selv gir – bare hvis studien trenger dem].
- **Kontaktopplysninger** (navn, e-post/telefon): lagres **atskilt** fra signalene og brukes bare til å nå deg.
- **Valgene dine:** hvilke bokser du krysset av, dato og skjemaversjon. De lagres i et samtykkeregister som ikke kan endres i det skjulte.

### 2. Hva hver boks betyr

| Boks | Hvem har ansvaret | Hva boksen tillater | Hva den IKKE tillater |
|---|---|---|---|
| **(i) Studien** | Studiearrangøren | Måling og bruk av dataene dine i [studiens tittel og spørsmål, 1–2 enkle setninger]. NeuroForge lagrer og behandler dataene bare for arrangøren, som leverandør. | At NeuroForge bruker dataene til egne formål |
| **(ii) NeuroForges forskningsdatabase** | NeuroForge | En **kopi** av de avidentifiserte dataene dine legges i NeuroForges forskningssamling. Den brukes til å studere hjerne- og nervesignaler og til å teste og forbedre NeuroForges analyseprogramvare. | Deling med noen utenfor NeuroForge (det krever (v), (vi) eller (vii)) |
| **(iii) Trening av NeuroForges KI-modeller (internt)** | NeuroForge | Bruk av dataene i databasen til å trene datamodeller (KI) som NeuroForge bruker selv | Lisensiering av modellene til andre selskaper (det krever (vi)) |
| **(iv) Fremtidig hjerneforskning i NeuroForge** | NeuroForge | Fremtidig forskning i NeuroForge på **hvordan nervesystemet virker og på nevrologiske tilstander**. Hvert nytt prosjekt må først godkjennes av en etikkomité der loven krever det. Du får informasjon om nye prosjekter på [nettside / e-post], og du kan når som helst si nei til et område. | Forskning utenfor dette området, for eksempel genetikk, legemidler eller annet som ikke gjelder nervesystemet. Da spør vi deg på nytt. |
| **(v) Deling med godkjente forskningspartnere** | NeuroForge | Deling av avidentifiserte data med universiteter og sykehus som signerer en avtale. Avtalen forbyr dem å prøve å finne ut hvem du er, og å dele dataene videre. | Selskaper som betaler (det krever (vi) eller (vii)) |
| **(vi) KI-modeller lisensiert til selskaper** | NeuroForge | Trening av KI-modeller på dataene i databasen og **lisensiering av modellene** til selskaper som betaler. Selskapene får modellen, ikke dataene dine. | Reklame, datameglere, forsikring, jobb, kreditt, eller å lese følelser på jobb eller skole. Dette er aldri tillatt. |
| **(vii) Data lisensiert til selskaper** | NeuroForge | Deling av avidentifiserte **data** med **selskaper som betaler lisens** for å bruke dem til forskning eller produktutvikling | Samme bruk som i (vi) er aldri tillatt |
| **(viii) Kontakt om nye studier** | NeuroForge | Vi kan spørre deg om nye studier. Du kan si nei hver gang. | – |

**Hvordan boksene henger sammen:**
- Boks **(iii)–(vii)** virker bare hvis du også krysser av for **(ii)**, fordi de bruker kopien i databasen.
- Trekker du tilbake (ii), stanser all bruk i NeuroForge. Unntaket er (viii), hvis du beholder den.

### 3. Rettslig grunnlag
Ditt **uttrykkelige samtykke**, gitt for hver boks for seg (personvernforordningen art. 6 nr. 1 bokstav a og art. 9 nr. 2 bokstav a). Ved helseforskning gjelder også helseforskningsloven, og en etikkomité ([REK]) må godkjenne prosjektet.

### 4. Hvem får dataene
| Mottaker | Når |
|---|---|
| Studiearrangørens navngitte team | Boks (i) |
| NeuroForges IT-leverandører (f.eks. skylagring [AWS, USA ved oppstart; EU-region planlagt]) | Alltid. De arbeider for oss etter avtale og kan ikke bruke dataene selv |
| NeuroForges forskere | Boks (ii)–(iv) |
| Forskere ved universiteter og sykehus [navngitte eller godkjente] | Boks (v) |
| Selskaper som betaler lisens | Bare boks (vi) og (vii) |
| Myndigheter | Bare når loven krever det |

Alle som får dataene, signerer en avtale. Avtalen forbyr dem å prøve å finne ut hvem du er, å selge dataene videre og å bruke dem til reklame, til beslutninger om jobb, forsikring eller kreditt, eller til å lese følelser på jobb eller skole.

**Data utenfor Norge / EU/EØS:** [Ved oppstart lagres dataene i USA (Amazon Web Services).] Dataene overføres bare med et lovlig grunnlag, for eksempel EUs standard personvernbestemmelser. Du kan be om kopi.

### 5. Slik beskyttes dataene
- Navnet ditt byttes ut med en kode, og kodenøkkelen lagres atskilt fra dataene.
- Dataene er kryptert, bare navngitte personer har tilgang, og all tilgang logges.
- **Ærlig begrensning:** risikoen blir mindre når navnet fjernes, men den blir ikke borte. Hjernesignaler kan noen ganger kobles til en person. Risikoen vurderes før deling, og det er forbudt i avtale å prøve å identifisere deg.

### 6. Hvor lenge dataene lagres
- **Boks (i):** til [studieslutt + ● år], slik arrangøren bestemmer.
- **Boks (ii)–(vii):** til du trekker samtykket tilbake, og høyst [●] år etter siste økt (se RETENTION-POLICY).
- Deretter slettes dataene, eller de gjøres helt anonyme hvis det er mulig og godkjent.

### 7. Å trekke tilbake samtykket – hva som kan og ikke kan gjøres
Du kan trekke tilbake hvilken som helst boks når som helst: send e-post til [privacy@neuroforge.bio], ring [telefon] eller bruk [lenke]. Det er like enkelt som å si ja. Vil du trekke deg fra selve studien (boks (i)), kontakter du [arrangøren]; vi sender beskjeden videre.

**Dette blir gjort:**
- dataene som ble brukt til formålet, slettes. Sikkerhetskopier blir uleselige fordi krypteringsnøkkelen for dataene dine ødelegges;
- alle som har fått dataene til formålet, får beskjed om å slette dem innen [30] dager og bekrefte det;
- datamodeller som er trent med dataene dine, **trenes på nytt uten dem** eller tas ut av bruk;
- du får bekreftelse hvis du ber om det.

**Dette kan ikke gjøres:**
- resultater som allerede er **publisert**, trekkes ikke tilbake (de viser bare resultater for grupper, aldri navnet ditt);
- kopier andre har laget **før** du trakk deg, kan vi ikke slette selv hvis de ikke gjør det. Sletting er et krav i avtalen, men vi har ikke tilgang til systemene deres;
- en KI-modell kan ikke få til å «glemme» deg nøyaktig. Det finnes **ingen bevist metode** for det. Modellene trenes i stedet på nytt uten dataene dine.

Det som ble gjort før du trakk deg, er fortsatt lovlig.

### 8. Rettighetene dine
Du kan be om å få se dataene dine, rette dem, slette dem, begrense bruken av dem eller få en kopi du kan ta med deg. Du kan også protestere mot bruken. For boks (i) kontakter du arrangøren, for boks (ii)–(viii) kontakter du NeuroForge. Du får svar innen én måned.

**Klage:** du kan klage til **Datatilsynet** (www.datatilsynet.no) eller til tilsynsmyndigheten der du bor.

### 9. Betaling
[Du får [beløp/gavekort] for tiden din. / Det gis ingen betaling.] **Du får samme betaling uansett hva du velger i boks (ii)–(viii)**, og du beholder den hvis du trekker deg senere. Ingen boks gir ekstra betaling.

### 10. Risiko og nytte
Målingen er [ikke-invasiv; beskriv eventuelt ubehag]. Den største risikoen for deg er personvernrisikoen beskrevet over. Du har ingen direkte nytte av å være med. Du får ingen medisinske resultater og ingen diagnose.

### 11. Personer bosatt i USA
I noen amerikanske delstater (f.eks. Connecticut, California og Colorado) er nevrale data «sensitive data». Deling med selskaper mot betaling kan regnes som «sale» (salg). **Boks (vi) og (vii) er samtykket ditt til det.** Du kan trekke det tilbake når som helst, og vi stopper innen [15] dager. [Amerikansk advokat bekrefter ordlyden. **UVERIFISERT** for Colorado og Montana.]

## Del 3 – Valgene dine (hver boks gjelder for seg, alle er tomme fra start, og hver kan trekkes tilbake for seg)

For å være med i studien må du krysse av for **(i)**. Resten er frivillig.

☐ **(i) Studien.** Jeg samtykker til at [studiearrangøren] kan måle, lagre og bruke dataene mine i studien beskrevet over.

☐ **(ii) NeuroForges forskningsdatabase.** Jeg samtykker til at NeuroForge Bio kan oppbevare en avidentifisert kopi av dataene mine i sin forskningsdatabase, for å studere hjerne- og nervesignaler og for å teste og forbedre analyseprogramvaren sin.

☐ **(iii) Trening av NeuroForges KI-modeller.** Jeg samtykker til at NeuroForge Bio kan bruke avidentifiserte data om meg til å trene KI-modeller som selskapet bruker selv. Jeg forstår at modellene trenes på nytt uten dataene mine hvis jeg trekker meg, men at de ikke kan få til å «glemme» meg nøyaktig.

☐ **(iv) Fremtidig hjerneforskning i NeuroForge.** Jeg samtykker til at NeuroForge Bio kan bruke avidentifiserte data om meg i fremtidig forskning på hvordan nervesystemet virker og på nevrologiske tilstander, med etikkgodkjenning der det kreves. Jeg får informasjon om nye prosjekter og kan si nei når som helst.

☐ **(v) Forskningspartnere.** Jeg samtykker til at NeuroForge Bio kan dele avidentifiserte data om meg med godkjente universiteter og sykehus til forskning. Det skjer etter en avtale som forbyr dem å identifisere meg og å dele dataene videre.

☐ **(vi) KI-modeller lisensiert til selskaper.** Jeg samtykker til at NeuroForge Bio kan bruke avidentifiserte data om meg til å trene KI-modeller som **lisensieres til selskaper** mot betaling. Lisensen forbyr å prøve å identifisere meg og bruken som er nevnt i punkt 4. Trekker jeg meg, trenes nye versjoner av modellene uten dataene mine.

☐ **(vii) Data lisensiert til selskaper.** Jeg samtykker til at NeuroForge Bio kan dele avidentifiserte **data** om meg med selskaper som betaler lisens for å bruke dem til forskning eller produktutvikling. Avtalen forbyr å identifisere meg, videresalg og bruken som er nevnt i punkt 4. *(Etter noen amerikanske lover er dette «salg».)*

☐ **(viii) Kontakt.** Jeg samtykker til at NeuroForge Bio kan kontakte meg om nye studier.

Jeg har lest del 1 og del 2 (eller fått dem lest opp), har kunnet stille spørsmål og er 18 år eller eldre.

Navn: ______________ Signatur / e-signatur: ______________ Dato: ________
Den som har forklart studien: ______________ Signatur: ______________

*Du får en kopi av det signerte skjemaet.*

## Hjemmel / Legal basis
- **Personvernforordningen, offisiell engelsk tekst** fra Publikasjonskontoret: http://publications.europa.eu/resource/celex/32016R0679 (åpnet 2026-09-26).
  - Fortalepunkt 26: pseudonymiserte data regnes som opplysninger om en identifiserbar person.
  - Fortalepunkt 33: bredt samtykke til visse forskningsområder.
  - Fortalepunkt 42: den registrerte skal kjenne den behandlingsansvarliges identitet, og det skal ikke få negative følger å si nei eller trekke seg.
  - Art. 5 nr. 1 bokstav b og e, og art. 12 nr. 3.
- **Personvernforordningen, norsk tekst på Lovdata** (åpnet 2026-09-26):
  - art. 4: https://lovdata.no/lov/2018-06-15-38/gdpr/a4
  - art. 7: https://lovdata.no/lov/2018-06-15-38/gdpr/a7
  - art. 9: https://lovdata.no/lov/2018-06-15-38/gdpr/a9
  - art. 17: https://lovdata.no/lov/2018-06-15-38/gdpr/a17
  - art. 19: https://lovdata.no/lov/2018-06-15-38/gdpr/a19
  - art. 46: https://lovdata.no/lov/2018-06-15-38/gdpr/a46
- **Personopplysningsloven § 10:** https://lovdata.no/lov/2018-06-15-38/§10 (åpnet 2026-09-26).
- **Helseforskningsloven** §§ 9, 13, 14, 16 og 17: https://lovdata.no/lov/2008-06-20-44/§14 og https://lovdata.no/dokument/NL/lov/2008-06-20-44 (åpnet 2026-09-26).
- **Amerikanske delstatslover:**
  - Connecticut PA 25-113: https://www.cga.ct.gov/2025/ACT/PA/PDF/2025PA-00113-R00SB-01295-PA.PDF (åpnet 2026-09-26).
  - California SB 1223: https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202320240SB1223 (åpnet 2026-09-26).
  - Colorado HB24-1058: https://leg.colorado.gov/bills/hb24-1058 (åpnet 2026-09-26). Ordlyden om samtykke er **UVERIFISERT**.
  - Montana SB 163: **UVERIFISERT**.
- **EEG som biometri:** doi:10.1155/2021/5229576; doi:10.1155/ijta/3946740 (åpnet 2026-09-26).
- **Produktfakta:** BLUEPRINT.md §8.3–8.4; MSA § 4.3; DECISIONS.md D4.
