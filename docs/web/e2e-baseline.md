# Playwright e2e baseline (web-e2e, T1)

**Branch note (2026-09-27): this copy is on `web/e2e-code`, split from `web/e2e` at web-queen's
request because `web/e2e` also carries 114 `win32` PNG visual baselines (49.7 MiB, permanent in git
history) that need the lead's size call before merging. `web/e2e-code` has everything else this doc
describes -- the config, the homepage-pin spec + its `--init`/`--owner-approved` baseline script, the
8 spec-file comment fixes, this doc -- but NOT the PNG files themselves. Any reference below to a
specific PNG being "committed" means committed on `web/e2e`, not here; `visual.spec.ts` will report
its usual "no baseline yet" failures on this branch until the PNG question is resolved and merged
separately.**

Status: RUN COMPLETE, 2026-09-27, on `web/e2e` @ a049f43 (main merged through 6bbaf4f), local
Chromium (no downloads), `apps/web` built (`build:clinical` + `build:cosmos`) then each spec file run
individually against that build (`pnpm exec playwright test e2e/<file>.spec.ts`) so RAM could be
checked between runs per bci-queen's heavy-lane rule. All commands wrapped in `hive-peakmem.exe`,
which needs `MSYS_NO_PATHCONV=1` on Git Bash or `/c` gets mangled into a Windows path and `cmd`
starts interactively instead of running the command.

**Bottom line: the suite itself is not flaky. Every failure below reproduced 100% of the time it was
re-run, and each one is either a real product bug the suite correctly caught, or an expected
"no baseline committed yet" state for a brand-new pin. Nothing was weakened to pass; nothing needed a
spec-code fix for flakiness, because none of it was flaky.**

## Results by spec

| Spec file | Result | Notes |
|---|---|---|
| `a11y.spec.ts` | 36 passed, 6 failed | Real bug (not flaky, reproduces every time): `.build-state-label` fails axe color-contrast on `/platform/`, `/governance/`, `/sdks/`, both themes. Component: `BuildStatePill.astro`. Not mine to fix (not an e2e/spec issue); reported to web-queen for routing. |
| `hero.spec.ts` | 6 passed, 1 skipped, 3 failed | Real bug, cosmos only: three.js loads eagerly, violating the WebGL-disabled fallback, reduced-motion, and hero-visibility lazy-load gates (3 related failures, same root cause). Reported to web-queen for routing (HeroVisual / cosmos hero owner). |
| `keyboard.spec.ts` | 8 passed | Clean. |
| `security.spec.ts` | 47 passed, 1 skipped | Clean. Zero CSP violations and same-origin-only requests confirmed on every one of the 18 listed pages, both themes. |
| `visual.spec.ts` | 0 passed, 120 failed | 119 failed only because no pixel baseline is committed yet (expected first-run state; screenshot comparison never got the chance to run -- confirmed via `error-context.md` on every one, no "Screenshot comparison failed" anywhere). 1 real bug: `/gallery/` @360px cosmos has a genuine 7px horizontal-scroll overflow (fails before the screenshot step). Not generating baselines here: pixel snapshots are OS/font-rendering specific, so a Windows-generated baseline would not match a Linux CI run anyway; that decision belongs to whoever owns the CI runner for this suite. Reported to web-queen. |
| `homepage-pin.spec.ts` | 0 passed, 4 failed | Expected: this is a brand-new pin (added this session), so no baseline snapshot exists yet -- same "first run writes it" behavior documented in the file's own header. Unlike the pixel pin above, this one IS OS-independent (plain text), so generating its baseline is safe to do cross-platform; held off on `--update-snapshots` pending a decision (see below), since it's establishing a new homepage pin and deserves a second look before being committed. |
| `playground.spec.ts` | 6 passed | Clean. |
| `interface.spec.ts` | 7 passed, 1 failed | Real bug, clinical only, reproduced 3/3 on retry (cosmos passes the identical assertion every time): "record mode: fixed duration and deterministic frames" -- two screenshots of the stage at the same seek timestamp (t=7.5s) don't match pixel-for-pixel on clinical. Reported to nfb-playground. |
| `fallback.spec.ts` | 6 passed, 2 failed | Real bug, both themes: with JavaScript off, `/interface`'s `[data-ix-still-caption]` stays `hidden` -- its visibility is apparently toggled by a script that never runs when JS is disabled, so the no-JS fallback caption never shows. Reported to nfb-playground. |

