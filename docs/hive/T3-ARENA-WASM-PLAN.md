# T3 plan: allow WebAssembly on /arena only (web-headers)

Status: plan only. No code has been written. Waiting for approval from web-queen, and for nfb-build-queen to agree to the change in its file.
Input: nfb-security's exception, APPROVED WITH CONDITIONS 1–8 (2026-09-27 message; the text will be copied into ADR-0014).
Facts from nfb-arena: wasm-bindgen `--target web`, compiled on the main thread only, no Worker, the `.wasm` is
same-origin and next to the glue JS, and /arena is the only route that uses wasm. Branch `feature/decoder-arena`, pkg/ not
committed yet. Condition 3 (Worker) therefore does not apply. If a Worker shows up later, option 3(a) or 3(b) is used, never
`/_assets/*`.

## Blocker: Netlify cannot give one route a looser CSP without dropping the CSP on unmatched URLs

Both hosts apply every matching rule. A second CSP header is joined as "A, B", browsers enforce both, and wasm
stays blocked. So /arena has to be the only rule that carries its CSP.

- **Cloudflare Pages** documents `! Header` (detach). The layout becomes: `/*` keeps today's CSP, and `/arena/` and
  `/arena/*` detach it and set the arena CSP. Every other URL, including unknown URLs that return 404, keeps the
  CSP byte for byte. Not documented: whether a detach and a new value in the *same* rule work together. The
  post-deploy checklist gets a curl check for this, and if it fails, the fallback is a separate rule ordered after the detach.
- **Netlify** documents no way to remove a header. The only option is to take the CSP off `/*` and put it on every
  per-path rule (the Netlify layout already lists every file). Cost: a URL that matches no rule (an unknown URL
  that returns the 404 page) would be served **without a CSP**. The 404 page is static and reflects nothing, so the
  exploit risk is low. But this changes a response nfb-security asked to keep byte for byte, so it needs nfb-security's decision
  (condition 1). The owner should also get this as input to the host choice (P7).

Recommendation: implement both layouts, and have `SITE_HOST=netlify` **fail the build** while the exception list is non-empty,
unless nfb-security accepts the unmatched-404 gap in writing. Cloudflare is clean.

**Decision (nfb-security, 2026-09-27): KEEP FAIL.** A `SITE_HOST=netlify` build fails while the SEC-150 exception list is
non-empty. SEC-150 promises a CSP on every response, and the host is still open (APP-L9 / P7). Until then, the supported hosts for the
exception are Cloudflare Pages and CloudFront (per-path response-headers policy). A later Netlify path that nfb-security would approve,
as a separate change:

- (a) every built HTML page, including 404.html, carries the baseline CSP in a `<meta http-equiv>` tag, and /arena's tag adds
  only the token;
- (b) the `/*` header keeps what meta cannot carry (`frame-ancestors 'none'`, XFO DENY) and the non-CSP headers;
- (c) tests: exactly one meta CSP per page, identical to the baseline except on /arena, and a Netlify preview's unmatched URL
  returns the 404 page with it.

This would reverse the "no meta CSP" test in host-headers.test.mjs, and that is expected.

## Who changes what

| Item | Owner | Notes |
|---|---|---|
| `apps/web/csp-exceptions.json`: `[{route:'/arena/', token:"'wasm-unsafe-eval'", directive:'script-src', reason, owner:'nfb-security', review:'each milestone'}]` | web-headers (new file) | cond. 6 |
| `security-headers.mjs`: `csp({ route })` appends the token only for a listed route; `assertCspSafe(v, { route })` still rejects the token unless (route, token) is listed; everything else unchanged | **nfb-build-queen's file**, needs their OK or they make the edit | cond. 1, 2, 6 |
| `security.test.mjs`: keep the "rejects wasm-unsafe-eval" case (now on `/` and on unlisted routes) and add "allowed on /arena/ only" | nfb-build-queen / web-headers | cond. 6 |
| `host-headers.mjs`: arena rules for both layouts (above); both the `/arena/` and `/arena` spellings | web-headers | |
| Snapshot test: CSP of every built route = baseline, except `/arena/` and `/arena/*`, which equal baseline + exactly one token in script-src; worker-src, connect-src, COOP/COEP/CORP unchanged | web-headers | cond. 1, 2 |
| `csp-check.mjs`: rejects a `WebAssembly.` / `instantiateStreaming` reference in a bundle that is loaded by a route without the token | web-headers | stops wasm creeping into other routes |
| `serve.mjs` (local e2e server): add `.wasm: application/wasm` and splat-aware matching | nfb-build-queen's file | cond. 4, 7 |
| `.github/CODEOWNERS`: `apps/web/csp-exceptions.json @PLACEHOLDER-ORG/security-role` | lead (shared file) | cond. 6 |
| Browser tests: arena decodes with the header; `eval('1')` gets a CSP violation; baseline CSP causes the wasm compile to fail | web-e2e / nfb-arena (Playwright, heavy slot) | cond. 7 |
| wasm built in CI from pinned source + locked toolchain, hashed, SBOM entry | nfb-arena + nfb-build-queen | cond. 4 |
| Demo or synthetic data only, no platform API calls | nfb-arena | cond. 5 |
| ADR-0014 "SEC-150 exception: wasm on /arena" + exception list in HOSTING-HEADERS.md | web-headers | cond. 8 |

Order: web-queen approves → nfb-build-queen agrees (or edits its file) → nfb-security decides on Netlify →
I implement my rows on `web/headers` after `feature/decoder-arena` lands its pkg/ (the tests need the real route) →
send the SHA to nfb-security for read-only verification.
