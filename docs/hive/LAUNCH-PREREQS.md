# Launch prerequisites: what the owner must supply before a launch or public build

Owner: web-headers. Status: 2026-09-27. **Nothing is deployed and no host is chosen.** Every CI and local build is
`SITE_STAGE=preview` (the default; `SITE_STAGE` is set nowhere in CI). This page lists what changes, and what turns
red, when a build is made with `SITE_STAGE=launch` or `SITE_STAGE=public`.

## Stages

| Stage | Meaning | Set by |
|---|---|---|
| `preview` (default) | Not for the public: noindex everywhere, short HSTS, placeholders allowed | nothing to do |
| `launch` | First public week: indexable, HSTS 1 day, **no placeholders** | owner, at deploy time |
| `public` | Steady state: HSTS 2 years with `includeSubDomains; preload`, **no placeholders** | owner, after the launch week |

## Gates that turn a launch/public build red

| # | Gate (where) | Fails when | Owner must supply |
|---|---|---|---|
| 1 | `security.txt` placeholders: `assertPublicReady` in `apps/web/scripts/security-txt.mjs` (SEC-157) | `packages/content/brand.json` has `domainIsPlaceholder: true`, or `security.txt` still has `.invalid`, `<domain TBD>` or `TBD` | A registered domain in `brand.json` (`domain`, `secondaryHost`, `domainIsPlaceholder: false`), and a real, monitored mailbox `security@<domain>`. The build cannot check that the mailbox exists, so the owner does. |
| 2 | Host gate: `assertNoPlaceholderHost` in `apps/web/scripts/host-gate.mjs` (postbuild step 5). Merged to web/integration, not yet on main. | Any built `.html`, `.xml`, `.txt`, `.json`, `.webmanifest` or `_headers` file still names a `*.invalid` host (canonical links, sitemap, robots.txt, structured data). The error lists every `file:line`. | The same domain as gate 1. A rebuild after setting it removes every hit, because all URLs come from `brand.json`. JS/CSS bundles are not scanned (minified code has identifiers like `x.invalid`), and no bundle contains the host today. |

These two are the only stage-dependent failures. Everything else a build checks (inline code SEC-150a, the CSP
self-check, the SEC-150 exception gate, the Cloudflare rule limit) fails the same way at every stage.

## What changes without failing

| Item (where) | preview | launch | public | Owner decision |
|---|---|---|---|---|
| HSTS: `hsts()` in `security-headers.mjs` (SEC-151) | `max-age=300` | `max-age=86400` | `max-age=63072000; includeSubDomains; preload` | When to move from launch to public. Submitting the domain to hstspreload.org is a separate, hard-to-undo owner step (see `HOSTING-HEADERS.md`, "HSTS preload guidance"). Every subdomain must serve HTTPS first. |
| `X-Robots-Tag: noindex, nofollow`: `globalHeaders()` (APP-L8) | on every response | removed | removed | None for the header itself. Pages that must stay out of search results at launch need Base's `noindex` prop, which renders a robots meta tag. Today these are the gallery, the 404 page, draft legal pages (EN and NO), Norwegian pages not yet reviewed, the `/arena` stub while its WebAssembly is absent, and the `/investors` draft (web-queen: it stays noindex until the owner publishes it). |
| `robots.txt`: `indexing.mjs` | `Disallow: /` | `Allow: /` (except `/gallery/`) + `Sitemap:` on the canonical host | same as launch | Which host is canonical (clinical theme = `domain`, cosmos = `secondaryHost`). |

Not stage-related, but it blocks a host: with the `/arena` WebAssembly exception active, a `SITE_HOST=netlify`
build fails (nfb-security, KEEP FAIL). The owner's host choice (P7) decides this; Cloudflare Pages is the build default.

## How to test locally (needs a bci-queen slot, like every build)

1. Set the domain in `packages/content/brand.json` (on a scratch branch, not committed, until the owner decides).
2. Run `SITE_STAGE=launch pnpm --filter @nf/web build`, or `SITE_STAGE=public ...`.
3. Expected results:
   - **With the placeholder domain:** step 1 fails with `security.txt: SITE_STAGE=launch but placeholders remain`.
   - **With a real domain but a leftover `.invalid` URL somewhere:** step 5 fails with
     `host gate: SITE_STAGE=launch but the placeholder host remains in N place(s)` and lists the files.
   - **With a real domain everywhere:** the build passes. Then check:
     - `dist/clinical/_headers` has `Strict-Transport-Security: max-age=86400` and no `X-Robots-Tag`;
     - `dist/clinical/robots.txt` has `Allow: /` and a `Sitemap:` line;
     - `dist/clinical/.well-known/security.txt` names `security@<domain>`.
4. The unit tests exercise both gates without a real domain: `apps/web/test/security.test.mjs` (SEC-157) and
   `apps/web/test/host-gate.test.mjs` (preview passes, a leftover placeholder fails, a real host everywhere passes).

After a real deploy, run the checklist in `docs/hive/HOSTING-HEADERS.md` ("Post-deploy checklist") against the live site.
