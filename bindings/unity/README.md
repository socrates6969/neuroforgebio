# NeuroForge SDK for Unity (`com.neuroforge.sdk`)

Status: **in development: not compiled in the Unity editor, not published** (no package registry, no store listing).
The C# code is written against the NeuroForge C ABI 1.2
(`bindings/c/include/neuroforge.h`). It has **not been compiled or run**: Unity is not installed on the development PC (it
needs the owner's Unity ID), and running the .NET SDK is not allowed there yet. The xUnit test suite in `Tests~/` is written and
ready, but it has **not been run**. See "Verification status" below before relying on anything here.

The SDK reads, replays and verifies NeuroForge data. It has **no device-control or stimulation API** (SEC-090/091).

## What's in it

| Area | Types | Native calls |
|---|---|---|
| Version | `NeuroForgeCore` (`AbiVersion`, `IsCompatible`, `EnsureCompatible`, `Version`, dtype helpers) | `nf_abi_version`, `nf_core_version`, `nf_dtype_*` |
| Errors | `NeuroForgeException` (`Status`, `NativeMessage`, `Detail`), `Status` constants | `nf_last_error`, `nf_last_error_detail`, `nf_status_name` |
| Hashing | `Hashing`: `Canonicalize`, `FormatNumber`, `BlobId`, `BlobIdOfFile`, `PipelineVersionId`, `ChunkId`, `ProvBatchId`, `VerifyProvChain`, `IsValidId`, plus the spec-v2 hashes | hashing spec v1 + v2 |
| Signatures | `Verification`: `VerifyStreamChunk`, `VerifyDeviceToken`, `VerifyProvbSignature`, `VerifyAnchor`, `VerifyCertificate` | `nf_verify_*` |
| Recordings | `Recording.Open(root, id)`, `Read` (physical values, double/float), `ReadStored`, `ReadRaw` (stored bytes), `ReadTimestamps`, channel names/units | `nf_recording_*` (needs ABI 1.1 for `nf_recording_read_f64`) |
| Cache | `ChunkCache.Open`, `TryGet` (hash-verified), `Size` | `nf_chunk_cache_*`, `nf_chunk_*` |
| Provenance | `ProvRecorder.Open`, `Record`, `Head`, `Pending`, `MarkSynced` | `nf_prov_recorder_*` |
| Capture | `DeviceKey`, `Wal.Open` (needs a persistent key: 32 bytes from an OS keystore, or a DPAPI key file), `Wal.OpenEphemeralForTesting` (tests only: unsent data dies with the process), `StreamWriter` (samples to signed chunks in an encrypted WAL) | `nf_device_key_*`, `nf_wal_*`, `nf_stream_writer_*` (ABI 1.2) |
| Replay | `NeuroForge.Replay.ReplayWorker` (background thread, real-time pacing, bounded queue), `SampleBlock` | (uses `Recording`) |
| Unity | `NeuroStream` (MonoBehaviour), `MainThreadDispatcher` (`Post`, `RunAsync`) | none |

Not in this version: the upload **sender** (`nf_sender_*`) and the **API client** (`nf_api_client_*`). Both need C
callback tables, and those callbacks need `[MonoPInvokeCallback]` for IL2CPP, which can't be verified without the editor.
For now, upload a WAL with the Python SDK or a C++ host. When they are wrapped, the ABI 1.2 threading rule applies:
ingest callbacks run on the thread that called `nf_sender_run`, `_state` or `_finish`, and can run concurrently when
state or finish is called while run is active. HTTP and token callbacks can run concurrently from every thread
that shares the client. Every C# callback must therefore be thread-safe and must not touch Unity objects directly.

Recording reads are split into native calls of at most `Recording.MaxStoredBytesPerCall` stored bytes (default
64 MiB). The core refuses a single read over 2^30 stored bytes (ABI 1.2).

## Install (for a customer or the owner)

1. Build the native library from a NeuroForge checkout: `cargo build -p neuroforge-c --release`.
2. In Unity (2021.3 or newer): **Window > Package Manager > + > Add package from disk...** and pick
   `bindings/unity/package.json`.
3. Copy `target/release/neuroforge.dll` into the package's `Plugins/x86_64/` folder. In the Plugin Inspector, tick
   Editor and Standalone, set OS to Windows, and set CPU to x86_64.
4. In **Player Settings > Other Settings**, set *Api Compatibility Level* to **.NET Standard 2.1**. The package's asmdef turns on
   *Allow 'unsafe' code* for its own assembly.
5. Import the **NeuroStream demo** sample from the Package Manager and follow `Samples~/NeuroStreamDemo/README.md`.

```csharp
using NeuroForge;
using NeuroForge.Unity;

NeuroForgeCore.EnsureCompatible();
string id = Hashing.BlobId(System.IO.File.ReadAllBytes(path));      // "blob:sha256:..."
using var rec = Recording.Open(root, "rec-001");
var buf = new float[64 * rec.ChannelCount];
int rows = rec.Read(0, 64, buf);                                      // row-major [rows][channels]

// From a MonoBehaviour: hash a big file off the main thread.
MainThreadDispatcher.RunAsync(() => Hashing.BlobIdOfFile(path), r => Debug.Log(r.Id));
```

`NeuroStream` component: set *Recording Root* (relative paths resolve against StreamingAssets) and *Recording Id*.
Then subscribe to `onSamples` (main thread, one `SampleBlock` per block), or poll `ChannelValue("Cz")` and
`LatestValues`.

WebGL isn't supported, because it has no native plug-ins and no threads. For `StreamWriter.Push<T>` and `Hashing.ChunkId<T>`,
the element type must match the dtype exactly (`short` is int16, `float` is float32, and so on). A same-size but
different type, such as `int` on a float32 writer, is rejected.

macOS and Linux: `Plugins/macOS` and `Plugins/Linux/x86_64` are placeholders. Those libraries are built in CI and are
not tested yet.

## Design rules

The full rules are in [DESIGN.md](DESIGN.md). In short:
- Every opaque handle is a `SafeHandle`, so its `nf_*_free` runs exactly once, whether through `Dispose` or the finalizer.
- Strings cross the boundary as NUL-terminated UTF-8. Embedded NULs and lone surrogates are rejected before the call.
- Every `nf_buf` is freed in a `finally`.
- Errors throw `NeuroForgeException`, with the message read on the failing thread before any other `nf_` call.
- The replay worker is the only thread that reads its recording. Game code sees data only on the main thread.

## Verification status

| Part | Status |
|---|---|
| The C ABI these wrappers call | Verified by nfb-cabi (Rust and MSVC C/C++ tests, `bindings/c`) |
| The same call sequences from C++ (read, replay round trip, pacing, loop, drop policy, leak loops, vectors) | **Verified outside the editor** on the Unreal side (`bindings/unreal/tests`, MSVC) |
| C# P/Invoke layer, wrappers, `ReplayWorker` | **Written, not compiled** (dotnet is not allowed on the dev PC yet) |
| xUnit suite `Tests~/NeuroForge.Tests` (vectors, errors, 100k create/free leak loops, replay round trip, WAL, provenance) | **Written, not run** |
| `NeuroStream`, `MainThreadDispatcher`, sample | **Unverified in-editor** (Unity not installed) |

To run the C# tests on a machine where .NET 8 is allowed, first build the native library and the fixture, then point the tests at them:

```
cargo build -p neuroforge-c --lib --examples
target\debug\examples\make_fixture.exe %TEMP%\nf-fixture
set NF_FIXTURE_DIR=%TEMP%\nf-fixture
dotnet test bindings\unity\Tests~\NeuroForge.Tests
```
