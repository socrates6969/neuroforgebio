# ADR 0014: SEC-150 exception, `'wasm-unsafe-eval'` on /arena only

- Status: **Proposed** (the owner accepts ADRs). nfb-security approved it with conditions on 2026-09-27. This ADR narrows ADR 0009's
  `script-src 'self'` for one route.
- Date: 2026-09-27
- Deciders: nfb-security (SEC-150 owner). Plan approved by web-queen. Implemented by web-headers on `web/headers`.
- Source: `docs/hive/T3-ARENA-WASM-PLAN.md`, `apps/web/csp-exceptions.json`, nfb-security's approval message (conditions 1–8, below).

## Context

The Decoder Arena (/arena, nfb-arena, `feature/decoder-arena`) runs a Rust decoder that is compiled to WebAssembly with
wasm-bindgen `--target web`. The module is compiled on the page's main thread through `WebAssembly.instantiateStreaming`, and the
.wasm file is same-origin. There is no Worker. Browsers block compiling WebAssembly unless script-src allows `'wasm-unsafe-eval'`.
That token allows compiling WebAssembly only. It does not allow JS `eval`/`Function`. SEC-150 banned the token on every route.

## Decision

`'wasm-unsafe-eval'` is added to script-src **only** for URL paths under `/arena/`. The only source for this is
`apps/web/csp-exceptions.json`, which is owned by the security role. `csp({ route })` adds the token only for a listed route.
`assertCspSafe(value, { route })` still rejects it, and every `'unsafe-*'`, everywhere else. Only tokens in
`EXCEPTION_TOKENS` can ever be excepted, and only in script-src.

Hosts: both Netlify and Cloudflare merge every matching `_headers` rule, and browsers enforce every CSP they receive, so /arena must
receive only its own policy.

- **Cloudflare Pages** removes the baseline CSP with the documented `! Content-Security-Policy` detach in a `/arena/*` rule
  and sets the arena policy there. The splat is taken to match `/arena/` itself. If it does not, /arena keeps the stricter
  baseline and wasm fails closed, which the post-deploy checklist catches.
- **Netlify** cannot remove a header. nfb-security ruled **KEEP FAIL**: a `SITE_HOST=netlify` build fails while the exception is
  active, because the only Netlify layout would serve unmatched URLs (404) with no CSP. A later meta-CSP path for Netlify is
  described in the plan and needs its own approval.

## Trigger: when the exception is active (lead requirement, 2026-09-27)

/arena ships first **without** its wasm. pkg/ only comes after an owner-approved CI dispatch (owner list #18). So the
exception is not switched on by the route alone. `exceptionsInUse(dist)` in `apps/web/scripts/csp-check.mjs` decides it
from the built output. The build (`scripts/postbuild.mjs`) passes the result to `host-headers.mjs`, which ignores anything
not listed in `csp-exceptions.json` or whose route is not built.

- **Active** only when a page under `/arena/` is built **and** that page can reach a `.wasm` file in the build. "Reach"
  means one of two things: the page's HTML references the `.wasm`, or a string literal in a script the page loads does.
  Loaded scripts are followed through `<script src>` and relative `.js` imports, transitively, and include wasm-bindgen's
  `new URL('x_bg.wasm', import.meta.url)`, which is resolved against the script.
- **Inactive** (baseline CSP on /arena, and Netlify builds) when /arena has no reachable wasm. A `.wasm` reachable only
  from another route never activates /arena, and neither does an unreferenced `.wasm` file under /arena.
- **Fails strict:** if detection throws, the result is no exception, the baseline CSP everywhere, and a printed reason.
- Canonical layout (lead ruling, 2026-09-27): the glue and the `.wasm` are content-hashed Vite assets in the shared
  `/_assets/`, and nothing is under `/arena/pkg/`. Sharing `/_assets/` does not widen the exception, because the token
  is set per document (only `/arena/` pages), and the glue and `.wasm` responses keep the baseline CSP.
- Layout guard (`arenaLayoutProblems()`, part of `checkCsp()`): any file under `/arena/pkg/`, any `.wasm`, and any
  `arena_core*.js` that is not a content-hashed `/_assets/` file fails the check (nfb-security checklist item 1).
- Separate guard: whatever the trigger decides, `checkCsp()` fails any page that lacks the token but can reach code
  that compiles WebAssembly.

Tests: `apps/web/test/csp-static.test.mjs` covers active with wasm, inactive without wasm, wasm on another route, and a
detection error. `apps/web/test/host-headers.test.mjs` checks the default (inactive) and that only listed exceptions for
built routes are honoured.

## Conditions (nfb-security) and where each is met

| # | Condition | Where |
|---|---|---|
| 1 | Token in script-src on /arena/ and below only; every other route keeps the baseline byte for byte | `host-headers.test.mjs` snapshot of every URL (synthetic and built dist); `security.test.mjs` |
| 2 | No other loosening: no unsafe-eval/unsafe-inline, no blob:/data:/hosts in script-src or worker-src, connect-src 'self', COOP/COEP/CORP unchanged | `assertCspSafe` (route-aware) and its tests; `assertPolicy` in `host-headers.test.mjs` |
| 3 | A Worker must not widen the exception to /_assets/* | Not applicable (main thread only). If a Worker is added later, use option 3(a) or 3(b) and get a new review |
| 4 | .wasm is same-origin, content-hashed, `application/wasm`, built in CI from pinned source with the locked toolchain, and listed in the SBOM | `serve.mjs` sets the MIME type; CI build and SBOM: nfb-build-queen + nfb-arena (open) |
| 5 | Demo or synthetic data only; no platform API | nfb-arena (open) |
| 6 | Data-file allowlist `{route, token, reason, owner, review}` with CODEOWNERS set to the security role | `apps/web/csp-exceptions.json`; the CODEOWNERS line is with web-queen and the lead |
| 7 | Browser tests: arena decodes; `eval('1')` is blocked; the baseline CSP makes the compile fail; other routes unchanged | Playwright: web-e2e (open); the other-routes part is covered by condition 1's tests |
| 8 | ADR plus an entry in the SEC-150 exception list | This ADR; the exception list in `docs/hive/HOSTING-HEADERS.md` |

Guard against wasm creeping onto other routes: `scripts/csp-check.mjs` fails if any page whose CSP lacks the token can
reach a bundle that compiles WebAssembly.

## Consequences

- While /arena exists, the build can only serve it on Cloudflare Pages (or CloudFront with a per-path response-headers policy). This is a technical limit, not a host choice: no host is chosen and nothing is deployed; `SITE_HOST=cloudflare` is only the build default.
  This is input to the owner's host decision (P7 / APP-L9).
- Review the exception at each milestone. Removing the entry from `csp-exceptions.json` restores the baseline everywhere.
- CODEOWNERS points at the owner (`@socrates6969`) until the security-role team exists; then switch it to that team (nfb-security note, 2026-09-27).
- Condition 7 smoke on a Cloudflare preview must assert the arena CSP on both `/arena/` and `/arena/index.html` (the empty-splat assumption).
