> UTKAST – ikke juridisk rådgivning. Må gjennomgås av norsk advokat før bruk.

# Tilleggsavtale om forskningspool (MSA pkt. 4.3, opt-in) – PLANLAGT

**Status: PLANLAGT.** Forskningspoolen er planlagt åpnet i måned 18–30 (ESTIMAT). Tilleggsavtalen skal ikke tilbys eller signeres før: (a) NeuroForge har gjennomført DPIA for poolen (legal\data-agreements\RISK-MEMO.md pkt. 9); (b) avidentifiseringsmetode og tekniske tiltak er bygget og dokumentert; (c) samtykkeskjemaet (legal\data-agreements\contributor-consent.*) er endelig; (d) advokat har gjennomgått avtalen. Gjeldende språk: engelsk [valg for advokat]. FORUTSETNING: NeuroForge Bio blir et norsk AS, ikke stiftet ennå.

**Parter:** [Kunden] og [NeuroForge Bio AS], under MSA [nr./dato] og bestillingsskjema [nr.]. Dette er det **særskilte, skriftlige samtykket (opt-in)** i MSA pkt. 4.3. Standard: **AV** – ingenting i MSA, bestillingsskjema eller databehandleravtale tillater bidrag til poolen uten at denne avtalen er signert og et datasett er meldt inn etter pkt. 3.

## 1. Definisjoner
- **Forskningspoolen**: NeuroForges planlagte samling av avidentifiserte kopier av nevrale data brukt til Poolformålene.
- **Poolformål**: bare formål som svarer til samtykkeboksene hver registrerte faktisk har krysset av: (ii) forskningspool – studier av nervesignaler og testing/forbedring av NeuroForges analyseprogramvare; (iii) intern KI-trening; (iv) fremtidig forskning på nervesystemet, med etikkgodkjenning per prosjekt; (v) deling med kontrollerte forskningspartnere; (vi) trening av KI-modeller som lisensieres til selskaper (modeller, ikke data); (vii) lisensiering av avidentifiserte data til selskaper etter datalisensavtale (legal\data-agreements\data-licence-agreement.*). Boksnumre etter legal\data-agreements\contributor-consent.no.md; omfangs-ID-er i samtykkeregisteret etter legal\data-agreements\CONSENT-SCOPES.no.md: (ii) `nf.pool` + `nf.internal_rnd`; (iii) `nf.model_training.internal`; (iv) `nf.research.future_neuro`; (v) `nf.share.research_partner`; (vi) `nf.model_training.licensed`; (vii) `nf.data_licence.commercial`; (viii) `nf.recontact` (bare kontakt, ingen pooldata).
- **Bidragsdatasett**: datasett Kunden melder inn etter pkt. 3.
- **Avidentifisert**: direkte identifikatorer fjernet og pseudonymer erstattet med poolnøkler som NeuroForge ikke kan koble tilbake uten Kundens nøkkel. **Nevrale data avidentifisert slik behandles fortsatt som personopplysninger** (risiko for reidentifisering; security\THREAT-MODEL.md P-03). Pooldata kalles aldri «anonyme».

## 2. Roller
2.1 For Tjenesten er NeuroForge fortsatt Kundens databehandler etter databehandleravtalen.
2.2 For **kopien** i poolen blir NeuroForge **selvstendig behandlingsansvarlig** for Poolformålene, basert på de registrertes uttrykkelige samtykke innhentet av Kunden på NeuroForges vegne (GDPR art. 6 nr. 1 bokstav a og art. 9 nr. 2 bokstav a) [advokat: bekreft roller og om felles behandlingsansvar etter art. 26 trengs for innsamlingen – **UVERIFISERT**].
2.3 NeuroForge skal oppgis som behandlingsansvarlig for boks (ii)–(viii) i Kundens samtykkeskjema.

## 3. Innmelding (per datasett)
3.1 Kunden melder inn datasett i konsollen eller i vedlegg 1 (datasett-ID, studie, jurisdiksjoner, referanse til etikkgodkjenning, versjon av samtykkeskjema).
3.2 Bare personer med tilsvarende omfang i samtykkeloggen kopieres. Tjenesten kopierer **bare avidentifiserte data**, og bare for omfangene hver person har valgt.

## 4. Kundens garantier
For hvert bidragsdatasett garanterer Kunden at:
(a) hver registrert har gitt tilsvarende samtykke på gjeldende NeuroForge-godkjente skjema, hver boks for seg, uten forhåndsavkrysning og uten at betaling avhenger av valgene;
(b) samtykket (skjemaversjon, bokser, dato) er registrert i samtykkeloggen;
(c) nødvendig REK-/IRB-/etikkgodkjenning dekker bidrag til poolen;
(d) dataene er lovlig innsamlet og Kunden har rett til å utlevere dem;
(e) Kunden straks registrerer enhver tilbaketrekking i loggen.

