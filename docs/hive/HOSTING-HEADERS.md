# Host security headers: Netlify and Cloudflare Pages

Owner: web-headers (branch `web/headers`). Status: built and unit-tested. Nothing is deployed and no host
account exists. **The owner has not chosen a host yet.** The lead recommends Cloudflare Pages. It is also the
only host that can serve the /arena exception below, so it is the build default.

## What the build emits

`pnpm --filter @nf/web build` writes `dist/<theme>/_headers`. Netlify and Cloudflare Pages both read this
file from the publish directory. It sits next to `_headers.json`, a host-neutral copy for any other host.
Every header value comes from one file, `apps/web/security-headers.mjs` (SEC-150..156, owned by
nfb-build-queen). `apps/web/host-headers.mjs` only decides which URL paths the values go on.

| Build variable | Values | Effect |
|---|---|---|
| `SITE_HOST` | `cloudflare` (default), `netlify` | Picks the path layout of `_headers`. Header values are the same for both hosts, except that a Netlify build fails while a SEC-150 route exception is active. |
| `SITE_STAGE` | `preview` (default), `launch`, `public` | Sets the HSTS level (see below). Launch and public builds fail while `brand.json` still has placeholders. |

Why there are two layouts: both hosts merge every rule that matches a URL, and both join repeated
headers with ", ". Cloudflare Pages also allows **at most 100 rules and 2,000 characters per line**
(developers.cloudflare.com/pages/configuration/headers, read 2026-09-27). The Netlify layout uses one rule
per page and per trailing-slash spelling. A devportal build already has 80 rules, so new pages would push
that layout past Cloudflare's limit. The Cloudflare layout uses splat patterns instead: `/` and `/*/` for
pages, `/*.html` for the 404 page, and one rule per other unhashed file. That gives 9–10 rules today, and
the count does not grow with pages. Netlify documents no rule limit, and its output is byte-for-byte what
the build emitted before `SITE_HOST` existed.

Deploy commands, once a host is chosen (the owner runs these; no agent deploys):

- Netlify: `SITE_HOST=netlify SITE_STAGE=<stage> pnpm --filter @nf/web build`, then publish `apps/web/dist/<theme>`.
- Cloudflare Pages: `SITE_HOST=cloudflare SITE_STAGE=<stage> pnpm --filter @nf/web build`, then publish `apps/web/dist/<theme>`.
  If the rules ever go over 100, the build fails.

## SEC-150 exception list

Source: `apps/web/csp-exceptions.json`, owned by the security role. Each entry needs nfb-security's written approval and an ADR.

| Route | Change | Approved | ADR | Hosts |
|---|---|---|---|---|
| `/arena/` and below | script-src adds `'wasm-unsafe-eval'`, nothing else | nfb-security, conditionally, 2026-09-27 (conditions 1–8 in the ADR) | [0014](../adr/0014-csp-wasm-exception-arena.md) | Cloudflare Pages only (`/arena/*` detaches the baseline CSP). **A `SITE_HOST=netlify` build fails** while the exception is active (nfb-security: KEEP FAIL). |

An exception is **active only when its route is built AND a page under it can reach a `.wasm` file in the build** (`exceptionsInUse()` in `apps/web/scripts/csp-check.mjs`). /arena can ship without its wasm and keeps the baseline CSP until then; a `.wasm` reachable only from other routes never activates it; if detection errors, the build keeps the baseline (strict) and prints why. Every other URL keeps the baseline CSP below, byte for byte.

## The policy (every response)

| Header | Value | Requirement |
|---|---|---|
| Content-Security-Policy | `default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; manifest-src 'self'; worker-src 'self'; media-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'; upgrade-insecure-requests` | No `unsafe-*` and no third-party hosts; framing is denied |
| Strict-Transport-Security | preview `max-age=300`; launch `max-age=86400`; public `max-age=63072000; includeSubDomains; preload` | Staged HSTS |
| X-Content-Type-Options | `nosniff` | |
| Referrer-Policy | `strict-origin-when-cross-origin` | |
| Permissions-Policy | denies camera, microphone, geolocation, usb, serial, hid, bluetooth (and 13 more); `fullscreen=(self)` | The site cannot reach devices |
| X-Frame-Options | `DENY` | Legacy fallback for `frame-ancestors 'none'` |
| Cross-Origin-Opener-Policy / -Embedder-Policy / -Resource-Policy | `same-origin` / `require-corp` / `same-origin` | Compatible, because every asset is same-origin (the CSP enforces this). The e2e test checks `crossOriginIsolated` and cosmos WebGL. |
| Cache-Control | `/_assets/*` immutable for 1 year; everything else `no-cache`; one value per URL | SEC-156 |

Tests: `node --test apps/web/test/host-headers.test.mjs` (new; covers both hosts) and
`apps/web/test/security.test.mjs` (existing; covers the default build). The tests parse the emitted
`_headers` and check the policy above on every built HTML page. They also check the Cloudflare limits and
check that Cache-Control has exactly one value on every URL.

CSP conformance check across all built pages (no browser needed): run
`node apps/web/scripts/csp-check.mjs apps/web/dist/clinical apps/web/dist/cosmos`. The same check runs as
`apps/web/test/csp-static.test.mjs`. It takes every script, stylesheet, image, font, media file, iframe,
object, form action, `<base>`, CSS `url()` and `@import`, and every literal external URL in the JS bundles,
and checks it against the CSP each page is served with, applying the CSP3 fallback rules. For example,
`frame-src` falls back to `default-src 'none'`, so any iframe fails. Runtime-built URLs are left to the
CI-only `e2e/security.spec.ts`.

