# NeuroForge Bio: security requirements (testable)

Status: **DRAFT v0.1**, 2026-09-26, security expert. Nothing here is built. Standards context: `STANDARDS-MAP.md`. Threats and ratings: `THREAT-MODEL.md` (threat IDs `T-xx`, privacy IDs `P-xx`).

## How to use this file

- Each requirement has an **ID** (`SEC-nnn`), a **MUST/SHOULD** statement, a **Verify** line (the test or evidence that proves it), the **BUILD-GUIDE step** that owns it, and a reference to an ASVS 5.0 chapter (V1–V17) or a standard.
- A BUILD-GUIDE step is **not done** until the SEC tests mapped to it pass in CI (BUILD-GUIDE "How to read this guide").
- Requirement IDs are stable. Never renumber; deprecate instead.
- 🔒 marks items that need the owner (spend, accounts, publishing, external parties).
- **Priority for the build team right now (M0 + M1):** §A. Everything else is listed so the M2+ design does not paint us into a corner.

---

## §A. NOW: M0 foundations and the M1 website (send to nfb-build-queen)

### A.1 Repository, CI and supply chain (M0)

| ID | Requirement | Verify | Step | Ref |
|---|---|---|---|---|
| SEC-080 | All dependencies MUST be installed from lockfiles (`pnpm-lock.yaml`, `uv.lock`, `Cargo.lock`). CI MUST use frozen installs (`pnpm install --frozen-lockfile`, `uv sync --locked`, `cargo build --locked`) | CI fails if a lockfile is out of date (fixture PR) | 0.1, 0.2 | A03:2025; SSDF PW.4 |
| SEC-081 | Every release artefact (site bundle, container image, wheel, crate) MUST be signed with **Sigstore cosign** in keyless mode from the CI OIDC identity. Signatures and attestations are recorded in Rekor | `cosign verify` / `cosign verify-blob` against the expected CI identity and issuer passes in the release job; a tampered artefact fails | 0.2 (site), 2.1 (images), 4.3 (wheels) | SSDF PS.2; A08:2025 |
| SEC-082 | Release builds MUST emit **SLSA build provenance** signed by the CI platform (Build L2 at M0; Build L3 by M4: ephemeral isolated runners, no long-lived secrets in build steps, provenance generated outside user-controlled steps) | Provenance attestation attached; verifier checks builder ID + source repo + commit | 0.2; 4.3 | SLSA v1.x Build track |
| SEC-083 | Every CI build MUST produce a **CycloneDX JSON SBOM** (spec ≥1.6) per artefact. Each component carries `nfb:supportLevel` (`maintained`/`unmaintained`/`abandoned`/`unknown`) and `nfb:endOfSupport` (date or `unknown`) properties, as FDA's Feb 2026 guidance expects | SBOM schema-validates; a script asserts that both properties exist on every component; the SBOM is attached to the build (0.3 acceptance test) | 0.3 | FDA 524B(b)(3); CRA Annex I Part II |
| SEC-084 | Dependency policy: **new direct dependencies need a reviewer from the security role** in the PR. Denied: packages with no release in 24 months (unless vendored and reviewed), install scripts from unknown publishers, copyleft licences in `apps/web`/`packages/*` shipped to browsers, CDN-loaded scripts. Allowed licences listed in `docs/security/licences.md` | `pnpm audit`/`pip-audit`/`cargo deny check` in CI; CODEOWNERS on lockfiles; a licence check fails on a GPL fixture | 0.3 | A03:2025 |
| SEC-085 | Known-vulnerability gate: CI MUST fail on any **critical/high** CVE with a fix available, and on **any** CVE listed in CISA KEV, unless a signed **VEX** statement (`not_affected` + justification) is committed | A fixture dependency with a known high CVE fails CI; adding a VEX file makes it pass | 0.3 | FDA (KEV); SSDF RV.1 |
| SEC-086 | Secret scanning in CI **and** as a pre-commit hook (gitleaks or equivalent). Push protection on the hosting provider 🔒 | A committed fake AWS key fails CI (0.3 acceptance test) | 0.3 | V13; SSDF PS.1 |
| SEC-087 | Data-file guard: the repo MUST NOT accept neural recordings. `.gitignore` covers `*.edf *.bdf *.nwb *.xdf *.set *.fdt *.fif *.vhdr *.eeg *.vmrk *.mat *.npy *.zarr data/`; a CI check rejects these extensions, plus any file >5 MB outside `tools/synth/fixtures` | A committed `.edf` fails CI (0.3 acceptance test) | 0.3 | GDPR Art. 32 |
| SEC-088 | Branch protection on `main`: signed commits required; ≥1 review (≥2 on `services/platform/governance`, `infra/`, `core/nf-core/src/crypto*`); required status checks; no force-push; CI tokens read-only by default, and write scopes granted per job | A hosting-settings export is checked in `docs/security/`; a manual audit each milestone 🔒 (the account is owner-created) | 0.2 | SSDF PS.1 |
| SEC-089 | GitHub Actions (or equivalent) MUST pin third-party actions by **commit SHA**. `pull_request_target` is banned. Workflows from forks get no secrets | A lint (zizmor/actionlint or a grep rule) fails on a tag-pinned action | 0.2 | A03:2025 |
| SEC-001 | `SECURITY.md` in the repo root links to the disclosure policy (`VULN-DISCLOSURE.md` text) and the security contact | File exists; link-checked | 0.3 | RFC 9116; CRA |
| SEC-002 | Security-relevant design changes (auth, crypto, governance, stream protocol, anything that touches acquisition hardware) MUST carry an ADR with a threat-model delta | PR template checkbox; reviewer sign-off recorded | 0.1 | SSDF PW.1 |

