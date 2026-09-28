# Incident response: PHI addendum — DRAFT v0.1

**DRAFT for counsel review. Not legal advice. Not adopted. No claim of HIPAA compliance.**
Delivered to counsel: pending (owner action).

The incident response plan is `security/INCIDENT-RESPONSE.md` (roles, severity, phases, playbooks,
notification clocks, tabletops). This addendum lists only what changes when a `phi=true` tenant is
involved. It does not restate or replace the plan.

## 1. When it applies

Any incident that touches data, keys, logs or systems of a `phi=true` tenant, or any service in
`infra/policy/phi-services.json`.

## 2. Additions to the plan

1. **Severity:** an incident involving PHI is at least SEV-2 until the incident commander rules out
   exposure; any confirmed exposure is SEV-1.
2. **Notification:** the Breach Notification Rule duties, the timelines in `INCIDENT-RESPONSE.md` §6
   (already marked UNVERIFIED there) and the timelines of any BAA we sign are confirmed by US HIPAA
   counsel before the first PHI tenant. This addendum sets no timeline of its own.
3. **Customer first:** as a business associate we would notify the covered entity (the customer),
   which handles notification to individuals and regulators. Counsel confirms (**UNVERIFIED**).
4. **Evidence:** preserve the audit chain, the WORM anchors and the placement-guard denials
   (`authz.denied`, action `phi:placement`) before any change.
5. **Provider:** open a case with the cloud provider under its BAA process when the provider's
   services are involved (owner action; the contact route is kept in the private runbook).

## 3. Exercises (SEC-115)

Tabletop twice a year. Once PHI tenants exist, one scenario per year involves PHI (for example a
misconfigured placement that put PHI on a non-listed service). Notes go to the records named in
`INCIDENT-RESPONSE.md` §8.
