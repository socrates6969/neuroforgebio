# Architecture decision records

| ADR | Title | Status |
|---|---|---|
| [0001](0001-positioning.md) | Positioning: reproducible, comparable pipelines and neural-data governance | Accepted |
| [0002](0002-company-name.md) | Company name via a single brand token | Accepted |
| [0003](0003-theme-selection.md) | Build-time theme per deployment; clinical canonical | Accepted |
| [0004](0004-hosting-cloud.md) | Hosting: static CDN for the website, AWS for the platform | Accepted |
| [0005](0005-build-order.md) | Consent ledger (M5) runs in parallel after M2 and step 3.1 | Accepted |
| [0006](0006-licensing.md) | Licensing: Apache-2.0 for SDK/core later, proprietary platform | Accepted |
| [0007](0007-core-language.md) | Rust for the shared SDK core | Accepted |
| [0008](0008-headline-wording.md) | One heading set for both themes | Accepted |
| [0009](0009-third-party-requests.md) | Self-hosted fonts, no trackers, no third-party scripts | Accepted |
| [0010](0010-external-assurance.md) | Order of external assurance spend | Accepted |
| [0011](0011-ai-layer-principles.md) | AI layer: evaluated, versioned, provenance-tracked, consent-gated, human-in-the-loop; no medical claims, no stimulation | Proposed (LLM provider = Anthropic API: Accepted 2026-09-26) |
| [0014](0014-csp-wasm-exception-arena.md) | SEC-150 exception: `'wasm-unsafe-eval'` on /arena only (Cloudflare; Netlify build fails) | Proposed (nfb-security: approved with conditions 2026-09-27) |

New ADRs: copy the shape of an existing one, next free number, status Proposed until the owner accepts.
