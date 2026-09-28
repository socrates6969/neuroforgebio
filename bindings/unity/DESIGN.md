# Unity SDK design (`com.neuroforge.sdk`)

Status: **in development**. Illustrative API, subject to change. It follows the C ABI in
`bindings/c/include/neuroforge.h`; if the two disagree, the header is correct and this document is out of date.

## Goals

- Unity projects get the same hashing, recording reading and provenance checks as the Python SDK. Every
  result comes from the one Rust core (BLUEPRINT §5), through the C ABI; none of the logic is reimplemented in C#.
- The SDK only reads, streams, replays and verifies data. It has no device-control or stimulation API
  (SEC-090/091, `tools/hw-guard`).
- Native memory must not leak, and no C# code runs on a native thread.

## Layers

```
NeuroStream (MonoBehaviour)          Samples/  - game-facing component, UnityEvents, inspector fields
  └─ NeuroStreamWorker               Runtime/  - background thread + bounded queue + MainThreadDispatcher
      └─ Recording, Hashing, ...     Runtime/  - idiomatic C# API, exceptions, IDisposable
          └─ SafeHandles             Runtime/  - one SafeHandle subclass per opaque nf_* handle
              └─ Native (internal)   Runtime/  - [DllImport("neuroforge")] declarations, 1:1 with the header
```

