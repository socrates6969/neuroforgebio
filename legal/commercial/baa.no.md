> UTKAST – ikke juridisk rådgivning. Må gjennomgås av norsk advokat før bruk.

# PLANLAGT – TILBYS IKKE ENNÅ
# Business Associate Agreement (amerikansk HIPAA) – norsk sammendrag

**Status: PLANLAGT – tilbys ikke ennå.** NeuroForge Bio signerer ikke BAA i dag, og kunder skal ikke laste opp PHI (MSA pkt. 10.6). Den bindende malen er på engelsk (baa.en.md); dette er et norsk sammendrag for styret/advokat. En BAA er et amerikansk rettsinstrument og må vurderes av **amerikansk HIPAA-advokat** i tillegg til norsk advokat. NeuroForge påstår ikke å være «HIPAA-compliant».

**Forutsetninger før bruk** (architecture\BLUEPRINT.md §8.5): (1) BAA med skyleverandør signert og PHI-leietakere begrenset til BAA-dekkede tjenester; (2) risikovurdering, retningslinjer, hendelseshåndtering og opplæring etter HIPAA Security Rule på plass; (3) gjennomgang av amerikansk advokat.

## Innhold (tilsvarer 45 CFR 164.504(e))
1. **Definisjoner** som i 45 CFR del 160 og 164.
2. **Plikter for Business Associate:** (a) ingen bruk/utlevering utover avtalen eller lov; (b) sikringstiltak og etterlevelse av Security Rule (subpart C) for elektronisk PHI; (c) rapportere uautorisert bruk/utlevering, brudd på usikret PHI (164.410) og sikkerhetshendelser innen [5] virkedager [frister fastsettes av US-advokat]; (d) underleverandører forpliktes skriftlig til samme vilkår (164.502(e)(1)(ii), 164.308(b)(2)); (e) innsyn (164.524) innen [15] dager; (f) retting (164.526); (g) logg over utleveringer (164.528); (h) følge Privacy Rule (subpart E) der BA utfører CE-plikter; (i) interne rutiner og dokumenter tilgjengelig for HHS-ministeren; (j) minimumsprinsippet.
3. **Tillatt bruk:** bare for å levere Tjenesten; [valgfritt] egen administrasjon etter 164.504(e)(4). **Ingen** avidentifisering til eget bruk, aggregering, salg eller modelltrening på PHI (jf. MSA pkt. 4.3).
4. **Covered Entitys plikter:** varsle om begrensninger, tilbakekall og avtalte restriksjoner (164.522).
5. **Varighet og opphør:** heving ved vesentlig mislighold som ikke rettes innen [30] dager (164.504(e)(2)(iii)); ved opphør tilbakeleveres eller destrueres PHI, ellers videreføres beskyttelsen. **Begrensning:** PHI eksportert ut av Tjenesten kan ikke kalles tilbake; modeller trenes på nytt, ikke «avlæres».
6. **Diverse:** henvisninger til gjeldende regelverk; endres ved regelendringer; ansvar etter MSA pkt. 12 [US-advokat vurderer eget tak].

## Hjemmel / Legal basis
- 45 CFR 164.504(e) m.fl. – etter forfatterens kunnskap om HHS' eksempelbestemmelser. **UVERIFISERT**: hhs.gov-siden ga **HTTP 403** (2026-09-26); eCFR videresendte til bot-sjekk; web.archive.org blokkert.
- HIPAA-omfang: market\regulation.md §3 (åpnet av markedsteamet, ikke av denne forfatteren).
- Produktfakta: architecture\BLUEPRINT.md §8.5; DECISIONS.md D4.
