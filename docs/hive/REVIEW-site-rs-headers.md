# Review: site-rs headers port (`tools/site-rs/src/headers.rs`)

Reviewer: web-headers, read-only, for web-queen. Reviewed: `feature/site-rs` @9740474 (`headers.rs`,
`tests/arena_fixture_parity.rs`), compared with main @6bbaf4f (`apps/web/security-headers.mjs`,
`host-headers.mjs`, `scripts/postbuild.mjs`, `scripts/csp-check.mjs`). I did not build or run anything.

## Matches the JS (verified by reading)

- `Stage`/`Host` resolution. The defaults (`preview`, `cloudflare`) and error texts are the same.
- `hsts()`, `PERMISSIONS_POLICY` (all 21 entries, same order), and the baseline `csp()`, which has the same
  directive order.
- `csp(route)`: the route token is added only by `route.starts_with(e.route)`. The no-slash `/arena` gets
  the baseline, as in JS.
- `csp-exceptions.json` validation: the route shape `^/[a-z0-9-]+/$`, `script-src` only, the
  `EXCEPTION_TOKENS` allowlist, and non-empty `owner`/`adr`. A missing field fails in serde, the same
  effect as JS's falsy check.
- Netlify layout (`header_rules`): the order, both trailing-slash spellings, and the security.txt
  Content-Type.
- Cloudflare layout (`cloudflare_rules`): `/`, `/*/`, `/*.html`, one rule per other unhashed file, and a
  `/<route>*` rule that detaches the CSP and sets the route CSP.
- `checked_active`: only listed exceptions whose route is built. It compares by route+token instead of
  JS's identity check, which has the same effect.
- Netlify KEEP FAIL: triggered by the checked active list, with the exact same message.
- `render_host_headers`, both layouts, including the Cloudflare comment line and the order in which the
  `! Header` detach lines appear.
- `assert_cloudflare_limits`: counts 100 rules and 2,000 characters per line. Lengths are counted in
  bytes instead of UTF-16 units, which is the same for the current ASCII output.
- `_headers.json`: the key order (`generatedBy, stage, host, activeExceptions, note, rules`), `detach`
  only when non-empty, and headers in insertion order.

## Missing or different (what nfb-site-rs should add)

1. **No wasm-reachable trigger (`exceptionsInUse`)**, which is known gap 2. The parity test feeds the JS
   `active.json` into Rust, so the trigger itself is never tested in Rust. This includes route built AND
   `.wasm` reachable, a `.wasm` only on another route never counts, and dist-root confinement.
   **Strict on error:** Rust today can only be strict by the caller passing `&[]`. There is no detection
   that could fail. If the Rust build ever becomes the generator, it must either port `exceptionsInUse`
   with the same fail-strict behaviour (an error means `[]`, with the reason printed), or refuse to build
   while any route in `csp-exceptions.json` is built. It must never default to an active exception.
2. **No `assertCspSafe` port.** JS postbuild asserts the baseline CSP, and each active route's CSP with its
   route, before writing. Rust emits the CSP without the SEC-150 gate. Port it: no `'unsafe-*'` or
   `'wasm-unsafe-eval'` except a listed `(route, script-src, token)`, `'self'`/`'none'`/sha256/`data:` in
   img-src only, the required directives present, and `default-src`/`object-src`/`base-uri`/`frame-ancestors`
   set to `'none'`.
3. **The Cloudflare limit is not enforced by the generator.** JS postbuild calls `assertCloudflareLimits`
   whenever the host is cloudflare. In Rust it is a free function. Make the Rust driver call it, or have
   `render_host_headers(Cloudflare)` return a `Result`.
4. **No `parseHostHeaders` / `hostHeadersForPath`.** These aren't needed to generate, but parity tests
   byte-compare the text and never check the served headers per URL. For example, a detach model where
   `/arena/` must receive exactly one CSP isn't asserted in Rust. Porting the matcher, 30 lines, would allow
   a per-URL snapshot like `host-headers.test.mjs`'s `assertPolicy`.
