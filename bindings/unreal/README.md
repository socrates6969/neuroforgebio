# NeuroForge SDK for Unreal Engine 5 (`NeuroForge` plugin)

Status: **in development: not compiled in the Unreal editor, not published** (no Marketplace/Fab listing).
The plugin's engine-free C++ core is compiled and tested with MSVC against the real NeuroForge
library. The Unreal module code (component, Blueprint library, Build.cs) is **written but never compiled by
Unreal**: Unreal is not installed on the development PC, because it needs the owner's Epic account. See "Verification
status".

The plugin replays and verifies NeuroForge data. It has **no device-control or stimulation API** (SEC-090/091).

## What's in it

| Part | What |
|---|---|
| `UNeuroForgeStreamComponent` | Replays a recording in scaled real time. Properties: `RecordingRoot`, `RecordingId`, `bLoop`, `PlaybackSpeed`, `bAutoStart`, `BlockSamples`, `MaxBlocksPerTick`. `BlueprintCallable`: `StartStream`, `StopStream`. `BlueprintPure`: `IsStreaming`, `GetLatestValues`, `GetChannelValue`, `GetChannelNames`, `GetSampleRate`, `GetCurrentSample`, `GetDroppedBlocks`. `BlueprintAssignable` events: `OnSamples(LatestValues, FirstSample, Rows)`, `OnError(Message)`, `OnCompleted`, all raised on the game thread. |
| `UNeuroForgeBlueprintLibrary` | `CoreVersion`, `IsCoreAvailable`, `BlobIdOfBytes`, `BlobIdOfString`, `BlobIdOfFile`, `CanonicalizeJson`, `IsValidId` |
| `FNeuroForgeModule` | Loads `neuroforge.dll` from the plugin's `Binaries/Win64` and checks the ABI version at startup |
| `NeuroForgeCore/NfReplay.h` | Engine-free C++17: `nf::engine::ReplayWorker` (worker thread, real-time pacing without drift across loops, bounded queue with `DropOldest` or `Block`, prompt `stop()`), `read_floats`, `to_float` |
| `NeuroForgeCore/NfStreamState.h` | Engine-free: newest value per channel, current sample, name lookup |
| C++ RAII wrapper | `neuroforge.hpp` from `bindings/cpp` (nfb-cabi). Staged into `ThirdParty/neuroforge/include` |

C++ gameplay code can use the whole `neuroforge.hpp` API directly: recordings, cache, provenance recorder, capture
writer, and verification.

## Setup (for a customer or the owner)

1. Build the native library: `cargo build -p neuroforge-c --release` (in a NeuroForge checkout).
2. Stage it into the plugin: `bindings\unreal\NeuroForge\Scripts\stage-sdk.cmd release`.
   This copies `neuroforge.h`, `neuroforge.hpp`, `neuroforge.dll.lib` and `neuroforge.dll` into
   `ThirdParty/neuroforge/` and `Binaries/Win64/`.
3. Copy the `bindings/unreal/NeuroForge` folder into `<YourProject>/Plugins/NeuroForge`. The project must be a C++
   project. A Blueprint-only project can get one by adding any C++ class once.
4. Regenerate project files, then build the editor target (for example from Visual Studio, or with
   `Engine\Build\BatchFiles\Build.bat <Project>Editor Win64 Development <Project>.uproject`).
5. Put a recording under `<YourProject>/Content/NeuroForge/`, for example `rec-001`. The SDK test fixture works:
   `target\debug\examples\make_fixture.exe <dir>` writes `<dir>\rec-001`.
6. Add a **NeuroForge Stream** component to an actor and set *Recording Id* to `rec-001`. Then bind *On Samples*, or
   call *Get Channel Value* ("Cz") on Tick. For packaged builds, add `Content/NeuroForge` to
   *Project Settings > Packaging > Additional Non-Asset Directories to Copy*.

Win64 only for now. `Build.cs` holds commented placeholders for Mac and Linux, which are not built or tested.

**DLL loading (security).** The module loads `neuroforge.dll` only by absolute path: first the plugin's
`Binaries/Win64`, then the engine's module directory. It never loads by bare name, because that would search the current
directory and PATH (DLL planting). If neither file exists, the plugin reports it through `OnError` and
`IsCoreAvailable() == false`, and no `nf_` function is called. The DLL is intentionally not unloaded at module
shutdown, because a worker thread may still be inside a read.

## Verification status

| Part | How it was checked |
|---|---|
| `NeuroForgeCore/NfReplay.h`, `NfStreamState.h` | **Verified outside the editor**: compiled with MSVC `/W4 /WX /permissive-` against the import library and against the static library (`/MD`). `tests/test_core.cpp` passes, covering exact replay round trip, 4x pacing, loop and stop, drop-oldest bound, option errors, stream state, 100k-iteration leak loops, and blob/canonical-JSON vectors |
| `neuroforge.hpp` usage | Same MSVC build |
| `FNeuroForgeModule`, `UNeuroForgeStreamComponent`, `UNeuroForgeBlueprintLibrary` | **Unverified in-editor**: never compiled by UHT/UBT and never run in Unreal |
| `NeuroForge.Build.cs`, `NeuroForge.uplugin`, `stage-sdk.cmd` | **Unverified**: never run by UBT |

To run the verified part:

```
bindings\unreal\tests\run-msvc.cmd
```

This builds `neuroforge-c` (debug), writes the fixture, then compiles and runs `test_core.exe` twice (DLL and static).
Set `NF_SKIP_CARGO=1` to reuse an existing build.
