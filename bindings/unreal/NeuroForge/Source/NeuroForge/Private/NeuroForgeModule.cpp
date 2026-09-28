// UNVERIFIED IN-EDITOR (never compiled by UBT). See README.md "Verification status".
#include "NeuroForgeModule.h"

#include "HAL/PlatformProcess.h"
#include "Interfaces/IPluginManager.h"
#include "Misc/Paths.h"
#include "NeuroForgeLog.h"

THIRD_PARTY_INCLUDES_START
#include "NeuroForgeCore/NfAbi.h"
THIRD_PARTY_INCLUDES_END

DEFINE_LOG_CATEGORY(LogNeuroForge);

namespace
{
	bool GAvailable = false;
	FString GLoadError = TEXT("module not started");
}

void FNeuroForgeModule::StartupModule()
{
#if PLATFORM_WINDOWS
	// Load ONLY by absolute path, never by bare name: a bare-name load searches the current
	// directory and PATH, which would let a planted neuroforge.dll run inside the game.
	// 1. <Plugin>/Binaries/Win64 (editor builds), 2. the module directory (packaged builds; Build.cs
	// stages the DLL there with RuntimeDependencies). Once loaded, the delay-load stub resolves
	// "neuroforge.dll" to this already-loaded module; no nf_ function is called if loading failed.
	TArray<FString> Candidates;
	TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("NeuroForge"));
	if (Plugin.IsValid())
	{
		Candidates.Add(FPaths::ConvertRelativePathToFull(FPaths::Combine(Plugin->GetBaseDir(), TEXT("Binaries/Win64/neuroforge.dll"))));
	}
	Candidates.Add(FPaths::ConvertRelativePathToFull(FPaths::Combine(FPlatformProcess::GetModulesDirectory(), TEXT("neuroforge.dll"))));
	for (const FString& Dll : Candidates)
	{
		if (FPaths::FileExists(Dll))
		{
			DllHandle = FPlatformProcess::GetDllHandle(*Dll);
			if (DllHandle)
			{
				break;
			}
		}
	}
	if (!DllHandle)
	{
		GLoadError = FString::Printf(TEXT("neuroforge.dll not found in %s (run Scripts/stage-sdk.cmd and rebuild the plugin)"),
			*FString::Join(Candidates, TEXT(" or ")));
		UE_LOG(LogNeuroForge, Error, TEXT("%s"), *GLoadError);
		return;
	}
#else
	GLoadError = TEXT("NeuroForge plugin: only Win64 is supported in this version");
	UE_LOG(LogNeuroForge, Error, TEXT("%s"), *GLoadError);
	return;
#endif
	// Only now is it safe to call into the delay-loaded library.
	const uint32 V = nf_abi_version();
	const uint32 Major = V >> 16, Minor = (V >> 8) & 0xff;
	if (!nf::engine::abi_compatible(V))
	{
		GLoadError = FString::Printf(TEXT("neuroforge ABI %u.%u is not compatible with this plugin (needs %d.%d+)"),
			Major, Minor, NF_ABI_VERSION_MAJOR, NF_ABI_VERSION_MINOR);
		UE_LOG(LogNeuroForge, Error, TEXT("%s"), *GLoadError);
		return;
	}
	GAvailable = true;
	GLoadError.Reset();
	UE_LOG(LogNeuroForge, Log, TEXT("NeuroForge core %s (ABI %u.%u)"), UTF8_TO_TCHAR(nf_core_version()), Major, Minor);
}

void FNeuroForgeModule::ShutdownModule()
{
	GAvailable = false;
	// Deliberately NOT FreeDllHandle: a stream component's worker thread may still be inside an nf_
	// call (for example nf_recording_read_f64) while modules shut down, and unmapping the DLL under
	// it would crash. The OS releases the library at process exit.
	DllHandle = nullptr;
}

bool FNeuroForgeModule::IsAvailable()
{
	return GAvailable;
}

const FString& FNeuroForgeModule::GetLoadError()
{
	return GLoadError;
}

IMPLEMENT_MODULE(FNeuroForgeModule, NeuroForge)