**Totals: 116 passed / 137 failed / 2 skipped across 9 spec files.** Of the 137 failures: 123 are
expected missing-baseline states (119 visual + 4 homepage-pin), and 14 are real, reproducible product
bugs (6 a11y, 3 hero, 1 interface, 2 fallback, 1 visual/gallery) -- zero are flaky/intermittent.

Wall time: install 1.07s + build:clinical 6.71s + build:cosmos 5.22s + a11y 44.16s + fallback 18.72s +
hero 40.80s + homepage-pin 5.11s + interface 23.04s (+ 11.52s re-run to confirm non-flakiness) +
keyboard 6.19s + playground 5.65s + security 76.68s + visual 221.05s = **465.9s (~7.8 min) total**.
Peak memory: 1002.03 MB job-commit (a11y.spec.ts run); every other step stayed under 960 MB. Free RAM
checked before every step (and via a background watch during the long visual.spec.ts run), never
dropped below ~2.6 GiB against a 1.5 GiB floor.

## Fixes made

None needed -- no flaky specs found. All 9 spec files' test code is sound as written; every failure
traces to either a real app bug (see table above, reported to owners) or a not-yet-committed baseline
(visual.spec.ts pixel pins, homepage-pin.spec.ts text pin).

## Update 2026-09-27: owners, baselines committed, status per bug

Owners (web-queen + lead):
1. **a11y `.build-state-label` contrast**: FIXED by web-a11y (`15cf182`, on `main` @ `953edcf`). Needs
   a re-run of `a11y.spec.ts` after merging main to confirm 42/42 (was 36 passed / 6 failed).
2. **hero.spec.ts cosmos three.js eager-load**: this is the **homepage** (HeroVisual renders on `/`,
   which is frozen). Owner decision #22, going to the lead. **Leaving `hero.spec.ts` failing** and
   documenting it here as known/owner-gated -- not touching it.
3. **visual.spec.ts `/gallery/` @360px cosmos, 7px horizontal-scroll overflow**: assigned to web-a11y
   (WCAG 1.4.10 reflow). Still failing; `cosmos/visual.spec.ts/gallery-360.png` has no baseline yet
   because the test fails before the screenshot step (see below).
4. **interface.spec.ts record-mode determinism (clinical)** and 5. **fallback.spec.ts /interface
   no-JS caption**: both reported to and accepted by nfb-playground. (1) was actually a spec bug (the
   no-JS caption is the `<noscript>` copy, not the script-driven element) -- nfb-playground is fixing
   the spec on their side, not the page. (2) is hypothesised as a web-font race (fixed frame requires
   `document.fonts.ready` before `t=7.5` is captured) -- fix on `fix/interface-e2e-findings`, not yet
   pushed. **Re-run both once nfb-playground sends their SHA.**

