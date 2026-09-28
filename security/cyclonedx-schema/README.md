# Vendored CycloneDX 1.6 JSON schemas (offline SBOM validation)

Used by `tools/sbom-validate/validate.py` (EXC-150-1 condition 4, SEC-083) to validate SBOMs without network access.
The lead approved the fetch on 2026-09-27; it was logged with hive-slot (lane "light", 0.3 MB).

| File | Source (fixed release tag, not a branch) | SHA-256 |
|---|---|---|
| `bom-1.6.schema.json` | https://raw.githubusercontent.com/CycloneDX/specification/1.6.2/schema/bom-1.6.schema.json | `18f57f7482593bad9f21b4feed09084640cbeff419d62ad5090c5ceccca5b37d` |
| `spdx.schema.json` | https://raw.githubusercontent.com/CycloneDX/specification/1.6.2/schema/spdx.schema.json | `c41917196639055e9f9670811bac23ef777732144f3ff5a2f39686f61580dbe6` |
| `jsf-0.82.schema.json` | https://raw.githubusercontent.com/CycloneDX/specification/1.6.2/schema/jsf-0.82.schema.json | `8bae002c25e723db7ee1f26afde680ae1a2b1a8f6b4b4b0fd65dc3becb090aae` |
| `LICENSE` | https://raw.githubusercontent.com/CycloneDX/specification/1.6.2/LICENSE | `6c29f22a4a7385285c6f579ec9f33c5e989f00739d6b257243a0b082ec9447ae` |

- **Tag** `1.6.2` = commit `e833d732337dd33aceb45ff1991f896796f1e5e7` (`git ls-remote --tags https://github.com/CycloneDX/specification`).
- **Licence:** Apache-2.0 (the `LICENSE` file above). The repository has no `NOTICE` file at this tag; the fetch of
  `NOTICE` returned 404. The files are unmodified.
- **Offline check (lead condition 3):**
  - The files are plain JSON Schema (draft-07), with no scripts.
  - The only non-local `$ref`s are relative: `spdx.schema.json` and `jsf-0.82.schema.json#/definitions/signature`,
    in `bom-1.6.schema.json`. They resolve against the `$id` base `http://cyclonedx.org/schema/` to exactly the
    `$id`s of the two other vendored files.
  - The validator preloads all three into a `referencing` Registry with no retrieve function, so an unresolved
    `$ref` raises an error instead of being fetched. A test refuses any socket use during validation.
- **Integrity:** `SHA256SUMS` in this folder is checked by the validator before every use; a changed file is refused.
- **Updating:** a new tag needs the lead's OK for the fetch. Record the tag, URLs and hashes here, and update `SHA256SUMS`.
