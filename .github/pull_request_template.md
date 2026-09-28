## What and why

<!-- One paragraph. Link the BUILD-GUIDE step and any SEC IDs this change implements. -->

## Checks

- [ ] `node tools/dev/tasks.mjs lint` and `node tools/dev/tasks.mjs test` pass locally (say which toolchains were skipped)
- [ ] No neural or human-subject data and no secrets (repo-guard passes)
- [ ] No operation, message or field that sends commands, parameters, waveforms or triggers to acquisition or stimulation hardware; LSL stays inlet-only (SEC-090/091, hw-guard passes)

## Security-relevant design change? (SEC-002)

Security-relevant = auth, crypto, governance, the stream protocol, CI/supply chain, or anything that touches acquisition hardware.

- [ ] Not security-relevant
- [ ] Security-relevant: this PR links an ADR in `docs/adr/` that contains a **threat-model delta** (new or changed `T-xx`/`P-xx` in THREAT-MODEL.md, or "no change" with a reason). ADR: <!-- docs/adr/NNNN-....md -->
- [ ] Security-relevant: a reviewer from the security role has signed off (CODEOWNERS)

## Dependency review (SEC-084)

- [ ] No new direct dependency, **or** every new direct dependency is listed below and a security-role reviewer is requested (CODEOWNERS on manifests and lockfiles)
- [ ] Each new package: licence allowed by `docs/security/licences.md` (licence-check passes for browser-shipped code), a release within the last 24 months, no install scripts from unknown publishers, nothing loaded from a CDN
- [ ] Lockfile updated by the one person who runs installs; CI installs stay frozen (SEC-080)

| Package | Version | Licence | Last release | Install scripts | Why needed |
| ------- | ------- | ------- | ------------ | --------------- | ---------- |
|         |         |         |              |                 |            |