### A.2 Website (M1, both themes, one shared config)

The headers live in **one shared file** (for example `apps/web/security-headers.ts`, emitted as `_headers`/host config for both `dist/clinical` and `dist/cosmos`). Both builds get identical headers. The only theme difference allowed is that the cosmos build loads the self-hosted three.js chunk, which `script-src 'self'` already allows.

| ID | Requirement | Verify | Step | Ref |
|---|---|---|---|---|
| SEC-150 | **Content-Security-Policy** (enforced, not report-only, at public launch): `default-src 'none'; script-src 'self' <build-time sha256 hashes only if Astro emits inline scripts>; style-src 'self' <hashes if any>; img-src 'self' data:; font-src 'self'; connect-src 'self'; manifest-src 'self'; worker-src 'self'; media-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'; upgrade-insecure-requests`. **No `'unsafe-inline'`, no `'unsafe-eval'`, no third-party origins** (D9). When the early-access form goes live (4.7), add only the API origin to `connect-src`/`form-action` | Playwright on both builds: zero CSP violations in the console on every page; a unit test parses the header and fails on `unsafe-*` or any host other than self/API; a test injects an inline `<script>` fixture and asserts it is blocked | 1.3, 1.10 | V3 (ASVS 5.0 Web Frontend) |
| SEC-150a | Astro inline scripts/styles: configure the build so that no inline script is needed (hoisted/bundled scripts; `build.inlineStylesheets: 'never'`), **or** generate CSP hashes at build time from the emitted HTML. Island hydration code MUST be covered (a build-verified fact, not assumed) | A post-build script scans `dist/**/*.html` for `<script>` without `src` and `style=` attributes; every one has a matching hash in the header, or the build fails | 1.6 | V3 |
| SEC-151 | **HSTS**, staged: previews `max-age=300`; first public week `max-age=86400`; then `max-age=63072000; includeSubDomains; preload`. **Preload-list submission is an owner action 🔒**, only after every subdomain serves HTTPS. hstspreload.org requires ≥31536000 s, `includeSubDomains`, `preload`, a valid cert, and an HTTP→HTTPS redirect on the same host | Smoke test checks the header value per environment; a checklist of hstspreload.org requirements is recorded in the 1.10 PR | 1.10 | V12; hstspreload.org |
| SEC-152 | **Permissions-Policy**: `accelerometer=(), ambient-light-sensor=(), autoplay=(), bluetooth=(), browsing-topics=(), camera=(), display-capture=(), encrypted-media=(), fullscreen=(self), geolocation=(), gyroscope=(), hid=(), magnetometer=(), microphone=(), midi=(), payment=(), publickey-credentials-get=(), screen-wake-lock=(), serial=(), usb=(), xr-spatial-tracking=()`. The marketing site never touches devices; a neural-data company's site must be visibly incapable of reaching USB/serial/HID/Bluetooth amplifiers | Header snapshot test | 1.10 | V3 |
| SEC-153 | **Referrer-Policy: `strict-origin-when-cross-origin`** (no full URLs leak to journals and GitHub links), **X-Content-Type-Options: `nosniff`**, **X-Frame-Options: `DENY`** (legacy twin of `frame-ancestors`) | Header snapshot test | 1.10 | V3 |
| SEC-154 | **Cross-Origin-Opener-Policy: `same-origin`**; **Cross-Origin-Resource-Policy: `same-origin`**; **Cross-Origin-Embedder-Policy: `require-corp`**. COEP is compatible because every resource is self-hosted (D9; three.js self-hosted per 1.5). If a future page must embed a cross-origin resource, switch that page to `COEP: credentialless` by ADR (SEC-002), never by dropping COEP site-wide | Playwright asserts `crossOriginIsolated === true` on `/` in both builds and that the cosmos hero renders (WebGL + fallback) with COEP on | 1.5, 1.10 | V3 |
| SEC-155 | **No third-party requests**: no analytics, fonts, CDNs, embeds or social widgets. Fonts are self-hosted after licence check (D9) | Playwright network log on every page: every request host equals the site host (the 1.5 "no jsdelivr" test, generalised) | 1.1, 1.5, 1.9 | GDPR; D9 |
| SEC-156 | **Subresource integrity** is not needed for same-origin assets. The site MUST NOT load any script it did not build. Built JS files are content-hashed and immutable (`Cache-Control: public, max-age=31536000, immutable`); HTML is `no-cache` | Header test on a hashed asset vs HTML | 1.6 | V3 |
| SEC-157 | `/.well-known/security.txt` per RFC 9116: `Contact`, `Expires` (<1 year ahead, regenerated at each build from a date in content), `Preferred-Languages: en, no`, `Canonical`, `Policy` → `/security#disclosure`. Served over HTTPS as `text/plain`. **Signing it with OpenPGP is roadmap** (needs a managed key) | A build test parses the file: both required fields present, Expires in the future and < 365 days away; the file is identical in both builds except `Canonical` | 1.8 | RFC 9116 |
| SEC-158 | `/security` page built from `security/website-security-page.md` content (EN + NO), one page shared by both themes; status labels exactly as written there; copy-lint passes | Copy-lint + text-diff test (1.6) | 1.8 | CONTENT-SPEC |
| SEC-159 | Early-access form (when enabled at 4.7): server-side validation, rate limit per IP and per email, double opt-in, no neural or health fields, honeypot rather than a third-party CAPTCHA, and CSRF not applicable (no cookies/session), with CORS limited to the site origins | 4.7 acceptance tests + a CORS test | 4.7 🔒 | V2, V4 |
| SEC-160 | Hosting: TLS certificates auto-managed; **TLS 1.2 minimum, TLS 1.3 preferred** at the CDN (browser reach; the platform API is 1.3-only, SEC-030); HTTP→HTTPS 301 redirect; DNSSEC and a CAA record limiting issuers **when the domain is registered 🔒** | An external header/TLS check of **our own** preview host only, from CI | 1.10 🔒 | V12 |

