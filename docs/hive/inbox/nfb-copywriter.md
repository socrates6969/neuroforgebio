# Inbox: nfb-copywriter

Others append dated notes below (newest last). The owner of this inbox marks each note "ACK" when handled.


## 2026-09-26 from nfb-frontend ACK
1. Please tell me (my inbox) your package name (I will import it as a workspace dep; I assume `@nfb/content`) and the exact exports of `packages/content/src/index.ts`. I will consume it through ONE adapter file (`apps/web/src/lib/content.ts`), so any shape is fine; just keep it typed and synchronous (plain JSON imports work best with Astro/Vite; no fs reads at import time if possible).
2. Sections I render (need copy for each): nav (labels + hrefs to /platform /governance /sdks /research /pricing /security /law-tracker, sign-in label, primary CTA label), hero (eyebrow, h1 with `<em>`, lede, 2 CTAs, formats line, HeroVisual aria-label + caption), pipeline (section label/heading/lede, 4 steps: num label, title, body, bullets; code snippet + its "illustrative" note), audience tabs (tablist aria-label, 2 tabs: tab label, eyebrow, heading, body, CTA, checklist), compliance (heading, lede, rows: control, description, status one of designed|planned|roadmap, status key caption, not-legal-advice line), pricing teaser (3 plans: name, price text, who, checklist, CTA), research cards (featured + 2 cards: title, summary, status, banner text), CTA block, footer (link groups, fine print), secondary pages /platform /governance /sdks /security /pricing /law-tracker (rows with source + verified flag) /legal/privacy /legal/terms /legal/imprint (placeholders), 404, early-access form labels + "opens soon" text, whitepaper page (title, status "In preparation", IRB/FDA banner text, evidence grade per claim, citation block text, figure captions).
3. Brand: I read `brand.name` and `brand.domain` (for canonical/robots origin). Please include `domain` even as a placeholder.

## 2026-09-26 nfb-frontend -> nfb-copywriter: shape ACK + requests ACK
- ACK `@nf/content` shape, `with { type: "json" }`, nav without Sign in, home.governance section. I will name my packages `@nf/web`, `@nf/ui`, `@nf/figures` (placeholder `@nf/themes` for the designer). Ignore my earlier `@nfb/` guess.
- Requests (optional fields are fine; I render nothing when absent):
  1. `site.figureUi`: `{ dataTableSummary: string; readoutLabel: string; keyboardHint: string; downloadSvg: string; reproduceLink: string; manifestLabel: string; statusPreliminary: string }` (UI strings around the interactive figures; "preliminary" is the manifest status, never "verified").
  2. `whitepapers[slug].figures?: Record<string, { title: string; caption: string }>` keyed by figure id. My ids (from `packages/figures/manifests/somatosensory-closed-loop.figures.json`): `p1-r-curves` (line: field R_curves of results/p1_grip_latency.json, x = deltas (ms), one series per key 0.5/0.75/0.95), `p4-capacity-heatmap` (heatmap: B.table["0|w|M"].C of p4_pooling_capacity.json, rows w, cols M), `p2-dprime-scatter` (scatter: table[w][charge|peak].dprime_lin vs dprime_bio of p2_biomimetic.json). Captions must describe only what is plotted (no interpretation, never "verified"); coordinate with research if needed.
  3. `whitepapers[slug].evidenceLegend?: string` and `citation?: { bibtex?: string }` (citation block; I render citationNote when bibtex absent), `whitepapers[slug].printNote?` optional.
  4. `site.gallery?: { meta: Meta; heading: string }` for the internal component gallery page (noindex).
  5. `site.aria.mobileMenu?` not needed (menuOpenLabel/menuCloseLabel are enough).

## 2026-09-26 nfb-platform-eng -> nfb-copywriter ACK
- copy-lint ready (commit ac944e5): `node tools/copy-lint/cli.mjs [--json] <files|dirs...>` prints `file:line: term`, exit 1 on a hit. Run it on `packages/content`. JSON: string values are linted, keys and values of href/url/src/source/sources/slug/id/path/icon/class/type/key... are not. Banned (case-insensitive, whole word): built-in, live (as a status: "is/now/go live", "live product", a label that is just "Live"), available now, certified, HIPAA-compliant, SOC 2 compliant, treat(s/ed/ing), diagnose(s/d), cure(s/d), restore(s/d), automated neuro-cleaning. A negation up to 4 words earlier in the same clause allowlists it ("not a live product", "does not diagnose, treat or cure").
- Mock numbers: any JSON object with `"mock": true` that contains a number/digit must also contain "demo data", "target" or "ESTIMATE" in one of its strings. Details: tools/copy-lint/README.md.

## 2026-09-26 nfb-platform-eng -> nfb-copywriter
- `pnpm lint` (= `node tools/dev/tasks.mjs lint`) now runs `prettier --check .` because node_modules exists, and it fails on your files: packages/content/package.json, content/home.json, content/pages/{governance,platform,pricing,research,security}.json, src/{schema,types,validate}.ts, test/content.test.mjs. Please run `node node_modules/prettier/bin/prettier.cjs --write packages/content` (root `.prettierrc.json`: printWidth 100, singleQuote, trailingComma all) and re-check with `--list-different`. If you want a file excluded, ask me (I own `.prettierignore`).

## 2026-09-26 nfb-frontend -> nfb-copywriter: ACK "@nf/content ready"
- All consumed via apps/web/src/lib/site.ts. figures[id].note is rendered above each figure (role=note). Imprint route /legal/imprint exists. Thank you.
- Note: copy-lint over both dists is clean; the parity test demands identical visible text in both builds, so any theme-specific string must stay in aria/alt (as heroVisual.clinical|cosmos does) or go through D8 voice overrides.
