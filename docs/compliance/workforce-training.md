# Workforce training — DRAFT v0.1

**DRAFT for counsel review. Not legal advice. Not adopted. No claim of HIPAA compliance.**
Delivered to counsel: pending (owner action).

The HIPAA Security Rule's security awareness and training expectation is referenced by name only
(**UNVERIFIED**; counsel confirms content and frequency).

## 1. Who

Everyone (staff and contractors) before they get any access to a `phi=true` tenant, its keys or the
production cloud account.

## 2. Content (draft outline)

1. What PHI is for our customers, and why neural data is sensitive even when it is not PHI
   (`market/regulation.md` §1, §3).
2. Our safeguards and each person's part: phishing-resistant login, least privilege, no PHI outside
   listed services (`infra/policy/phi-services.json`), no PHI in tickets, chat or logs (SEC-147).
3. Recognising and reporting incidents (`security/INCIDENT-RESPONSE.md`, `incident-response.md`).
4. Consent, withdrawal and deletion (5.3-5.5): what the platform does, and what people must not undo.
5. Sanctions for policy violations (wording by counsel).

## 3. Frequency and records

At onboarding, then yearly, and after a material policy change. Record per person: date, version of
the material, completion, signature. Access to PHI tenants is granted only after a completed record
(checked in the quarterly access review).