## 5. Eierskap og lisens
5.1 **Kunden beholder eiendomsretten** til sine data og Resultater (MSA pkt. 4.1). De registrerte beholder sine rettigheter.
5.2 Kunden gir NeuroForge en ikke-eksklusiv, verdensomspennende, ikke-overdragbar (unntatt til etterfølger etter MSA pkt. 17.2) lisens til å kopiere, lagre og bruke avidentifiserte bidragsdatasett **bare til Poolformål som den enkeltes samtykke tillater**, så lenge samtykket står.
5.3 NeuroForge eier modeller, programvare og forskningsresultater laget av pooldata, med forbehold for pkt. 6 og de registrertes rettigheter. [Forhandlingsbart: kreditering i publikasjoner eller lisens til modellene.]
5.4 **Ikke salg av identifiserbare data.** NeuroForge skal aldri selge, leie ut eller dele data som identifiserer, eller med rimelig sannsynlighet kan identifisere, en person. Lisensiering etter boks (vii) gjelder bare avidentifiserte data, etter avtale som forbyr reidentifisering og videreoverføring. Forbudt bruk etter AUP (reklame, datameglere, forsikring, ansettelse, kreditt, følelsesutledning på arbeid eller skole) er utelukket i alle lisenser.

## 6. Tilbaketrekking
6.1 Kunden kan trekke tilbake et helt datasett, og en registrert kan trekke tilbake enhver boks, **når som helst** uten begrunnelse.
6.2 Tilbaketrekking registreres i samtykkeloggen og gjennomføres som utformet (architecture\BLUEPRINT.md § 8.4):
   - poolkopier slettes og poolnøkler destrueres (kryptografisk sletting);
   - modeller trent på dataene merkes **`retrain_required`** og trenes på nytt uten dem eller blokkeres; **sertifisert «machine unlearning» tilbys ikke**;
   - **kopier allerede delt med partnere eller lisenstakere (boks (v)–(vii)) kan ikke kalles tilbake av NeuroForge**; mottakerne varsles og er avtalemessig forpliktet til å slette, og de listes for Kunden;
   - publiserte aggregerte forskningsresultater trekkes ikke tilbake.
6.3 Mål: sletting i poolen innen [30] dager etter loggføring; reservasjon mot «salg» etter amerikanske delstatslover innen [15] dager [**UVERIFISERT**].

## 7. Motytelse: tjenestekreditter (ikke penger)
7.1 Kunden får **tjenestekreditter** på [●] per [innmeldt samtykkende person / GB / datasett] per [år] (ESTIMAT), begrenset til [●] % av årlig vederlag, som trekkes fra fremtidige fakturaer. **Ingen pengebetaling, og kreditter kan ikke veksles i penger** (beslutning fra daglig leder).
7.2 Kreditter er ikke betaling for de registrertes samtykke, og Kunden skal ikke gi de registrerte betaling som avhenger av valgene.
7.3 **Kreditter som allerede er gitt, tilbakeføres ikke ved tilbaketrekking** [merk: forhandlingsbart – NeuroForge kan foretrekke forholdsmessig tilbakeføring av ubrukte kreditter].
7.4 Kreditter bortfaller ved opphør av MSA [forhandlingsbart]; skatte-/MVA-behandling – **UVERIFISERT**.

## 8. Varighet
Løper med MSA. Hver part kan si opp med [30] dagers varsel. Ved opphør kopieres ikke nye data; NeuroForge kan bruke allerede bidratte data så lenge samtykket står, med mindre Kunden velger full tilbaketrekking etter pkt. 6 [forhandlingsbart].

## 9. Ansvar
MSA pkt. 12 gjelder. Brudd på pkt. 4 eller 5.4 er unntatt det alminnelige taket [forhandlingsbart].

Vedlegg 1 – Bidragsdatasett: | Datasett-ID | Studie | Jurisdiksjoner | Etikkref. | Skjemaversjon | Omfang |

## Hjemmel / Legal basis
- GDPR art. 6 nr. 1 bokstav a, 7, 9 nr. 2 bokstav a, 26 – via personopplysningsloven § 1 (https://lovdata.no/dokument/NL/lov/2018-06-15-38, åpnet 2026-09-26); ordlyd **UVERIFISERT**. Helseforskningsloven/REK – **UVERIFISERT** av denne forfatteren.
- Colorado HB24-1058 (https://leg.colorado.gov/bills/hb24-1058, åpnet 2026-09-26). CA/CT «sale» – **UVERIFISERT**.
- Avtaleloven § 36 (https://lovdata.no/dokument/NL/lov/1918-05-31-4/KAPITTEL_3, åpnet 2026-09-26).
- Internt: legal\data-agreements\contributor-consent.no.md; architecture\BLUEPRINT.md § 8.3–8.4; security\LEGAL-HANDOFF.md A9.
