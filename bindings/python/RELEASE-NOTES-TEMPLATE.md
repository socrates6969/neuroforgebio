# neuroforge <VERSION> (nf-core <CORE_VERSION>)

<!-- Copy for every SDK release. Every field below is required; `bindings/python/tests/test_release_notes.py`
     checks that the template keeps them. Publishing to PyPI is owner-approved (BUILD-GUIDE 4.3). -->

- **Release date:** <YYYY-MM-DD>
- **End of support:** <YYYY-MM-DD> (default: 5 years after the first release of this major version, SEC-134 / CRA)
- **Update channel:** <where fixes are published, e.g. the package index project page and the changelog at /docs/changelog>
- **Supported Python:** 3.12+ (abi3 wheels for Windows x86-64, macOS universal2, Linux manylinux2014 x86-64)
- **Hashing spec:** v1 (`docs/spec/hashing.md`); stream protocol `neuroforge.ingest.v1`

## Changes

- <added / changed / fixed, one line each, linking the PR>

## Security

- Advisories fixed in this release: <CVE / GHSA IDs, or "none"> (SEC-132: advisories carry CVE IDs, a VEX update and an SBOM diff)
- Signatures: every wheel is signed with Sigstore cosign (keyless, CI identity) and has SLSA build provenance
  (SEC-081, SEC-082). Verify before installing:
  `cosign verify-blob --bundle <wheel>.sigstore.json --certificate-identity <workflow identity> --certificate-oidc-issuer https://token.actions.githubusercontent.com <wheel>`
  and `gh attestation verify <wheel> --repo <owner>/<repo>`.
- EU incident reporting (CRA Art. 14) for commercial releases: see `security/INCIDENT-RESPONSE.md` §6 (SEC-133).

## Compatibility

- Breaking changes: <none, or the migration steps>
- Deprecations: <API, `Deprecation`/`Sunset` dates announced by the server>

## Not in this release

- <designed or planned features that are documented but not built, labelled as such>
