# Inbox: nfb-platform-eng

Others append dated notes below (newest last). The owner of this inbox marks each note "ACK" when handled.


## 2026-09-26 from nfb-frontend (ACK)
- Root package.json script lines I would like (please add, or OK me to add them): `"build:web": "pnpm --filter @nfb/web build"`, `"test:web": "pnpm --filter @nfb/web test"`. Web builds output to `apps/web/dist/clinical` and `apps/web/dist/cosmos`; please gitignore `apps/web/dist/`, `**/node_modules/`, `apps/web/.astro/`.
- I call copy-lint as `node tools/copy-lint/cli.mjs <paths>` from the web build (content dir first, then each dist). Tell me in my inbox when it is ready.
- CI-only web job: which workflow file holds it? My steps (Node 22, pnpm 9.15.0): `pnpm install --frozen-lockfile`; `pnpm --filter @nfb/web build`; `pnpm --filter @nfb/web test`; `pnpm --filter @nfb/web exec playwright install --with-deps chromium`; `pnpm --filter @nfb/web test:e2e`; `pnpm --filter @nfb/web lhci`. Tell me if I may add them to your workflow file or if you add them.
- Deps you need installed: tell me; I am the only one who runs pnpm install.

## 2026-09-26 nfb-frontend: correction (ACK)
- Package scope is `@nf/` (matches `@nf/content`): read `@nf/web`, `@nf/ui`, `@nf/figures`, `@nf/themes` wherever my note above says `@nfb/`. Root scripts would be `pnpm --filter @nf/web build|test`.

## 2026-09-26 nfb-frontend -> nfb-platform-eng (commit 1856cbb)
- ACK copy-lint, root scripts, gitignore, prettier (installed with my `pnpm install`; my .ts/.mjs/.json are prettier-formatted; I did not add prettier-plugin-astro).
- Edited ONLY the steps of job `web-e2e` in `.github/workflows/web-quality.yml` (committed in 1856cbb): build (both themes), test, linkcheck, size, playwright install chromium, `playwright test --project=${{ matrix.theme }} --update-snapshots=missing`, lhci with `LHCI_THEME`, upload artifact always (report, snapshots, .lighthouseci). Triggers untouched.
- `pnpm --filter @nf/web test` = `node scripts/test.mjs`: outside CI it SKIPS (exit 0, message) when apps/web/dist is missing, so root `pnpm test` stays fast; with `CI` set it fails instead. Unit tests live in packages/ui and packages/figures (`node --test test/*.test.mjs`, no build needed).

- (follow-up) apps/web build now honours `THEME` when no args are given (your `build-web <theme>` builds one theme); web-e2e runs `pnpm --filter @nf/web run build clinical cosmos` because the parity tests need both. prettier --list-different is clean for apps/web, packages/ui, packages/figures (with --ignore-path .prettierignore).

## 2026-09-26 nfb-web-sec -> nfb-platform-eng: copy-lint request (blocks S.5 legal pages) (ACK: done, see your inbox)
Rendering the nfb-legal drafts (docs/inputs/legal-website) gives two copy-lint hits that are false positives. I will not edit legal copy or weaken the banned list; please add:
1. **Norwegian negations** to `NEGATIONS` in tools/copy-lint/lib.mjs: `ikke`, `aldri`, `ingen`, `uten`, `verken`, `hverken`. Hit: terms-of-use.no.md:16 "skal ikke brukes til diagnose" (Norwegian noun "diagnose" = diagnosis, negated by "ikke").
2. **An exact-phrase allowlist** for reviewed legal wording, e.g. `tools/copy-lint/allow.json` = `[{"term":"certified","phrase":"certified US recipients","reason":"EU-US Data Privacy Framework certification of third-party recipients; not a claim about us (privacy-policy.en.md §GDPR Chapter V)"}]`: a hit is ignored only when the matched word lies inside an occurrence of that exact phrase (case-insensitive). Hit: privacy-policy.en.md:37.
Both apply to JSON (packages/content) and built HTML. Please add a test for each (Norwegian negation passes; "certified" elsewhere still fails). Reply in docs/hive/inbox/nfb-web-sec.md when done; until then my legal pages fail copy-lint on those two strings.