---

## §B. Identity and access (M2 onward)

| ID | Requirement | Verify | Step | Ref |
|---|---|---|---|---|
| SEC-010 | Human login MUST be through **OIDC** (Authorization Code + PKCE) with a managed IdP (D4); SAML for enterprise SSO. The platform never stores passwords | Integration test with a mock IdP; no password column exists in the schema | 2.2 | V6, V10 |
| SEC-011 | **Roles `owner`, `admin`, `data-steward`, `auditor` MUST authenticate with a phishing-resistant authenticator: passkeys/WebAuthn** (platform or roaming). The platform checks it via the IdP's `amr`/`acr` claim (e.g. `hwk`/`phr`) and refuses admin sessions without it. Rationale: NIST SP 800-63B-4 requires phishing resistance at AAL3 and says verifiers at AAL2 "SHALL offer at least one phishing-resistant authentication option" | Token-claim test: an admin token without the phishing-resistant `amr` → 403 on every admin route | 2.2 | V6; SP 800-63B-4 |
| SEC-012 | **Break-glass and KMS-admin accounts MUST use hardware-bound (non-syncable) security keys.** SP 800-63B-4: syncable authenticators "SHALL NOT be used at AAL3". Two keys per person, stored separately | A quarterly access review record lists the key type per privileged identity | 2.2, 5.7 | V6 |
| SEC-013 | All other human users MUST use MFA. Passkeys are offered to everyone; TOTP is allowed; **SMS is not allowed** | IdP policy export checked in; login test without a second factor fails | 2.2 | V6 |
| SEC-014 | API keys: ≥128-bit random, shown once, stored as a hash (Argon2id or HMAC-SHA-256 with a server pepper held in KMS), with scopes, expiry ≤ 365 days (default 90) and a prefix for secret scanning (`nfb_live_…`, registered with GitHub secret scanning 🔒) | An expired key → 401; a wrong scope → 403 (2.2 test); the DB contains no plaintext key (grep test) | 2.2, 4.8 | V6, V9 |
| SEC-015 | Sessions: console tokens are short-lived (access ≤ 15 min, refresh rotation with reuse detection), idle logoff at 15 min, absolute lifetime 12 h; cookies `Secure; HttpOnly; SameSite=Strict; __Host-` prefix | Session tests; replaying a refresh token revokes the family | 3.8 | V7; HIPAA 164.312(a) auto-logoff |
| SEC-016 | Device tokens (edge SDK): bound to a registered device ID and key pair; the private key is generated on the device and stored in the OS keystore where available (DPAPI/Keychain/libsecret), never exported; **enterprise option: mTLS** with per-device client certs | A token replayed from another key → 401; key-export test on each OS | 2.7, 4.2 | V6, V9 |
| SEC-017 | Revocation: revoking a key, device or user stops access within **60 s** everywhere, including open gRPC streams (the stream is closed) | 4.8 test extended to an open stream | 4.8 | V7 |
| SEC-020 | One `authorize(principal, action, resource)` + one `policy.check()` (5.4). **Deny by default.** Role × endpoint matrix generated from OpenAPI and tested | 2.2 matrix test; the route-enumeration test fails on an unmapped route | 2.2, 5.4 | V8; API5 |
| SEC-021 | Tenant isolation at 3 layers: app check, Postgres RLS, per-tenant KMS key. **Every** route has a two-tenant test | 2.1 isolation test + per-route BOLA test | 2.1 | V8; API1 |
| SEC-022 | Governance properties (`classification`, `nervous_system`, `consent_scope`, `use_restrictions`) are writable only by `data-steward`/`admin`, and every change is audited | Property-level authz tests | 5.1 | API3 |
| SEC-023 | Least-privilege service identities: each deployable has its own cloud role; workers cannot call KMS `Decrypt` for tenants outside their job's tenant (encryption context = tenant + subject) | IaC policy test (`tofu plan` + policy-as-code) | 0.7, 2.3 | V8, V13 |
| SEC-024 | **Four-eyes** by default for: raw export of classified data, model deployment requests, rule changes, key destruction outside a DeletionJob | Workflow test: a single approver cannot complete | 5.4, 6.2 | API6 |
| SEC-025 | Break-glass access: time-boxed (≤ 4 h), reason required, pages the security lead, fully audited | Test that break-glass emits an alert event | 2.8 | HIPAA 164.312(a) |
| SEC-026 | Fail closed: any exception in `policy.check`, classification lookup or consent lookup → **deny** with a problem+json that reveals no internals | Fault-injection test | 5.4 | A10:2025 |

