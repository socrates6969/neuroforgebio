# NeuroForge Bio: vulnerability disclosure policy (draft)

Status: **DRAFT policy v0.1**, 2026-09-26, security expert. The safe-harbour wording must be reviewed by nfb-legal and a Norwegian lawyer (advokat) before publication 🔒. **Not legal advice.**
The published version appears at `/security#disclosure` (see `website-security-page.md`) and is linked from `/.well-known/security.txt` (RFC 9116) and `SECURITY.md` in each repository (SEC-001, SEC-130, SEC-157).

**Why this policy matters beyond our own security.** FDA's Feb 2026 cybersecurity guidance says a plan "including coordinated vulnerability disclosure and related procedures" is required for cyber devices (section 524B(b)(1)). The EU Cyber Resilience Act expects coordinated vulnerability disclosure from manufacturers of software products (`STANDARDS-MAP.md` §4.3, §5.1). Device makers who embed our components need to cite a supplier CVD process. This document is written so they can.

---

## 1. Scope

**In scope**
- NeuroForge Bio websites on `<domain TBD>` and its subdomains that we operate.
- The NeuroForge Bio platform, API (REST and gRPC) and web console, **only against your own trial or test tenant**.
- Our released software: `nf-core`, the Python package, the C/C++ SDK, and the Unity/Unreal packages when released.
- Our published container images, SBOMs, provenance and signatures.

**Out of scope**
- Other customers' tenants, data or accounts.
- **Any medical device, BCI or acquisition hardware**, including customers' devices that use our components. Report those to the device manufacturer. We will help coordinate if our component is involved.
- Denial-of-service, load or volumetric testing.
- Social engineering, phishing or physical attacks against our staff, customers or suppliers.
- Third-party services (cloud provider, IdP, CDN, package registries). Report to them. Tell us if it affects us.
- Findings with no security impact: missing headers on non-HTML resources, version banners, self-XSS, clickjacking on pages without actions, SPF/DMARC reports without a spoofing demonstration.

## 2. Rules for researchers

1. Test only against accounts and data you own. **Never access, download, keep or share neural recordings or metadata belonging to anyone else.** If you encounter such data, stop, do not look further, and report it to us immediately.
2. Use the smallest proof of concept that shows the issue.
3. Do not degrade the service, corrupt data or change other users' data.
4. Do not publish or share the issue until we have fixed it or the disclosure deadline in §5 has passed. We will agree on the date with you.
5. Follow the law that applies to you.

## 3. How to report

- **Email:** `security@<domain TBD>`
- **Encrypted channel:** on our roadmap (an OpenPGP key or a web form over TLS). Until then, send a short first message without details, and we will arrange a secure transfer.
- **Language:** English or Norwegian.
- **Please include:** the affected component and version or URL; the steps to reproduce; the impact you believe it has; your proof of concept; whether it is already public; and how you want to be credited.

## 4. What we commit to

| Step | Target |
|---|---|
| Acknowledge the report | ≤ 3 business days |
| Initial assessment and severity (CVSS v4.0 or v3.1, stated) | ≤ 10 business days |
| Status updates | At least every 14 days until closed |
| Fix targets (from confirmation) | Critical ≤ 14 days · High ≤ 30 days · Medium ≤ 90 days · Low: next planned release |
| Advisory | Published when a fix is available, with a CVE ID (through a CNA or the code host's advisory system 🔒), affected and fixed versions, an updated SBOM and a VEX statement |
| Credit | In the advisory and on our acknowledgements page (roadmap), if you wish |

The targets are goals, not guarantees. If we are going to miss one, we will tell you why and give a new date.

**Rewards:** we do not run a paid bug bounty yet (**roadmap**, owner decision 🔒).

## 5. Coordinated disclosure timeline

- The default embargo is **90 days** from our acknowledgement, or the release of a fix, whichever comes first.
- If the issue is being **actively exploited**, we may publish mitigations sooner. We will then also meet our regulatory reporting duties, which may require reporting to authorities within 24 hours of our becoming aware (EU CRA Art. 14, `INCIDENT-RESPONSE.md` §6).
- If the issue affects a component that customers embed in medical devices, we notify those customers **before** public disclosure so they can assess their devices. We may ask for a short extension for that reason.

## 6. Safe harbour (to be reviewed by counsel)

If you make a good-faith effort to follow this policy:
- we consider your research authorised under our terms of service for the activities allowed here;
- we will not start legal action or file a complaint with law enforcement against you for that research;
- if a third party brings legal action about activities that followed this policy, we will make it known that you acted with our authorisation.

This does not authorise access to other people's data, and it cannot bind third parties such as customers or cloud providers.

## 7. Third-party components

If the vulnerability is in an open-source component we use (MNE, pynwb, liblsl, a Rust crate), please also report it upstream. We will track it in our SBOM and VEX and ship the fix or a mitigation. If you report it only to us, we will coordinate with the upstream maintainers and credit you.

## 8. Internal handling (not published)

- The mailbox is monitored by the security lead with a deputy. Every report gets a tracking ID in the advisory log.
- Triage uses `THREAT-MODEL.md` IDs where they fit. A report that suggests exploitation or data exposure opens an incident under `INCIDENT-RESPONSE.md`.
- The fix path: private branch → review by two people including the security role → signed release (SEC-081/082) → advisory + VEX + SBOM diff (SEC-132) → notice to affected customers.
- Metrics kept for FDA-style postmarket plans: time to acknowledge, time to fix, and the percentage of vulnerabilities fixed within target.
