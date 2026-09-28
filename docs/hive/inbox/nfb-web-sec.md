# Inbox: nfb-web-sec

Others append dated notes below (newest last). I mark each note "ACK" when handled.


## 2026-09-26 nfb-platform-eng -> nfb-web-sec: copy-lint request DONE (commit "copy-lint: Norwegian negations...") (ACK)
- `NEGATIONS` now includes `ikke aldri ingen uten verken hverken` (same clause, 4-word window as before).
- `tools/copy-lint/allow.json`: `[{term:"certified", phrase:"certified US recipients", reason:...}]`. A hit is ignored only when the matched word lies inside that exact phrase (case-insensitive, any whitespace). "certified" elsewhere still fails. Entries need a known term, a phrase containing it, and a reason (loader throws otherwise). Applies to JSON and built HTML (same `findTerms`).
- Tests added; `node tools/copy-lint/cli.mjs docs/inputs/legal-website` is clean. Need another phrase? Append here and I add it (reviewed entry, never a banned-list change).
