# arena-core

Decoder Arena's evaluation engine: ridge / Kalman / GRU-style-reservoir decoders, R² +
bootstrap CI + shuffle-null significance, and a planted-leak control. Pure Rust, no I/O, no
network, no hardware — see `src/lib.rs` for the module map.

Design and current build status (including what's *not* built yet, and why): see
`../../docs/hive/ARENA-DESIGN.md`.

## Data licence (EXC-150-1 condition 5(a), VERIFIED)

Checked directly against the DANDI API on 2026-09-27 (`GET
https://api.dandiarchive.org/api/dandisets/000129/versions/0.241017.1444/`), not just trusted
from the asset's own `dataset.licence` field: `"license": ["spdx:CC-BY-4.0"]`, dataset name
`"MC_RTT: macaque motor cortex spiking activity during self-paced reaching"`, DOI
`10.48324/dandi.000129/0.241017.1444`, author O'Doherty, Joseph (DataCollector, UCSF). Matches
what `tools/playground/nf_playground/dataset.py` already pins (same dandiset/version/sha256,
shared source). Visible on-page attribution, the "we modified this data" statement, and the
licence link are in `apps/web/src/pages/arena/index.astro`.

## Running the tests

```
cargo test --manifest-path Cargo.toml -p arena-core -j 2   # from the repo root
```

Verified 2026-09-27: 6/6 tests pass (native, x86_64-pc-windows-msvc). A wasm32 sanity check
also passes: `cargo check -p arena-core --features wasm --target wasm32-unknown-unknown`.

(`-j 2`: one build at a time on this machine, per `RESOURCE-RULES`/`RUST-POLICY` — ask the
compile-slot owner first. `-p arena-core` keeps the build scoped to this crate, not the
whole workspace.)

## Building the WASM bundle (for `/arena`, CI recipe per nfb-build-queen T3 row 41)

```
cargo build --release --target wasm32-unknown-unknown -p arena-core --features wasm
wasm-bindgen --target web --out-dir apps/web/src/assets/arena/pkg --out-name arena_core \
  target/wasm32-unknown-unknown/release/arena_core.wasm
```

Output goes to `apps/web/src/assets/arena/pkg/` (**not** `apps/web/public/`; superseded
2026-09-27 -- see history below). `apps/web/src/assets/arena/loader.mjs` imports the glue
normally and the `.wasm` via `?url`, passing it to `init({ module_or_path })`, so **Vite
itself** content-hashes both into the built dist's `/_assets/` -- no manual renaming step,
no separate hash-patching of the glue. `astro.config.mjs` aliases the virtual specifier
`virtual:arena-loader` to this file when `apps/web/src/assets/arena/pkg/` exists
(`apps/web/src/lib/arena-pkg.mjs`), or to `loader-stub.mjs` (zero wasm-referencing code)
when it doesn't, so a missing/not-yet-built bundle degrades only `/arena` (rendered
"decoder unavailable"; `src/pages/arena/index.astro`) instead of failing the whole site
build. Expected raw wasm-bindgen output set is exactly 4 files: `arena_core.js`,
`arena_core_bg.wasm`, `arena_core.d.ts`, `arena_core_bg.wasm.d.ts` — no `snippets/` dir
(this crate uses no `inline_js`/JS-module wasm-bindgen attributes). All four filenames are
literal/unhashed at the source level; only Vite's *build output* is hashed.

<details>
<summary>History: this went through two other schemes on 2026-09-27 before landing here</summary>

1. First cut: output to `apps/web/public/arena/pkg/`, loaded via
   `import(/* @vite-ignore */ '/arena/pkg/arena_core.js')` to keep a missing bundle from
   failing the build (`public/` is outside Vite's module graph, so nothing there is ever
   statically resolved).
2. The lead then asked for a CI-side content-hashed filename
   (`arena_core_bg.<hash>.wasm`) in that same `public/` location.
3. nfb-security's review required both the glue and the `.wasm` to be ordinary,
   content-hashed **Vite** assets (no `@vite-ignore`, nothing under `public/arena/`) --
   which is the scheme documented above, and supersedes 1 and 2.

</details>

The Windows/Linux reproducibility note below (from step 1/2's public-artifact approach)
still applies to the *source* build producing `pkg/`, even though the publishing mechanism
changed.

- Toolchain: root `rust-toolchain.toml` (channel 1.95.0). It does **not** list
  `wasm32-unknown-unknown` under `targets` — CI must add the target explicitly (e.g.
  `rustup target add wasm32-unknown-unknown`), not rely on it already being installed.
- `wasm-bindgen` (the crate, pinned `=0.2.129` in this crate's `Cargo.toml`) and
  `wasm-bindgen-cli` (the binary, `cargo install wasm-bindgen-cli --locked --version
  0.2.129`) **must match exactly** — that's why the crate is pinned with `=`, not a range.
- No network beyond ordinary `Cargo.lock`-pinned crate downloads.
- **Byte-for-byte reproducibility across machines is not expected**, and CI's build is the
  one that ships (nfb-build-queen's `ci/arena-wasm-v2`, hash-gated against two independent
  CI builds): `--remap-path-prefix` only rewrites the matching prefix, not the path
  *separator* style of what follows, so a Windows-built `pkg/` (backslash-separated
  embedded paths) and a Linux CI build (forward-slash) are expected to differ even with
  identical flags otherwise. A `pkg/` built on this Windows machine is a local dev artifact
  for exercising the page end-to-end — it is **not committed on `feature/decoder-arena`**
  and must never be assumed to match the CI-gated bytes.
- Output filenames must keep the `.wasm` extension in the built dist (web-headers needs it
  for the `Content-Type: application/wasm` that `instantiateStreaming` requires).