## §C. Cryptography and keys

| ID | Requirement | Verify | Step | Ref |
|---|---|---|---|---|
| SEC-030 | Platform endpoints (REST, gRPC, console) accept **TLS 1.3 only**; the edge SDK refuses anything lower. HTTP disabled. Certificate validation is always on (no "insecure" flag in release builds of the SDK) | A TLS scanner run **against our own staging** only: 1.2 handshake fails; SDK test with a bad cert fails | 2.1, 4.2 | V12 |
| SEC-031 | At rest: **AES-256-GCM** envelope encryption. KMS root → tenant KEK → **per-subject DEK** (BLUEPRINT §8.1). Unique 96-bit nonces per key (random or counter; never reused); AAD binds `tenant_id, subject_id, object_key, version` | Unit tests: tampering with AAD or ciphertext → decrypt fails; a nonce-uniqueness property test | 2.3 | V11; GDPR 32(1)(a) |
| SEC-032 | Crypto library: vetted implementations only (Rust `aws-lc-rs`/RustCrypto AEADs, Python `cryptography`); no custom primitives; FIPS-validated modules for PHI tenants where the provider offers them 🔒 | Dependency allow-list; review | 2.3, 4.2 | V11 |
| SEC-033 | Key rotation: KMS keys rotate automatically yearly; tenant KEKs rotate yearly and on demand (re-wrap DEKs, no data rewrite); DEKs are per subject and per object version, and a DEK is re-keyed after 2^32 encryptions or on compromise | Rotation test: data still readable after rotation; the old KEK version is disabled after the re-wrap job | 2.3 | V11 |
| SEC-034 | Crypto-shredding: destroying a subject's wrapped DEK makes every object copy unreadable immediately. **Database backups that still hold the wrapped DEK row stay a risk until the DB backup retention window expires.** The deletion certificate therefore states "unrecoverable in all copies after <date = shred + DB backup window>"; restores re-apply all shreds before serving (SEC-124); no long-retention DB snapshots contain `subject_key` (M2-REVIEW F3) | 2.3 crypto-shred test (objects + backup object copy); restore-drill test with a shredded subject | 2.3, 5.5 | GDPR Art. 17 support |
| SEC-034a | A shredded subject is **tombstoned**. Any later encrypt for that subject MUST fail (no new DEK is ever minted), open streams for that subject are aborted, and the refusal is audited (M2-REVIEW F1) | Test: shred → encrypt raises `SubjectKeyUnavailable`; shred during an open stream → the next chunk is refused and no new `subject_key` row appears | 2.3, 2.7, 5.5 | GDPR Art. 17 |
| SEC-035 | Hashing: SHA-256 for content addressing (0.5 spec); HMAC-SHA-256 for webhooks; Ed25519 or ECDSA P-256 via KMS for provenance batch, audit anchor and deletion-certificate signatures | Test vectors | 0.5, 3.1 | V11 |
| SEC-036 | Passwords/secrets never in URLs; no sensitive data in query strings (signal windows use IDs, not subject names) | Log-scan test | 2.4 | V14 |
| SEC-037 | Edge write-ahead buffer (SDK) is **encrypted at rest** on the lab PC with a key from the OS keystore, and deleted after server ACK | Test: the WAL file on disk is ciphertext; after ACK it is removed | 2.7, 4.2 | GDPR 32; T-10 |
| SEC-038 | **Crypto-agility / post-quantum readiness:** every envelope header records `alg`, `kek_id`, `kek_version`; algorithm choice is config-driven; an inventory of crypto uses (CBOM, a CycloneDX extension) is maintained. Hybrid ML-KEM (FIPS 203) TLS key exchange is enabled at the edge termination once the provider supports it (roadmap; provider support not verified) | Header-format test; `docs/security/crypto-inventory.md` exists and is reviewed each milestone | 2.3 | FIPS 203 |

