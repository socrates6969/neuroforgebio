> UTKAST – ikke juridisk rådgivning. Må gjennomgås av norsk advokat før bruk.

# Bilag 1 – Tjenestenivåavtale (SLA)

Del av MSA (msa.no.md / msa.en.md). Gjeldende språk: engelsk [valg for advokat]. **Alle tall er ESTIMATER og forhandlingsbare.** Tilgjengelighetsmålet speiler lanserings-SLO i architecture\BLUEPRINT.md §9 (99,5 %, et mål, ikke målt).

## 1. Omfang
Gjelder generelt tilgjengelige komponenter av produksjonstjenesten i bestillingsskjemaet, for betalte nivåer der skjemaet sier «SLA gjelder».
**Unntatt:** Beta-funksjoner og alt merket forhåndsvisning/tidlig tilgang; akademiske/gratis nivåer; åpen SDK; test-/sandkassemiljøer; nettstedet; målet om fullført slettejobb innen 24 t (BLUEPRINT §8.4 – designmål, ikke SLA) [forhandlingsbart for Enterprise].

## 2. Tilgjengelighet
**Månedlig tilgjengelighetsmål: [99,5] %** per kalendermåned (UTC).
Tilgjengelighet % = (minutter i måneden − nedetid) ÷ (minutter i måneden − unntatte minutter) × 100.
**Nedetid**: minutter der API eller konsoll gir serverfeil (5xx) eller ikke svarer på > [50] % av gyldige forespørsler, målt av NeuroForges eksterne overvåking [planlagt] og bekreftet på statussiden [planlagt].

## 3. Unntak
(a) Planlagt vedlikehold varslet ≥ [5] virkedager før, maks [4] t/mnd, i [vindu]; (b) akutt sikkerhetsvedlikehold [varsles straks]; (c) forhold utenfor NeuroForges kontroll (MSA pkt. 17.1), herunder svikt i skyregion utover arkitekturforpliktelsene [forhandlingsbart]; (d) Kundens systemer, nett, enheter, integrasjoner eller brudd på MSA/AUP; (e) suspensjon etter MSA pkt. 14.3 eller 11.3; (f) bruk over avtalte grenser.

## 4. Servicekreditter
| Månedlig tilgjengelighet | Kreditt (% av månedens vederlag for berørt tjeneste) |
|---|---|
| < [99,5] % og ≥ [99,0] % | [5] % |
| < [99,0] % og ≥ [95,0] % | [10] % |
| < [95,0] % | [25] % |
- Krav skriftlig innen [30] dager etter månedsslutt med tidspunkter; NeuroForge svarer innen [15] dager.
- Kreditt trekkes fra neste faktura (ingen utbetaling unntatt ved opphør). Maks [25] % av månedens vederlag.
- **Vedvarende svikt:** under [99,0] % i [3] påfølgende måneder eller [4] av 12 gir Kunden rett til å si opp berørt bestillingsskjema med [30] dagers varsel og forholdsmessig refusjon.
- Kreditter og oppsigelsesretten er Kundens **eneste beføyelse** ved utilgjengelighet, unntatt ansvar som ikke kan begrenses (MSA pkt. 12.4) [forhandlingsbart]. Kreditter regnes med i taket i MSA pkt. 12.2.

## 5. Brukerstøtte (ESTIMAT)
| Alvorlighet | Definisjon | Første svar (arbeidstid [CET], [man–fre 09–17]) |
|---|---|---|
| S1 Kritisk | Produksjon nede eller mistenkt brudd på personopplysningssikkerheten | [4] t [Enterprise: 1 t, 24/7] |
| S2 Høy | Viktig funksjon svekket, ingen omvei | [1] virkedag |
| S3 Normal | Delvis svekket / omvei finnes | [2] virkedager |
| S4 Lav | Spørsmål, ønsker | [5] virkedager |
Svartider er ikke løsningsgarantier og gir ikke kreditt med mindre skjemaet sier det. Bruddvarsler følger databehandleravtalen (innen [24] t etter bekreftelse).

## 6. Rapportering
Månedlig tilgjengelighetsrapport på forespørsel [statusside – planlagt].

## Hjemmel / Legal basis
Avtaleloven § 36 (https://lovdata.no/dokument/NL/lov/1918-05-31-4/KAPITTEL_3, åpnet 2026-09-26). Mål: architecture\BLUEPRINT.md §9 og §8.4. Kreditttrinn: forfatterens ESTIMAT, ikke sammenlignet med konkurrenter (**UVERIFISERT**).
