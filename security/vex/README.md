# VEX exceptions (SEC-085)

The CI vulnerability gate (`tools/vuln-gate`) fails on any critical/high (or unknown-severity) finding with a fix
available, and on any CVE in the CISA KEV catalogue. A finding passes only if a VEX document here says we are
`not_affected` (with a justification or impact statement) or that it is `fixed`.

**Format:** one [OpenVEX](https://github.com/openvex/spec) v0.2.0 JSON document per decision, file name
`<package>-<vulnerability>.openvex.json`. Products are package URLs; leave out the version only when the statement
holds for every version we can resolve.

```json
{
  "@context": "https://openvex.dev/ns/v0.2.0",
  "@id": "https://<domain TBD>/vex/<package>-<CVE>",
  "author": "NeuroForge Bio security role",
  "timestamp": "2026-09-26T00:00:00Z",
  "version": 1,
  "statements": [
    {
      "vulnerability": { "name": "CVE-YYYY-NNNNN", "aliases": ["GHSA-xxxx-xxxx-xxxx"] },
      "products": [{ "@id": "pkg:npm/<package>@<version>" }],
      "status": "not_affected",
      "justification": "vulnerable_code_not_in_execute_path",
      "impact_statement": "Why this cannot be reached in our build, with evidence."
    }
  ]
}
```

Allowed `justification` values (OpenVEX): `component_not_present`, `vulnerable_code_not_present`,
`vulnerable_code_not_in_execute_path`, `vulnerable_code_cannot_be_controlled_by_adversary`,
`inline_mitigations_already_exist`.

**Who signs.** Until release signing covers VEX, a VEX document is authenticated by (1) a signed commit
(branch protection, SEC-088) and (2) a required review by the security role (`.github/CODEOWNERS` covers
`security/`). Signing each VEX with cosign keyless (`cosign attest-blob --type openvex`) is planned for the first
SDK release (SEC-132). Every VEX is re-reviewed when the package version changes.