## §D. Integrity of neural data, provenance and messages

| ID | Requirement | Verify | Step | Ref |
|---|---|---|---|---|
| SEC-040 | **Stream chunk authentication:** each chunk carries `(stream_id, seq, t_first, t_last, sha256)` **and an Ed25519 signature (or HMAC with a per-stream key derived at `openStream`) made by the device key**. A plain hash detects corruption but not forgery, so a hash is not enough | Server rejects a chunk with a valid hash but a bad signature; replaying a `(stream_id, seq)` is idempotent and a conflicting duplicate is rejected and alerted | 2.7, 4.2 | T-01 |
| SEC-041 | Server-side stream sanity checks: sample-rate consistency, monotonic timestamps, channel count, and physical-range checks per modality; violations mark the segment `suspect` (never silently dropped) and raise an event | Synthetic tests: a timestamp jump, a spliced replay, an impossible amplitude → `suspect` | 2.7 | T-02 |
| SEC-042 | File uploads: client and server SHA-256 must match (BUILD-GUIDE 2.6); the raw original is kept immutable (object lock or versioning) so every derivative can be re-derived | 2.6 test | 2.6 | A08:2025 |
| SEC-043 | Provenance and audit batches are hash-chained and signed (KMS key); chain heads are anchored daily to the WORM bucket; a verification job runs hourly and alerts on mismatch | 3.1/2.8 tamper tests; alert test | 2.8, 3.1, 5.3 | A08:2025 |
| SEC-044 | Published PipelineVersions and ModelVersions are immutable and digest-addressed; images are pulled by `@sha256` only; the worker verifies the cosign signature of every step image before running it | Unsigned image → run refused | 3.2, 3.3 | SLSA; T-20 |
| SEC-045 | Webhooks are signed (HMAC-SHA-256 over timestamp + body); the timestamp tolerance is 5 min; secrets rotate with overlap | 4.6 test | 4.6 | V4 |
| SEC-046 | Deletion certificates are signed (KMS) and verifiable offline with a published public key; the certificate never includes subject identifiers beyond the tenant pseudonym | Verification sample passes; a PII scan of the certificate | 5.5 | T-31 |

## §E. Secrets and configuration

| ID | Requirement | Verify | Step | Ref |
|---|---|---|---|---|
| SEC-050 | Secrets live only in the cloud secrets manager / KMS; injected at runtime; never in images, IaC state, env files in the repo, or logs | 0.7 "no secrets in state" test; image scan for secrets | 0.7 | V13 |
| SEC-051 | CI → cloud via **OIDC federation** (no static cloud keys in CI) | IaC review; no `AWS_SECRET_ACCESS_KEY` in CI settings 🔒 | 0.7 | SLSA L3 |
| SEC-052 | Secrets rotate at least yearly and immediately on staff change or suspected exposure; the rotation runbook is tested | Runbook drill record | 5.7 | CSF PR |
| SEC-070 | All infrastructure through OpenTofu; no console click-ops in prod; drift detection nightly | Drift job alerts on a manual change in staging | 0.7 | CSF ID/PR |
| SEC-071 | Environments: `dev`/`staging` contain **only synthetic or licence-checked public data**; a guard refuses real-subject uploads (a tenant flag `synthetic_only`) outside prod | Upload into staging without the synthetic marker → refused | 2.6 | BLUEPRINT §7 |
| SEC-072 | Network: private subnets for DB/workers; no public DB endpoint; egress through a proxy with an allow-list | IaC policy test | 0.7 | V13 |
| SEC-073 | Containers: non-root, read-only root FS, no privileged mode, seccomp default; minimal base images; image scan gate (critical/high) | Policy test on the task definition; scan in CI | 2.1, 3.3 | A02:2025 |
| SEC-074 | Pipeline worker sandbox: steps run with **no network by default** (the ingest/archive fetch jobs are explicit exceptions), CPU/memory/time limits, and only their job's inputs mounted | Step that tries an outbound connection → fails | 3.3 | T-21 |
| SEC-075 | Resource limits: per-tenant quotas; gateway rate limits; `readWindow` max span/channels per request; upload max size; sweep max N; gRPC max message size and max concurrent streams per device | 4.8 quota tests; a load test on staging only | 4.8 | API4 |
| SEC-076 | SSRF: webhook URLs and archive fetches resolve through the egress proxy; block RFC 1918, link-local, metadata IPs (169.254.169.254) and DNS rebinding | Unit tests with each blocked target | 4.6 | API7 |
| SEC-077 | No undocumented routes: the OpenAPI diff check + route enumeration fails on any route that is not in the spec | 4.1 CI check | 4.1 | API9 |
| SEC-078 | Outbound integrations (IdP, KMS, archives) validate TLS, schema-validate responses, and time out | Contract tests with malformed fixtures | 2.2, 2.5 | API10 |
| SEC-079 | Errors: RFC 9457 problem+json without stack traces, SQL or internal hostnames; debug endpoints absent in prod builds | Test with a forced exception | 4.1 | V16 |

