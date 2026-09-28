# Vendored test fixtures (m3-prov, 3.7)

| File | Source | Licence | Fetched |
|---|---|---|---|
| `openlineage-2-0-2.json` | https://openlineage.io/spec/2-0-2/OpenLineage.json (OpenLineage core spec, `$id` identical) | Apache-2.0 (OpenLineage project, https://github.com/OpenLineage/OpenLineage/blob/main/LICENSE) | 2026-09-26 |

Used only by `test_prov_export.py` to validate exported OpenLineage RunEvents offline (no network calls
inside tests). The file is unmodified; its SHA-256 is asserted by the test. To update: download the new
spec version, update the path/hash in the test and this table.