`Runtime/` has no `UnityEngine` references except `Runtime/Unity/` (the component and the dispatcher).
The engine-free part therefore builds as a plain `netstandard2.1` library, and xUnit on .NET 8 tests it against the real
`neuroforge.dll` without Unity (`Tests~/`; Unity's importer ignores folders that end in `~`).

## Marshalling rules

| C type | C# | Notes |
|---|---|---|
| `const char*` input (UTF-8) | `byte[]`, NUL-terminated, built by `Utf8.Encode` | Unity's Mono default is ANSI, so the SDK never relies on `CharSet` |
| string returned by the library | `IntPtr`, copied with `Utf8.Decode`, then freed with the header's free function | copy and free in a `try/finally` |
| `const uint8_t*, size_t` | `byte*` via `fixed` / `ReadOnlySpan<byte>` | no copy |
| `double* out, size_t` | `double[]` / `Span<double>` via `fixed` | the caller owns the buffer; no native allocation per read |
| opaque `nf_x*` | `NfXHandle : SafeHandleZeroOrMinusOneIsInvalid` | `ReleaseHandle` calls `nf_x_free`; it runs exactly once, even from the finalizer |
| status `int32` | `NfStatus` enum; non-OK status -> `NeuroForgeException(status, message)` | the message comes from the header's last-error call on the same thread, read immediately |

The calling convention is `Cdecl` everywhere. Unity IL2CPP requires `[DllImport("__Internal")]` only on iOS,
which is out of scope for v0.

## Public API (v0)

```csharp
namespace NeuroForge {
  public static class NeuroForgeCore { string Version { get; } }
  public static class Hashing {
    string BlobId(ReadOnlySpan<byte> data);                // "blob:sha256:..." (hashing.md §4)
    string ChunkId(Dtype dtype, ulong[] shape, ReadOnlySpan<byte> data);
    string Canonicalize(string json);                       // NF-CJSON v1
    bool   IsValidId(string id);
    IReadOnlyList<string> VerifyChain(IEnumerable<string> batchJson); // throws on a broken chain
  }
  public sealed class Recording : IDisposable {             // local nf-signal/1 Zarr store
    static Recording Open(string path);
    int ChannelCount; double SampleRate; long SampleCount; IReadOnlyList<string> ChannelNames;
    int Read(long startSample, int sampleCount, Span<double> dest); // interleaved [sample][channel]
  }
  public sealed class NeuroStreamWorker : IDisposable {     // background replay, paced in real time
    NeuroStreamWorker(Recording rec, double speed = 1.0, bool loop = false, int blockSamples = 32);
    void Start(); void Stop();
    bool TryDequeue(out SampleBlock block);                 // call on the main thread
    event Action<Exception> Faulted;                        // raised by the dispatcher on the main thread
  }
  public readonly struct SampleBlock { long FirstSample; double Timestamp; int Channels; double[] Data; }
}
namespace NeuroForge.Unity {
  public sealed class NeuroStream : MonoBehaviour {
    string recordingPath; bool playOnEnable = true; bool loop; float speed = 1;
    UnityEvent<SampleBlock> onSamples;                      // raised in Update on the main thread
    float[] LatestValues { get; }                           // last sample per channel, for game logic
    float ChannelValue(string name);
  }
  public static class MainThreadDispatcher { void Post(Action a); }  // drained in a PlayerLoop hook
}
```

The final function names follow the header; wherever the header offers more (for example provenance), the C#
names follow the Python SDK (`nf.canonical.blob_id` -> `Hashing.BlobId`).

## Threading

- The worker thread calls only `Recording.Read` (the header states whether that is thread-safe; the worker owns
  its `Recording` and no other thread touches it until `Stop()` has joined).
- The queue is a `ConcurrentQueue<SampleBlock>` with a capacity. When it is full the oldest block is dropped and
  `DroppedBlocks` is incremented, so a stalled frame cannot grow memory without limit.
- `NeuroStream.Update` drains at most N blocks per frame and raises `onSamples`. Exceptions on the worker are
  marshalled back to the main thread through `MainThreadDispatcher`.
- `OnDisable`/`OnDestroy` stop and join the worker, then dispose the recording. Domain reload (entering Play
  mode without a reload) is handled because `OnDisable` always runs first.

## Native plug-in layout

```
Plugins/x86_64/neuroforge.dll      Windows x64   (Editor + Standalone, import settings in the .meta)
Plugins/macOS/neuroforge.bundle    placeholder: README only (build in CI, not on the dev PC)
Plugins/Linux/x86_64/libneuroforge.so  placeholder: README only
```

## Tests (without Unity)

`Tests~/NeuroForge.Tests` (xUnit, net8.0) references `Runtime/NeuroForge.Runtime.csproj`
(netstandard2.1) and copies the real `neuroforge.dll` built by `bindings/c`. It covers:
hash vectors from `docs/spec` (the same vectors the Rust core tests), error mapping, 100k create/free loops with
private-bytes checks for leaks, double dispose, use after dispose, and a streaming round trip
(write a recording with the core, replay it with the worker, then compare the samples exactly).

The `MonoBehaviour` layer cannot be run without the Unity editor. It is "unverified in-editor".
On 2026-09-27 the owner had not allowed dotnet to run on the development PC, so the whole C# layer is also
**written, not compiled** until that changes (README "Verification status").

## Out of scope for v0

The sender (`nf_sender_*`) and the API client (`nf_api_client_*`) take C callback tables. Under IL2CPP, those callbacks must be
static methods marked `[MonoPInvokeCallback]`, with a GCHandle for `user`. That can't be verified without the editor,
so these are left for v0.2.

When the sender is wrapped (v0.2), CABI-T2 (nfb-security ruling, ABI 1.2.1) applies:
- `Finish` refuses (`NF_ERR_INVALID_ARG`) while the WAL still holds chunks or while `Run` is active, and it never sends
  FinishStream in that case. The doc text states that it only closes the stream on the server and does NOT upload.
- Only one `Run` may be active per sender.
- A `DrainAndFinish()` convenience does what the C++ `Sender::drain_and_finish(t, writer, wal, timeout_s)` does:
  1. flush the writer;
  2. reset the sender;
  3. run it on a background thread until `Wal.Count == 0` (or timeout, or fatal);
  4. stop and join;
  5. if chunks are left, throw `NF_ERR_TRANSPORT` and leave the stream open; otherwise finish.
- There is no "abandon" API. Deleting the WAL directory is the only way to drop unsent chunks.