## §F. Input handling, parsers and fuzzing

| ID | Requirement | Verify | Step | Ref |
|---|---|---|---|---|
| SEC-060 | All file parsing (EDF/BDF/BIDS/NWB/XDF) runs in the **worker sandbox**, never in the API process, with size and time limits | Architecture test (import-linter: `api` cannot import converter modules) | 2.5 | V5 |
| SEC-061 | HDF5/NWB/pickle safety: **no `pickle`/`np.load(allow_pickle=True)`/`torch.load` without `weights_only=True`** anywhere; model weights accepted only as safetensors/ONNX | A lint rule (Ruff/Semgrep) bans the calls | 2.5, 6.1 | A08:2025; T-22 |
| SEC-062 | Continuous fuzzing of every converter entry point and of nf-core parsers (cargo-fuzz / Atheris) with a corpus seeded from `tools/synth`; crashes block release | CI fuzz job (short) + nightly (long); 2.5 corrupt-file test | 2.5, 4.2 | V5; IEC 81001-5-1 verification |
| SEC-063 | SQL only through parameterised queries / the ORM; no string-built SQL (Semgrep rule) | SAST gate | 2.1 | A05:2025 |
| SEC-064 | Zip/archive handling: path-traversal and zip-bomb limits on BIDS zip uploads | Fixture tests | 2.6 | V5 |

## §G. Stimulation exclusion and closed-loop integrity (BCI-specific, non-negotiable)

These requirements keep the blueprint's scope boundary: **the platform, API and SDKs never control stimulation or any actuator.** Any change here needs the owner's written approval **and** a new regulatory analysis, not just an ADR.

| ID | Requirement | Verify | Step | Ref |
|---|---|---|---|---|
| SEC-090 | The public API, gRPC protos and SDKs MUST NOT contain any operation, message or field that sends commands, parameters, waveforms or triggers **to acquisition or stimulation hardware**. Data flows device → SDK → platform only | A CI test scans `proto/` and `openapi/`, **and the external surface of `services/`** (the OpenAPI generated from the app, the gRPC servicer names, outbound schemas; see M2-REVIEW), against a denylist of names/semantics (`stim*`, `pulse*`, `amplitude_set`, `trigger_out`, `command`, `actuat*`, `write_register`…) and fails; architecture review at each milestone | 2.7, 4.1 | T-40 |
| SEC-091 | The nf-core LSL bridge is **inlet-only**. It MUST NOT create LSL outlets except in test fixtures under `tests/`, and MUST NOT open serial/USB/HID/Bluetooth handles to devices | A grep/AST test for `StreamOutlet`/`lsl_create_outlet` and serial/USB/HID/Bluetooth crates or Python packages outside `tests/`, over `core/`, `bindings/`, `sdk/` **and `services/`**; a crate feature list is reviewed | 4.4 | T-40 |
| SEC-092 | Model-registry deployment tokens MUST refuse `deployment_context ∈ {closed_loop_stimulation, neuromodulation_control, actuator_control}`, and the terms of service prohibit such use. The registry records `intended_use` and the SOUP export states "not intended for real-time or safety-critical control" | 6.2 test: a deployment with a stimulation context → refused + audited | 6.2 | T-41 |
| SEC-093 | Cloud streaming is **never in the real-time loop**: the SDK docs and the API contract state that acknowledgements carry no timing guarantee; the SDK exposes no API that blocks acquisition on a server round-trip | Doc test + an SDK test where the server stalls for 5 s and local acquisition/WAL continues without sample loss | 2.7, 4.2 | T-42 |
| SEC-094 | Timing provenance: every stored segment keeps the LSL clock-offset series and the local monotonic-clock samples; the platform never rewrites original timestamps (corrections are new derived artefacts with provenance) | 4.4 test; a derived-timestamp lineage test | 2.7, 4.4 | T-43 |

