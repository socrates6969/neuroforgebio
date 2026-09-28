> DRAFT – not legal advice. Must be reviewed by a Norwegian lawyer (advokat) before use.

<!-- meta-description: Draft cookie statement: this site sets no cookies and uses no analytics, ads or third-party scripts. Not legal advice; pending advokat review. -->

# Cookie statement – [neuroforge.bio]

Version [1.0] · Last updated [DATE] · [Proposal: English prevails in case of conflict – advokat choice.]

## Short version
**This website sets no cookies and stores nothing on your device.** We use no analytics, no advertising, no social-media plugins and no third-party scripts. Fonts are served from our own server. That is why you see no cookie banner.

## What this means in detail
- **Cookies:** none set by us or by third parties.
- **Local storage / session storage / IndexedDB / similar:** none. [Build team: confirm before launch. If the theme or language switch ever stores a preference, update the table below.]
- **Tracking pixels, fingerprinting, embedded videos or maps:** none.
- **Fonts and code:** self-hosted; your browser does not contact Google Fonts or any other third party when loading our pages.
- **Server logs:** our hosting/CDN provider records technical request data (IP address, time, page, browser type) to deliver and protect the site. That is not stored on your device; see the [Privacy policy](/legal/privacy).

| Name | Type | Purpose | Duration | Set by | Consent needed? |
|---|---|---|---|---|---|
| – | – | *No storage is used today* | – | – | – |

## When would this change – and would we ask you?
Norwegian law (ekomloven § 3-15) allows storing or reading information on your device without consent only when it is purely technical for transmitting a communication, or **strictly necessary** to deliver a service you have explicitly asked for. In all other cases we must inform you and obtain **consent meeting GDPR standards** first.
- **Would NOT need consent (strictly necessary; we would list it here):** e.g. a session cookie to keep you logged in to the platform console once it exists; a security/load-balancing cookie; storing a preference you actively set (such as theme) – [exemption for preferences to be confirmed by advokat].
- **WOULD need your prior consent (and a "Reject" choice as easy as "Accept"):** any analytics (including most "privacy-friendly" tools that store an identifier), A/B testing, embedded third-party content (YouTube, maps, social media), marketing or retargeting pixels, or loading fonts/scripts from third-party servers.
We have decided (design decision D9) not to use any of the latter. If that ever changes, we will update this page, add a consent tool **before** anything is set, and let you change your choice at any time.

## Contact
[privacy@neuroforge.bio] · [NeuroForge Bio AS] (under formation), org.nr. [●].

## Hjemmel / Legal basis
- Ekomloven (LOV-2024-12-13-76) § 3-15 "Bruk av informasjonskapsler mv.", in force 1 Jan 2025 – information + GDPR-standard consent; exemptions for pure transmission and strictly necessary storage for a service explicitly requested: https://lovdata.no/dokument/NL/lov/2024-12-13-76 (opened 2026-09-26).
- Datatilsynet, cookies guidance (consent per GDPR; "as easy to say no as yes"; Nkom decides scope/exemptions, Datatilsynet assesses information and consent): https://www.datatilsynet.no/personvern-pa-ulike-omrader/internett-og-apper/cookies/ (opened 2026-09-26).
- GDPR Art. 4(11), 7 (consent) – EUR-Lex failed to load – **verbatim UNVERIFIED**.
- Whether a user-set preference (theme) qualifies as "strictly necessary" – **UNVERIFIED**, advokat/Nkom practice.
- Product facts: architecture\DECISIONS.md D9 (self-hosted fonts, no third-party scripts, CSP `script-src 'self'`); D3 (theme chosen at build time).