5. **No `checkCsp` / `arenaLayoutProblems` port.** These are the wasm-compile guard and the "no /arena/pkg,
   no unhashed arena_core*/.wasm" guard, and they are part of SEC-150 enforcement. nfb-build-queen is moving
   them into postbuild as a hard gate. They are out of scope for a headers port, but if Rust replaces
   postbuild, they must come along. Otherwise the gate disappears.
6. **Drift to expect:** `chore/ci-site-hardening` (not on main yet) adds
   `X-Robots-Tag: noindex, nofollow` to `globalHeaders()` on preview builds (APP-L8). The port's
   `global_headers` has no stage-dependent header. Byte parity will break when that lands.
7. **Inline hashes are hardcoded empty.** That's acceptable today, but make it fail loudly: have a parity
   test assert that JS `INLINE_SCRIPT_HASHES`/`INLINE_STYLE_HASHES` are still `[]`, so a new hash can't be
   dropped silently.
8. Minor: `checked_active` should also compare `directive`, to mirror identity fully. And `HeadersJson`
   receives the checked list. JS writes `detect()`'s list unfiltered, which is equivalent while
   `exceptionsInUse` only returns built routes, but worth a comment.

## Verdict

The generation logic (both layouts, detach, KEEP FAIL, limits, JSON shape) is a faithful port. It is
**not yet a drop-in replacement for `postbuild.mjs` step 3**, because the SEC-150 gates (items 1, 2, 3 and
5) exist only on the JS side. Keep JS authoritative until items 1–3 are ported, or until the Rust
driver refuses to build when an excepted route exists. Item 6 is a scheduling note.

## Re-review: `feature/site-rs-headers` @dfccaae (read-only, not run)

Gaps 1–4 and items 7–8 are addressed. nfb-site-rs reports 119/119 tests plus 11 ignored parity tests passing
in bci-queen's slots. I did not re-run them.

- **Gap 1 (`csp_check.rs`):** `dist_file` confinement, the `.wasm` literal and relative/absolute `.js` literal
  regexes, route-prefix page selection, and fail-strict (`Err` → `[]` + `on_error`) all match the JS.
  Remaining differences:
  - **a. `<link rel="modulepreload">` is not followed** (flagged in the file). JS `htmlRefs()` classifies it as
    `script-src`, so JS follows it. That is a parity gap, not a safety gap: a miss means inactive, so the baseline
    is kept. It is about 10 lines to port, because Astro/Vite do emit modulepreload links for page chunks. Recommend
    porting it before Rust is authoritative.
  - **b. Read errors inside `reachable_scripts`/`reachable_wasm` are skipped** (`if let Ok`), while JS throws
    and reports through `onError`. The direction is the same (under-detection, which keeps the baseline), but the
    reason is not reported. Suggest propagating the error so fail-strict also prints why.
  - **c. The parity tests feed the JS `active.json` into Rust.** Suggest also running
    `csp_check::exceptions_in_use()` on the same fixture dist and asserting it equals `active.json`, so the trigger
    is cross-checked on identical input and not only against synthetic Rust dists.
- **Gap 2 (`assert_csp_safe` + `parse_csp`):** matches: lower-cased names, duplicate-directive error, excepted
  `(route, script-src, listed token)` only, `'self'`/`'none'`/sha256/`data:` in img-src only, allowed origins,
  required directives, and the four `'none'` directives.
- **Gap 3:** `render_host_headers_checked` enforces the Cloudflare limits, and both parity tests use it.
- **Gap 4:** `parse_host_headers` (with detach-after-header rejected) and `host_headers_for_path` (with detach
  semantics) match. Minor: JS keeps the last value for a header key repeated within one rule (an object), while
  Rust keeps both. The renderer never emits repeats, so this is only relevant for hand-written input.
- **Wiring:** nothing in the crate yet runs these as a pipeline (detect → `assert_csp_safe` on the baseline and each
  active route → rules → checked render), the way `postbuild.mjs` step 3 does. That is fine while JS stays
  authoritative. When a Rust driver is added, it must call them in that order.

**Updated verdict:** the parity is good. Before Rust can be authoritative: (a) the modulepreload entry point,
(c) a trigger cross-check on the fixture, and the pipeline wiring above. (b) is a nice-to-have. Gap 5 is out of scope,
per the lead.