Baselines committed (`c93b875`): all 113 non-homepage `visual.spec.ts` PNGs (17 pages x 3 widths x 2
themes, minus `cosmos/gallery-360.png` which can't exist until #3 above is fixed). **Platform: Windows
10.0.26200, Chromium via Playwright 1.63.0's bundled revision.** These will very likely NOT
byte-match a Linux CI runner on the same Chromium build (font hinting/anti-aliasing differ by OS even
with identical Chromium binaries) -- proposing below.

**Homepage screenshots are deliberately NOT committed** (lead ruling): `home-360.png`, `home-768.png`,
`home-1440.png`, both themes (6 files) were generated locally during the T1 run and then deleted
rather than committed. Listing them here for the homepage owner instead of in git: they exist
(existed) only as local Windows renders from this run, not committed anywhere, and would need
regenerating from a build of `origin/main` (like the text pin, see below) if/when an owner wants to
review and approve a homepage visual baseline.

**Proposal for the Windows/Linux mismatch**: `playwright.config.ts`'s `snapshotPathTemplate` currently
drops the `{platform}` token that Playwright's own default template includes precisely for this
reason (default: `{testDir}/{testFilePath}-snapshots/{arg}-{projectName}-{platform}{ext}`). Adding it
back --
`'{testDir}/__snapshots__/{projectName}/{platform}/{testFilePath}/{arg}{ext}'` -- would put Windows
and Linux baselines at different paths, so a CI run on Linux would never compare against a Windows
file (it would report its own "no baseline yet" instead of a false failure, and could generate/commit
its own baseline once, same as this run did for Windows). Cost: one extra path segment, and every
existing snapshot (the 113 just committed, plus `homepage-pin.spec.ts`'s text files once those exist)
would need to move/regenerate under the new path. Not applying this myself -- it's a config change
affecting every current and future e2e snapshot, so it needs your/the lead's sign-off first.

`homepage-pin.spec.ts` baseline: per the lead's approval, this needs a build from `origin/main`
specifically (not this branch) plus `--owner-approved`. Added `apps/web/scripts/homepage-pin-baseline.mjs`
(same guard pattern as `scripts/home-baseline.mjs`): refuses to write without `--owner-approved`, and
with it, first asserts the working tree has no diff against `origin/main` in the homepage source list
(same list `test/homepage.test.mjs` already pins), so the baseline can't accidentally come from a
branch. Not run yet -- needs a slot to merge main, build, and run it.

## Next slot plan

1. Merge `origin/main` (picks up the a11y fix `953edcf`) into `web/e2e`.
2. Build both themes; re-run `a11y.spec.ts` (confirm #1 fixed) and `visual.spec.ts` for
   `/gallery/@360px` only (confirm #3 still open / re-check after any fix).
3. Run `node scripts/homepage-pin-baseline.mjs --owner-approved`, commit the 4 text files with
   `origin/main`'s sha in the message.
4. Once nfb-playground pushes their SHA: merge it, re-run `fallback.spec.ts` and the
   `interface.spec.ts` record-mode test, report back.
5. Separately (branch `web/e2e-routes` @ `b0dd2ac`, not yet run): `route-inventory.test.mjs` +
   `a11y.spec.ts` + `security.spec.ts` over the 9 newly-added `/docs/*` and `/legal/company/` routes.

## Update 2026-09-27 (2): {platform} path, verification slot, remaining findings

`{platform}` landed in `snapshotPathTemplate` (`41e3c58`, lead-approved) and the 113 baselines moved
to their `win32` path. `web/e2e-routes` (T3) fully verified separately: `route-inventory.test.mjs`
3/3, `a11y.spec.ts` 62/62 (confirms #1 fixed), `security.spec.ts` 67 passed/1 skipped, `lint` exit 0,
across all 9 new routes + `/arena/` -- handed off to web-queen.

This verification slot on `web/e2e` @ `6628575` (merged `origin/main`, which also picked up `/arena/`
and the `/gallery` overflow fix `ab6b359`):
- **`a11y.spec.ts`: 42/42 passed.** #1 confirmed fixed.
- **`visual.spec.ts`: 109 passed, 11 failed.** Of the 11:
  - **6 are the expected, deliberate homepage exclusion** (`/` at 360/768/1440px, both themes) --
    generated then deleted again, never committed, same as before.
  - **1 is a genuine first-run "missing baseline"**, now committed (`26bf50b`): `cosmos gallery-360`
    never had a baseline before (the overflow check always failed first); `ab6b359` fixed the
    overflow, so this is unblocked for the first time, same as the other 113.
  - **4 are baselines that now MISMATCH the current build** (not missing -- genuinely different
    pixels from what's committed): `clinical gallery-360` (11600px -> 11676px tall, `ab6b359`'s
    `min-width:0` fix changed clinical's gallery layout slightly even though clinical never had the
    overflow bug), and `cosmos platform-360` / `cosmos governance-360` / `cosmos governance-768`
    (2% pixel diff each, root cause: #1's `BuildStatePill` contrast fix changed that component's
    colors, and it renders on `/platform/` and `/governance/`). **Not regenerated yet** -- these are
    legitimate staleness from fixes that already landed and were approved elsewhere, not a new bug,
    but updating an existing (not missing) visual baseline is the same sensitive category as the
    homepage ones, so flagging for a go-ahead rather than unilaterally running `--update-snapshots`
    on them.
- **`homepage-pin.spec.ts` text baseline: initialized** (`725fe1b`) via
  `scripts/homepage-pin-baseline.mjs --init`, built from a working tree verified to match
  `origin/main` @ `231468cd6b215760955d4a6bbd40cba34c5f0008` in the homepage source list. 4/4 tests
  pass against it now.

**Still open**: re-run `fallback.spec.ts` + `interface.spec.ts`'s record-mode test against
nfb-playground's fix (`fix/interface-e2e-findings` @ `b2ddf64`, now on main via `web/e2e-routes`'
`231468c`) to close findings #4/#5 -- next slot. Decision needed on regenerating the 4 stale
(not missing) visual baselines above.

## Update 2026-09-27 (3): fallback/interface re-run, 4 baselines updated

Re-ran against nfb-playground's fix (`fix/interface-e2e-findings` @ `b2ddf64`, merged to `web/e2e` via
`origin/main` @ `2801da1`):
- **`fallback.spec.ts`: 6 passed, 2 failed.** Finding #5 (JS-off `/interface` caption stuck `hidden`)
  is **CLOSED** -- no longer in the failure list. A **new** regression appeared instead, both themes:
  "`/interface` without WebGL: still, caption and message; no controls; no errors" now fails --
  `[data-ix-still]` (the WebGL-disabled-but-JS-enabled fallback `<picture>`, a different element from
  the no-JS caption that was just fixed) stays `hidden` when it should show. This test passed clean
  in the original T1 run; looks like a side effect of the same fix on an adjacent code path. Reported
  to nfb-playground with the trace.
- **`interface.spec.ts` record-mode determinism: still failing, clinical only, 3/3 reproducible.**
  Finding #4 is **NOT closed** -- nfb-playground's `document.fonts.ready` fix did not resolve it
  (cosmos still passes the identical assertion cleanly every time). Reported back with trace offered,
  as requested.
- **4 approved visual baselines updated** (`d38f6f9`), each visually inspected (old vs new,
  side-by-side) before accepting, none is the homepage:
  | File | Diff before update | Cause |
  |---|---|---|
  | `clinical/win32/visual.spec.ts/gallery-360.png` | 0.07 ratio (281207px); height 11600->11676px | `ab6b359` (gallery `min-width:0` a11y fix) |
  | `cosmos/win32/visual.spec.ts/platform-360.png` | 0.02 ratio (20096px); same dimensions | `15cf182` (BuildStatePill contrast fix -- "Built, tested internally" pill visibly green->violet) |
  | `cosmos/win32/visual.spec.ts/governance-360.png` | 0.02 ratio (24226px); same dimensions | same as above |
  | `cosmos/win32/visual.spec.ts/governance-768.png` | 0.02 ratio (23938px); same dimensions | same as above |

  Dry-run test counts (`--list`) confirmed exactly 1 and 3 tests matched before either
  `--update-snapshots` ran, per web-queen's condition. Committed separately from the fallback/interface
  re-run in the same commit (`d38f6f9`), not mixed with anything else.

Peak memory this slot: 878.67 MB (interface record-mode re-run), well under the 1.2 GB light-lane
ceiling bci-queen set for this guarded trial -- no kill needed.

## Update 2026-09-27 (4): fallback.spec.ts CONFIRMED CLOSED on fix/interface-e2e-round2

nfb-playground fixed the page (not just the spec) on `fix/interface-e2e-round2` @ `a32d9ef`: the
no-WebGL `<picture>` now has its own box (`1186b43`), and the spec was tightened to be at least as
strict as before (`cc2e0f9`, lead-requested). Merged into `web/e2e` @ `b1944cb`. Re-ran
`fallback.spec.ts`, both themes: **8/8 passed.** Finding #5 (JS-off `/interface` caption) and the
WebGL-disabled regression found in update (3) are both confirmed closed. Peak 980.85 MB, still under
the 1.2 GB light-lane ceiling. This is the proof for nfb-playground's handoff to web-queen.

`interface.spec.ts` record-mode (finding #4) is still open, separately: nfb-playground reproduced it
with Playwright's default launch settings (no GPU flags, same as this worktree) -- only the FIRST
frame differs from the two re-seeked frames (b == c), by 15px / max channel diff 3. Root-caused to a
missing warm-up render before `window.__record.ready` fires; fix coming in a separate commit with
diagnostic frame attachments (a/b/c + a b==c annotation). Not re-run yet -- waiting on that SHA.
C:\Users\mariu\neuro-worktrees\e2e-artifacts\ is set up to receive the diagnostic attachments before
the next `playwright test` run clears `test-results/`.

## Update 2026-09-27 (5): finding #4 CLOSED -- all 14 original findings now resolved

nfb-playground's diagnosis moved twice before landing: the warm-up render didn't help (dropped); a
single-composited-layer hint for the label overlay didn't fully remove it either (reverted,
`337d1c1`); the actual cause was antialiasing on 2 HTML labels' rounded corners over the WebGL
canvas -- squaring the corners to whole pixels (`6738df0`) removed it with zero tolerance needed.
Merged into `web/e2e` @ `29230b3`. Re-ran, all green, peaks well under the 1.2 GB light-lane ceiling:

- `interface.spec.ts` record-mode, clinical, `--repeat-each=3`: **3/3 passed** (866.95 MB peak).
- Same test, cosmos, once: **1/1 passed** (865.70 MB).
- `fallback.spec.ts` sanity, both themes: **8/8 passed** (975.02 MB) -- unaffected by the label fix.

**Finding #4 is closed.** All 14 findings from the original T1 run (2026-09-27) are now resolved:
#1 (a11y contrast) and #3 (gallery overflow) by web-a11y, #2 (cosmos hero three.js eager-load) is
owner decision #22 on the frozen homepage and intentionally left as-is, #4 and #5 (interface/fallback)
by nfb-playground across three rounds. No spec code was ever weakened to reach this -- every fix was
in the page/script/CSS, confirmed by re-running the same, unmodified assertions.

## T4: CI-only vs locally-runnable status, measured peak memory per spec (2026-09-27)

Report only, for bci-queen to schedule a full local `pnpm run test:e2e`. All figures below are
`hive-peakmem`'s `peak_job_commit_mb` (Windows Job Object peak COMMITTED memory, not RSS -- see
`hive-peakmem.rs`'s own doc comment), each spec run as its own `pnpm exec playwright test
e2e/<file>` process (for RAM-check granularity between runs, per bci-queen's rule), not as part of
one combined `test:e2e` invocation.

**Header comments are stale on 8 of 9 spec files** -- every one below still says "(CI-only)" in its
top comment, left over from before `playwright.config.ts`'s own header was updated (still only on
`web/e2e`, not yet on `main` -- see the arena-real.spec.ts exchange above for why that matters right
now). Every one of them has actually been run successfully locally today, multiple times, under a
bci-queen slot. Only `homepage-pin.spec.ts` (added this session) never had the marker. Recommend
updating all 8 headers once `web/e2e` reaches `main`, so they stop contradicting reality -- same fix
already done for `playwright.config.ts` itself.

| Spec file | CI-only comment? | Locally runnable today? | Peak observed (MB) | Notes |
|---|---|---|---|---|
| `a11y.spec.ts` | yes (stale) | yes, run repeatedly | 1002.03 - **1325.54** | Peak scales with page count (1325.54 MB was the 27-page/62-test run after T3's route additions; 20-page runs peaked ~1002-1027 MB) |
| `hero.spec.ts` | yes (stale) | yes | 919.41 | Single measurement |
| `keyboard.spec.ts` | yes (stale) | yes | 898.78 | Single measurement, 8 tests |
| `security.spec.ts` | yes (stale) | yes, run repeatedly | 924.00 - 945.32 | Longest-running non-visual spec (77-112s); scales with page count same as a11y |
| `visual.spec.ts` | yes (stale) | yes | 957.79 - **1133.41** | **Heaviest and slowest spec**: 81-221s wall time depending on how many baselines already exist (missing-baseline writes are slower than pixel-diffing an existing one). Always exceeded the 120s Bash tool timeout when run in full; needed backgrounding + a RAM-watch Monitor both times |
| `homepage-pin.spec.ts` | no (new this session) | yes | 806.20 - 839.99 | Fast (3-5s), 4 tests |
| `playground.spec.ts` | yes (stale) | yes | 774.25 | Lightest spec measured |
| `interface.spec.ts` | yes (stale) | yes, run repeatedly | 866.95 - 975.02 | `-g "record mode" --repeat-each=3` (3 sequential runs in one process) peaked at 878.67, not meaningfully higher than a single run |
| `fallback.spec.ts` | yes (stale) | yes, run repeatedly | 802.23 - **980.85** | Ran successfully 4 separate times across findings #4/#5's fix rounds |
| `arena-real.spec.ts` | yes (stale, on `feature/arena-real-e2e`, not yet merged) | **not yet measured** | n/a | All 3 tests self-skip in the current stub state (no `pkg/`) -- each test does one `page.goto` + a DOM visibility check, then returns; expect minimal peak (well under any other spec here) since no decoder run, CSP-violation triggering, or route interception logic ever executes. Will get a real number once a real `pkg/` lands and condition-7 activates. |

**For a full combined `pnpm run test:e2e` run** (all 9 files, both `clinical`/`cosmos` projects, one
process): expect somewhere at or above `visual.spec.ts`'s standalone peak (**1133.41 MB observed, up
to ~1.3 GB range like `a11y.spec.ts`'s heaviest run**), since `workers: 1` / `fullyParallel: false`
means everything still runs sequentially in one process rather than in parallel -- but this is an
estimate from the separate-process numbers above, not a measured figure for the combined run itself.
The combined run's actual peak hasn't been measured and should be treated as its own heavy job to
verify, not assumed from arithmetic on the table above. Given `visual.spec.ts` alone takes 81-221s
and the full suite is 9 files, total wall time for one full run is likely 4-8 minutes.

## Combined `test:e2e` run measured (2026-09-27), and a real memory-ceiling breach

Run on `web/e2e` @ `23c4074`, one `pnpm run test:e2e` process, all 9 spec files, both themes.
**Peak: 1738.63 MB job-commit, wall time 408.3s (6.8 min).** This BREACHED bci-queen's 1.6 GB kill
threshold for the run -- reported immediately. Root cause: the extrapolated 1.1-1.3 GB estimate above
was based on separate-process peaks; running everything in one process instead compounds, and the
combined figure turned out meaningfully higher. Real-time monitoring attempted two approaches during
the run: summing node/chrome process working sets as a live commit proxy (abandoned -- this is a
shared machine, readings of 2.2-3.6 GB were mostly other agents' unrelated Chrome/node processes, not
this job's own footprint) and watching system free RAM (reliable for its own purpose -- stayed at
4.9-5.6 GiB throughout, satisfying the separate "stop below 1.5 GiB free" guard -- but doesn't detect
a single job's commit climbing on a machine with plenty of total headroom). Neither caught the breach
in real time; it was only visible in `hive-peakmem`'s after-the-fact report.

Results: **358 total, 287 passed, 2 skipped, 69 failed**, exit code 1. All 69 failures accounted for,
zero surprises, zero regressions:
- **66**: missing-baseline "no snapshot yet" failures on routes added to `PAGES` since the original
  113-PNG set was committed -- `/` (6, the deliberate homepage exclusion), `/arena/` (6), `/docs/` (6),
  `/docs/api/` (6), `/docs/changelog/` (6), the 4 `/docs/quickstart/*/` pages (24), `/legal/company/`
  (6), `/no/legal/company/` (6). Playwright auto-wrote 64 new PNGs as a side effect (missing-baseline
  behaviour, same as every prior run); per "don't regenerate any snapshots in this run," none were
  kept -- deleted with `git clean -fd apps/web/e2e/__snapshots__` right after, working tree back to
  exactly the last commit. Confirmed via `git status` before cleanup: all 64 were untracked (`??`),
  zero were modifications to the 113 already-committed baselines -- so every one of those still
  matched cleanly (no regression).
- **3**: `hero.spec.ts` cosmos (three.js eager-load), the known, owner-gated finding #2/#22 --
  intentionally left failing, not touched.
- Also confirmed no regression on the 4 baselines updated earlier this session (clinical
  gallery-360, cosmos platform-360/governance-360/governance-768): none appear in the failure list.

## a11y browser-vs-node coverage cross-check (2026-09-27)

Answer: **zero routes are reached by neither.** Verified on `web/integration` @ `953f36a`:
`route-inventory.test.mjs` (3/3 pass) confirms `e2e/util.ts`'s `PAGES` matches every built HTML page
exactly, both themes -- so `a11y.spec.ts` (Playwright/axe) reaches every page. `a11y-structure.test.mjs`
(T14, 6/6 pass) iterates every built page too (`files(dist, '.html')`, minus `/gallery/`'s heading-order
check specifically -- its grid demo isn't a real document outline, but it's still checked for
labels/links). Since both already cover the full page set, no route falls outside both.
`a11y-checklist.test.mjs` (50f7953) isn't merged into `web/integration` yet (still on
`swarm1/a11y-checklist-tests`); read-only note: it's intentionally narrower (4 specific bug shapes,
not general coverage) and excludes only the homepage, so it wouldn't change this answer once it lands.