## §H. Privacy engineering for neural data and models

| ID | Requirement | Verify | Step | Ref |
|---|---|---|---|---|
| SEC-140 | Pseudonymisation by default: the platform stores subject pseudonyms; any direct identifier (name, DOB, MRN) is rejected by metadata validators unless the tenant enables an "identified" mode with a separate encrypted table and extra authz | Validator test with an identifier fixture (BIDS `participants.tsv` with a name column → flagged) | 2.5 | GDPR 25, 32; P-01 |
| SEC-141 | **Header scrubbing:** EDF/BDF patient/recording fields, BIDS sidecars and NWB `subject` fields are parsed, identifiers are moved to the governed table, and the stored canonical copy has them blanked; the raw original stays encrypted under the subject DEK | Round-trip test: the exported file has no identifier from the fixture | 2.5 | P-02 |
| SEC-142 | Neural signals themselves are treated as **identifying** (EEG is studied as a biometric; `THREAT-MODEL.md` P-03). Export of raw or minimally processed signals is a classified action (SEC-024), even when pseudonymised | Policy matrix test | 5.4 | P-03 |
| SEC-143 | Model release hygiene: models trained on tenant data are private to the tenant by default; cross-tenant sharing or publication requires a model card with a **privacy-risk section** (membership-inference test result on a held-out split, method recorded) and four-eyes approval | Registry test: publish without the privacy section → refused | 6.1 | P-05 |
| SEC-144 | Inference APIs (if offered) return labels or coarse scores, not full logits/embeddings, by default; per-principal query-rate limits reduce model-extraction and inversion attacks | API test | 6.2 | P-06 |
| SEC-145 | Adversarial robustness: models accepted into the registry for decoding declare their evaluation on perturbed inputs (noise, channel dropout and a documented adversarial method), and the model card records the result. **We do not claim robustness**; we record measurements | Registry schema requires the field | 6.1 | T-44 |
| SEC-146 | Consent scope `model_training` is required for any training job (5.4) and `commercial_use` for any registry publication | 5.4 matrix test | 5.4 | P-07 |
| SEC-147 | Logs and traces never contain signal samples, subject IDs, free-text notes or tokens; log fields are allow-listed (BLUEPRINT §8.1) | Log-scan test in CI on the full e2e suite output | 2.1 | V16 |

## §I. Logging, monitoring, detection

| ID | Requirement | Verify | Step | Ref |
|---|---|---|---|---|
| SEC-100 | Audit events for authentication, every data read/export, admin action, consent change, key operation and deletion; written to Postgres and WORM, hash-chained (2.8) | 2.8 route-enumeration test | 2.8 | V16; HIPAA 164.312(b) |
| SEC-101 | Audit retention ≥ 6 years for BAA tenants (the HIPAA documentation-retention period, **UNVERIFIED here**, legal to confirm), default 3 years otherwise, configurable per tenant within legal limits | Object-lock policy test | 2.8 | — |
| SEC-102 | Alert rules (minimum set): mass export; cross-tenant access denial spikes; break-glass use; a new admin; a KMS key deletion scheduled; audit-chain mismatch; a stream signature failure; a device token used from a new ASN; a CI signing identity used outside CI | Each rule has a synthetic trigger test in staging | 2.8, 4.8 | CSF DE |
| SEC-103 | Time sync: all services use provider NTP; audit events use UTC with monotonic sequence numbers | Config test | 2.1 | V16 |
| SEC-104 | Security logs are reviewed weekly (lightweight) with a signed-off record; the tooling is roadmap | Review log | 5.7 | CSF DE |
| SEC-105 | Customer-visible audit export (auditor role) with a verification tool for the hash chain | Tool verifies an exported chain; a modified export fails | 2.8 | — |
| SEC-106 | Transparency-log monitoring: an alert if our cosign identity appears in Rekor for an artefact our release job did not produce | Scheduled job with a test entry | 4.3 | Sigstore guidance |

## §J. Testing cadence and assurance

| ID | Requirement | Verify | Step | Ref |
|---|---|---|---|---|
| SEC-110 | **External penetration test** before the first real customer data enters prod, then **yearly and after major architecture changes**. Scope: API, gRPC ingest, console, SDK network client, IaC review. Website (static) in scope once. Retest of fixed highs 🔒 (owner spend) | Report + retest letter on file | before M2 prod | GDPR 32(1)(d); FDA |
| SEC-111 | SAST (Semgrep/CodeQL), SCA (SEC-084/085), container scan, IaC scan (checkov/tfsec-equivalent), secret scan on every PR | CI required checks | 0.3 | SSDF PW.7 |
| SEC-112 | ASVS 5.0 L2 (+L3 chapters per `STANDARDS-MAP.md` §1.1) self-verification checklist at each milestone exit | Checklist committed | each milestone | ASVS |
| SEC-113 | Threat-model review at each milestone exit and for every SEC-002 ADR | Updated `THREAT-MODEL.md` with a date | each milestone | FDA; IEC 81001-5-1 |
| SEC-114 | Quarterly access review (people, keys, service roles) | Signed record | 5.7 | HIPAA admin safeguards |
| SEC-115 | Tabletop incident exercise twice a year (one scenario must be a neural-data breach with GDPR + CRA clocks) | Exercise notes | 5.7 | `INCIDENT-RESPONSE.md` |