## Launch prerequisite: a real domain (owner)

Today the site's domain is the reserved placeholder `neuroforge-bio.invalid` (`packages/content/brand.json`,
`domainIsPlaceholder: true`; no domain is registered, per DECISIONS.md GATE B). The built pages use it in their
canonical links, the sitemap, `security.txt` and the structured data. A preview build keeps it. A
`SITE_STAGE=launch` or `SITE_STAGE=public` build **fails** while it remains, in two places:

- `security.txt` placeholders (`assertPublicReady`, SEC-157);
- any built text file (`.html`, `.xml`, `.txt`, `.json`, `.webmanifest`, `_headers`) that still names a `.invalid`
  host (`apps/web/scripts/host-gate.mjs`). The error lists every `file:line`. JavaScript and CSS bundles are not
  scanned: minified code contains identifiers such as `x.invalid`, which would be false alarms. So a host built into
  a script at runtime is not caught by this gate. Today no script does that.

To launch, the owner registers the domain, sets `domain`, `secondaryHost` and `domainIsPlaceholder: false` in
`brand.json`, and rebuilds. Neither gate can be skipped.

## HSTS preload guidance (owner decision; hard to undo)

- `preload` is only sent when `SITE_STAGE=public`. Submitting the domain at hstspreload.org is a separate
  manual step for the owner. Being on the list makes browsers refuse plain HTTP for the domain **and all its
  subdomains**, and getting removed takes months.
- Before you submit:
  1. Run at least one week at `launch` (max-age 1 day) with no HTTPS problems.
  2. Check that **every** subdomain serves valid HTTPS, including the secondary (cosmos) host and any mail or
     API hosts.
  3. Check that `http://<apex>` redirects to `https://<apex>` on the same host first.
  4. Check that the apex serves the public-stage HSTS header.
- Custom domains: HTTP-to-HTTPS redirects are host settings (Netlify: HTTPS is forced once the certificate is
  provisioned; Cloudflare: "Always Use HTTPS"). Check them with the curl steps below.

## Post-deploy checklist (owner, about 10 minutes)

Replace `$SITE` with the deployed origin, for example `https://example.org`.

1. **Headers on a page:** run `curl -sI $SITE/ | sort` and compare every row with the table above. The
   CSP must match exactly. Repeat for `$SITE/security/` and for one inner page with a trailing slash.
2. **Headers on an asset:** open the page source, copy a `/_assets/...js` URL, then run `curl -sI $SITE/_assets/<file>`.
   It must show `Cache-Control: public, max-age=31536000, immutable` (one value, not merged with
   `no-cache`) and the same security headers.
3. **Headers on the 404 page and security.txt:** `curl -sI $SITE/does-not-exist` returns 404 with the full
   security headers. `curl -sI $SITE/.well-known/security.txt` shows `Content-Type: text/plain; charset=utf-8`.
4. **The URL without a trailing slash:** `curl -sI $SITE/security`. On Cloudflare this is expected to be a
   redirect to `/security/`, and it still carries the security headers from `/*`. On Netlify it serves the page.
5. **No leaks:** `curl -s $SITE/_headers` must not return the file. (`_headers.json` is served, and that is
   fine: it contains only public header values.) Also check that no `Set-Cookie` header appears anywhere.
6. **HTTPS:** `curl -sI http://<domain>/` returns a 301/308 to `https://`. At the public stage, HSTS on the
   apex must include `includeSubDomains; preload`.
7. **Browser:** open DevTools on `/` and on the cosmos 3D page. The console must show no CSP or COEP errors,
   and `crossOriginIsolated` must print `true`.
8. **Scanners** (optional, both public): securityheaders.com should grade A or A+, and Mozilla HTTP
   Observatory (developer.mozilla.org/en-US/observatory) should report no failed tests. Record the grade and
   date in `docs/security/SEC-COVERAGE.md`.
9. **Previews:** a host's preview URLs (`*.netlify.app`, `*.pages.dev`) run a `preview`-stage build.
   Their HSTS must be `max-age=300`, with no preload.

10. **/arena exception (Cloudflare, once /arena is deployed):**
    - `curl -sI $SITE/arena/` and `curl -sI $SITE/arena/index.html`: exactly ONE `Content-Security-Policy` line. It equals the baseline with
      `'wasm-unsafe-eval'` after `script-src 'self'`. If the header is missing, duplicated, or joined with ", ", the
      detach did not work, so stop and report it.
    - `curl -sI $SITE/` and `curl -sI $SITE/does-not-exist`: the baseline CSP with no `wasm`.
    - `curl -sI $SITE/arena`: a redirect to `/arena/`, carrying the baseline CSP.
    - `curl -sI $SITE/_assets/<the .wasm file>`: `Content-Type: application/wasm`.
    - In a browser on /arena/: the decoder runs with no CSP errors, and `eval('1')` in the console is refused.

## Known limits

- Neither host applies `_headers` to Functions, Edge Functions or proxied responses. The site uses none
  today. If one is added, it must set these headers in code.
- `apps/web/scripts/serve.mjs` (the local e2e server) models both layouts the way the host docs describe:
  splats and Cloudflare's `! Header` detach. It also serves `.wasm` as `application/wasm`. It is a model
  of the hosts, not the hosts themselves. Steps 1–4 and 10 above confirm the real behaviour after a deploy.
- These tests check what the build emits, not what a host actually sends. Only the checklist above
  confirms the live headers.
