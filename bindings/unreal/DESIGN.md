# Unreal SDK design (`NeuroForge` UE5 plugin)

Status: **in development**. Illustrative API, subject to change. It follows the C ABI in
`bindings/c/include/neuroforge.h` and the C++ wrapper `bindings/cpp/neuroforge.hpp`; if they disagree with this
document, they are correct.

## Goals

- Blueprints and C++ gameplay code can replay or stream NeuroForge recordings and verify content IDs, using the
  one Rust core (BLUEPRINT §5) through the C ABI.
- The plugin only reads, streams and verifies data. It has no device-control or stimulation API (SEC-090/091).
- The UE-specific code is kept thin, and all logic lives in engine-free C++17, so it can be compiled and tested
  with plain MSVC (Unreal is not installed on the dev PC).

## Layout

```
bindings/unreal/NeuroForge/
  NeuroForge.uplugin
  Source/NeuroForge/
    NeuroForge.Build.cs                      links neuroforge.dll.lib, stages neuroforge.dll (RuntimeDependencies)
    Public/NeuroForgeCore/NfReplay.h         ENGINE-FREE: replay worker (std::thread, bounded queue) on neuroforge.hpp
    Public/NeuroForgeModule.h                IModuleInterface: loads the DLL from the plugin's Binaries dir
    Public/NeuroForgeStreamComponent.h       UActorComponent + BlueprintAssignable event
    Public/NeuroForgeBlueprintLibrary.h      static BlueprintCallable helpers (hashing, version)
    Private/*.cpp
  ThirdParty/neuroforge/{include,lib/Win64,bin/Win64}   filled by the setup script (copied from bindings/c)
  tests/                                      MSVC-only tests for NeuroForgeCore (not shipped)
```

## API (v0)

```cpp
// Engine-free (namespace nf::engine)
class ReplayWorker {                       // owns an nf::Recording from neuroforge.hpp
 public:
  ReplayWorker(nf::Recording rec, double speed, bool loop, std::size_t block_samples, std::size_t max_queued);
  void start(); void stop();               // stop() joins; the destructor calls stop()
  bool try_pop(SampleBlock& out);          // any thread; the game thread in UE
  std::optional<std::string> error() const;
  std::uint64_t dropped_blocks() const;
};

// UE
UCLASS(ClassGroup=(NeuroForge), meta=(BlueprintSpawnableComponent))
class UNeuroForgeStreamComponent : public UActorComponent {
  UPROPERTY(EditAnywhere, BlueprintReadWrite) FString RecordingPath;
  UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bLoop = false;
  UPROPERTY(EditAnywhere, BlueprintReadWrite) float PlaybackSpeed = 1.f;
  UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bAutoStart = true;
  UPROPERTY(BlueprintAssignable) FNeuroForgeSamplesEvent OnSamples;   // (const TArray<float>& Latest, int64 FirstSample)
  UPROPERTY(BlueprintAssignable) FNeuroForgeErrorEvent  OnError;      // (const FString& Message)
  UFUNCTION(BlueprintCallable) bool StartStream();
  UFUNCTION(BlueprintCallable) void StopStream();
  UFUNCTION(BlueprintPure) TArray<float> GetLatestValues() const;
  UFUNCTION(BlueprintPure) float GetChannelValue(const FString& Channel) const;
  UFUNCTION(BlueprintPure) TArray<FString> GetChannelNames() const;
  UFUNCTION(BlueprintPure) float GetSampleRate() const;
};
UCLASS() class UNeuroForgeBlueprintLibrary : public UBlueprintFunctionLibrary {
  UFUNCTION(BlueprintPure)     static FString CoreVersion();
  UFUNCTION(BlueprintCallable) static FString BlobIdOfBytes(const TArray<uint8>& Data);
  UFUNCTION(BlueprintCallable) static FString BlobIdOfString(const FString& Utf8Text);
  UFUNCTION(BlueprintPure)     static bool IsValidId(const FString& Id);
};
```

## Threading

The worker thread only reads the recording. `TickComponent` (game thread) drains the queue up to a per-tick
limit and broadcasts `OnSamples`. As a result, Blueprint handlers always run on the game thread, and no `AsyncTask`
lambdas outlive the component. `EndPlay` and `BeginDestroy` stop and join the worker.

## Linking

The Windows build uses the C ABI's import library and delay-loads `neuroforge.dll`
(`PublicDelayLoadDLLs`). `FNeuroForgeModule::StartupModule` loads it from `Binaries/ThirdParty/neuroforge/Win64`
with `FPlatformProcess::GetDllHandle` before first use. `RuntimeDependencies` stages the DLL into packaged builds.
Mac and Linux are placeholders in `Build.cs`, documented but not built.

## Verification status

| Part | How it is checked on this PC |
|---|---|
| `NeuroForgeCore/*` (replay worker, conversions) | compiled with MSVC `/W4 /WX` against the real lib, and unit tests run |
| `neuroforge.hpp` usage | same MSVC build |
| UE module, component, Blueprint library | **unverified in-editor**: written, not compiled (a stub of UHT's generated code would give false confidence, so none is used) |
| `Build.cs`, `.uplugin` | reviewed only; not run by UBT |