## §K. Backups, recovery, continuity

| ID | Requirement | Verify | Step | Ref |
|---|---|---|---|---|
| SEC-120 | Postgres PITR ≥ 14 days; daily snapshots copied to a second region/account with separate credentials (ransomware isolation) | Restore drill | 0.7 | GDPR 32(1)(c) |
| SEC-121 | Object storage versioning on; WORM on `audit/`; deletion by crypto-shred, not by rewriting backups (SEC-034) | Policy test | 2.3 | — |
| SEC-122 | Targets (ESTIMATE, to validate): **RPO ≤ 15 min** for metadata/ledger, **RPO ≤ 24 h** for derived artefacts (re-derivable), **RTO ≤ 8 h** | **Quarterly restore drill** with a measured RPO/RTO recorded (the number is a measurement, not a claim) | 0.7, 2.3 | CSF RC |
| SEC-123 | KMS key material cannot be deleted without the waiting period + a two-person approval, except inside a DeletionJob, which is itself four-eyes for bulk deletions | IaC policy test | 2.3 | T-30 |
| SEC-124 | A restored backup must never resurrect crypto-shredded subjects: restore procedure re-applies the deletion ledger | Drill includes a withdrawn subject | 5.5 | P-08 |

## §L. Vulnerability disclosure, incidents, releases

| ID | Requirement | Verify | Step | Ref |
|---|---|---|---|---|
| SEC-130 | Publish the disclosure policy (`VULN-DISCLOSURE.md`) at `/security#disclosure` and security.txt (SEC-157) **before** the first public SDK release | Site test | 1.8 | RFC 9116; FDA 524B(b)(1); CRA |
| SEC-131 | Triage SLAs: acknowledge ≤ 3 business days; initial assessment ≤ 10 business days; fix targets by CVSS: critical ≤ 14 days, high ≤ 30, medium ≤ 90 | Advisory log metrics | ongoing | FDA postmarket plan |
| SEC-132 | Security advisories are published with CVE IDs (via a CNA or GitHub advisories 🔒), a VEX update and SBOM diff | Release checklist | ongoing | CRA |
| SEC-133 | CRA Art. 14: after the first EU commercial SDK release, the IR runbook for 24 h early warning / 72 h notification / final report is active and tested (`INCIDENT-RESPONSE.md` §6) | Tabletop record | 4.3 🔒 | CRA Art. 14 |
| SEC-134 | Support period: every SDK release states its end-of-support date (default 5 years for the major version, per the CRA minimum) and the update channel | Release-notes template check | 4.3 | CRA |

---

## Mapping index: BUILD-GUIDE step → SEC IDs

| Step | SEC IDs |
|---|---|
| 0.1 | 002, 080 |
| 0.2 | 080, 081, 082, 088, 089 |
| 0.3 | 001, 083, 084, 085, 086, 087, 111 |
| 0.7 | 023, 050, 051, 070, 072, 120, 122 |
| 1.1 / 1.3 / 1.5 / 1.6 | 150, 150a, 154, 155, 156 |
| 1.8 | 157, 158, 130 |
| 1.10 🔒 | 150–157, 160 |
| 2.1 | 021, 063, 073, 103, 147 |
| 2.2 | 010–014, 020 |
| 2.3 | 031–034, 038, 121, 123 |
| 2.5 / 2.6 | 042, 060–062, 064, 071, 140, 141 |
| 2.7 | 016, 037, 040, 041, 090, 093, 094 |
| 2.8 | 025, 100–102, 105 |
| 3.1–3.3 | 043, 044, 074 |
| 3.8 | 015 |
| 4.1 | 077, 079, 090 |
| 4.2 / 4.3 / 4.4 | 016, 030, 037, 062, 081, 082, 091, 106, 132–134 |
| 4.6 | 045, 076 |
| 4.7 🔒 | 159 |
| 4.8 | 014, 017, 075 |
| 5.1–5.5 | 022, 024, 026, 034, 046, 124, 142, 146 |
| 5.7 🔒 | 012, 052, 104, 114, 115 |
| 6.1–6.2 | 061, 092, 143–145 |
| Pre-prod gate 🔒 | 110 |
