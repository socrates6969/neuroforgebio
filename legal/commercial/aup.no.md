> UTKAST – ikke juridisk rådgivning. Må gjennomgås av norsk advokat før bruk.

# Retningslinjer for akseptabel bruk (AUP)

Versjon [0.1] · [DATO] · Gjelder NeuroForge Bio-plattformen, API-er, konsoll, modellregister og proprietære plattform-/klientkomponenter («Tjenesten»), og er en del av MSA. [Åpen SDK reguleres av Apache-2.0 uten bruksbegrensninger; AUP gjelder den bare ved bruk sammen med Tjenesten.] Gjeldende språk: engelsk [valg for advokat].

Brudd kan føre til fjerning av innhold, suspensjon (MSA pkt. 14.3) eller oppsigelse, og brudd på MSA pkt. 10.7/11 er unntatt ansvarstaket (MSA pkt. 12.4 d). Meld misbruk til [abuse@neuroforge.bio].

## Du skal ikke bruke Tjenesten til å:

### 1. Reidentifisere personer
1.1 Forsøke å reidentifisere eller koble pseudonymiserte/avidentifiserte registrerte til identifiserte personer, herunder ved å kombinere nevrale data med andre datasett, med mindre behandlingsansvarlig har grunnlag, etikkgodkjenningen dekker det og de registrerte er informert.
1.2 Bruke nevrale data til entydig identifikasjon (biometrisk) uten uttrykkelig grunnlag og unntak etter GDPR art. 9 nr. 2 og eventuelt opt-in etter amerikansk delstatslov.

### 2. Forbudt KI-praksis (KI-forordningen art. 5)
Der forordning (EU) 2024/1689 gjelder:
2.1 **utlede følelser hos personer på arbeidsplassen eller i utdanningsinstitusjoner**, unntatt av medisinske eller sikkerhetsmessige grunner;
2.2 subliminale, manipulerende eller villedende teknikker som vesentlig forvrider atferd og gir eller sannsynlig gir betydelig skade;
2.3 biometrisk kategorisering som utleder etnisitet, politisk syn, fagforeningsmedlemskap, religion/livssyn, seksualliv eller seksuell legning;
2.4 annen praksis i art. 5 (utnyttelse av sårbarhet, sosial poengsetting m.m.).
Bruksbegrensningsflagg i registeret skal respekteres. [**UVERIFISERT** mot offisiell tekst.]

### 3. Behandle data uten nødvendig samtykke eller godkjenning
3.1 Laste opp eller behandle personopplysninger (særlig nevrale data/helsedata) uten gyldig grunnlag, nødvendig samtykke (også opt-in for nevrale data som sensitive etter delstatslover som Colorado, California, Connecticut, Montana) og nødvendig REK-/IRB-godkjenning.
3.2 Behandle utenfor samtykkeomfanget i samtykkeloggen, eller omgå samtykkekontrollene.
3.3 Laste opp HIPAA-PHI (BAA tilbys ikke – PLANLAGT).

### 4. Selge eller utnytte identifiserbare nevrale data
4.1 Selge, leie ut eller omsette identifiserbare (også pseudonymiserte) nevrale data, eller dele dem for reklame eller profilering for markedsføring, kreditt, forsikring eller ansettelse.
4.2 Bruke nevrale data til beslutninger om ansettelse, opptak, forsikring, kreditt eller strafferettslig status.

### 5. Ta kliniske beslutninger
5.1 Bruke Tjenesten, Resultater eller registermodeller til diagnose, behandling, overvåking eller kliniske beslutninger om en pasient, eller til å styre stimulering/utstyr i lukket sløyfe (MSA pkt. 10.1).
5.2 Markedsføre Resultater som klinisk validerte når de ikke er det.

### 6. Bryte lov eller andres rettigheter
6.1 Bryte eksportkontroll- eller sanksjonsregler, eller gi tilgang til sanksjonerte personer eller land (MSA pkt. 11).
6.2 Krenke immaterielle rettigheter eller konfidensialitet; laste opp data du ikke har rett til.
6.3 Utvikle våpen, overvåke enkeltpersoner uten hjemmel, eller bruke nevrale data til avhør/«løgndeteksjon» [policyvalg – advokat/eier].
6.4 Trakassere, diskriminere eller skade personer.

### 7. Angripe eller misbruke Tjenesten
7.1 Sondere, skanne eller teste sårbarheter (unntatt etter vår policy for ansvarlig varsling), omgå autentisering, bruksgrenser eller leietakerisolasjon, eller få tilgang til andre kunders data.
7.2 Laste opp skadevare, drive kryptoutvinning eller skape urimelig last.
7.3 Dele påloggingsdata eller API-nøkler med andre enn Autoriserte brukere.

## Unntak for forskning
Sikkerhets- og personvernforskning på **egen leietaker og egne data** (f.eks. test av reidentifiseringsrisiko på egne datasett med etikkgodkjenning) er tillatt hvis det ikke påvirker andre, og funn om Tjenesten meldes først til [security@neuroforge.bio].

## Endringer
NeuroForge kan oppdatere AUP med [30] dagers varsel; vesentlige innskrenkninger gir oppsigelsesrett etter MSA.

## Hjemmel / Legal basis
- KI-forordningen (EU) 2024/1689 art. 5 – EUR-Lex lastet ikke (2026-09-26) – **UVERIFISERT**; pkt. 2.1–2.3 etter market\regulation.md §5 (grad B, gjelder fra 2.2.2025).
- GDPR art. 9 via personopplysningsloven § 1 (https://lovdata.no/dokument/NL/lov/2018-06-15-38, åpnet 2026-09-26); ordlyd **UVERIFISERT**.
- Colorado HB24-1058 (https://leg.colorado.gov/bills/hb24-1058, åpnet 2026-09-26). CA/CT/MT – etter market\regulation.md, **UVERIFISERT** av denne forfatteren.
- Eksportkontrolloven (https://lovdata.no/dokument/NL/lov/1987-12-18-93, åpnet 2026-09-26).
- Produktfakta: architecture\BLUEPRINT.md §1, §8.2, §8.3.
