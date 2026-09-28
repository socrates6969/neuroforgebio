# WEB-STATUS

Queen-maintained status and task queue for the website hive. Workers: report in WEB-BOARD.md; web-queen updates this file.
Handoff checklist (WEB-PLAN rule 6): both theme builds pass; `node --test apps/web/test/*.test.mjs` passes; `node tools/dev/tasks.mjs lint --skip=rust`
clean; content tests pass; homepage diff empty; exact counts in the handoff. Heavy jobs need a bci-queen slot.

## Active tasks
| Worker | Branch / worktree | Task | State |
|---|---|---|---|
| nfb-playground | new branch from web/integration | T2: reduced-motion + keyboard pass on /playground, /interface | sent |
| nfb-arena | feature/decoder-arena (neuro-worktrees/arena) | T1: /arena builds in both themes with wasm artifacts + arena.test.mjs; no nav link | sent |
| nfb-site-rs | feature/site-rs (neuro-worktrees/site-rs) | T1: Stage 2 parity test: robots.txt + sitemap.xml byte-identical to dist of both themes | sent |
| nfb-video | neuro-media | T1 DONE (stills-manifest.json); now video renders (own queue) | busy |
| nfb-build-queen | chore/ci-site-hardening | T1 DONE b3277ec; T2: drafts.test.mjs (draft pages noindex, not in sitemap/nav) | sent |
| web-copy | web/copy | T1: platform.json + sdks.json mark M2-M6, M4 API/SDK, C ABI as built, with evidence tags | sent |
| web-a11y | web/a11y | T1: WCAG 2.2 AA audit of inner pages -> docs/web/a11y-audit.md, fix top 5 in components | sent |
| web-perf | web/perf | T1: tools/web/perf-audit.mjs (no deps) + per-page budgets + test | sent |
| web-seo | web/seo | T1: metadata audit of built inner pages -> docs/web/seo-audit.md; fill missing descriptions | sent |
| web-headers | web/headers | T1: apps/web/public/_headers generated from the build CSP + parity test; security.txt | sent |
| web-e2e | web/e2e | T1: run existing Playwright specs on installed Chromium (slot), fix flakes, report | sent |
| web-papers | web/papers | T1: PAPERS-REVIEW.md claims audit, then draft pages under /papers/draft (noindex); owns content schema | acked |
| web-investor | web/investor | T1: INVESTOR-PAGE-SOURCES.md then /investors draft (noindex); schema after web-papers | acked |
| web-docs | web/docs | T1: /docs/python-sdk page generated from bindings/python + test | sent |

## Next-task queue (hand out when someone is idle)
0. RULE: every branch merges origin/main before handoff; no rebases onto unmerged branches (lead).
1. web-e2e: specs for /playground and /interface (after merge #1) and /arena (after merge #2).
2. web-seo: JSON-LD (Organization, SoftwareApplication, TechArticle) on inner pages via page-level slots only.
3. web-a11y: reduced-motion and keyboard review of /playground, /interface, /arena.
4. web-perf: image budget for playground/interface stills; propose AVIF/WebP pipeline (no new deps without lead).
5. web-docs: /docs/c-abi page from the C ABI headers; then Unity/Unreal SDK pages (status "designed" until compiled).
6. web-headers: CSP violation report test across all built pages; host variants (Netlify + Cloudflare).
7. web-copy: Norwegian (no) parity for every inner-page change.
8. nfb-site-rs: Stage 3: one inner page (security) byte-identical.
9. web-papers: render drafts as noindex pages behind a draft flag (needs schema slot).
10. web-investor: /investors draft page (noindex) + data-room index (needs schema slot).
11. nfb-video: poster frames for /arena after its page lands.

## Merged into web/integration
- web/headers 68ec96d + feature/playground-a11y bdc927e: queen re-check 91/90/0/1, content 25/25, lint ok.
- feature/neural-playground @ 60384cb (via lead into main 6a79900; synced 2106118). Worker report: 77 tests / 76 pass / 0 fail / 1 skip; content 25/25; both themes PASS. Queen re-check DONE: identical counts, homepage test passes on built dist.
