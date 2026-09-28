// UNVERIFIED IN-EDITOR: written against the UE 5.x UnrealBuildTool API but never run by UBT (Unreal is
// not installed on the development PC). See ../../README.md "Verification status".
using System.IO;
using UnrealBuildTool;

public class NeuroForge : ModuleRules
{
	public NeuroForge(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		CppStandard = CppStandardVersion.Cpp17;

		// neuroforge.hpp reports failures with C++ exceptions (neuroforge::Error). The plugin catches
		// every one of them inside the module; none crosses into engine code.
		bEnableExceptions = true;

		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "Projects" });

		// ThirdParty/neuroforge is filled by Scripts/stage-sdk.cmd from bindings/c and bindings/cpp.
		string ThirdParty = Path.GetFullPath(Path.Combine(ModuleDirectory, "..", "..", "ThirdParty", "neuroforge"));
		PublicSystemIncludePaths.Add(Path.Combine(ThirdParty, "include"));

		if (Target.Platform == UnrealTargetPlatform.Win64)
		{
			string LibDir = Path.Combine(ThirdParty, "lib", "Win64");
			string BinDir = Path.Combine(ThirdParty, "bin", "Win64");
			// Import library of neuroforge.dll; the DLL is delay-loaded and loaded explicitly by
			// FNeuroForgeModule::StartupModule from the plugin's Binaries folder.
			PublicAdditionalLibraries.Add(Path.Combine(LibDir, "neuroforge.dll.lib"));
			PublicDelayLoadDLLs.Add("neuroforge.dll");
			// Stage the DLL next to the module binaries in editor and packaged builds.
			RuntimeDependencies.Add("$(BinaryOutputDir)/neuroforge.dll", Path.Combine(BinDir, "neuroforge.dll"));
		}
		else if (Target.Platform == UnrealTargetPlatform.Mac)
		{
			// Placeholder: libneuroforge.dylib (universal) from CI. Not built or tested yet.
			// PublicDelayLoadDLLs.Add(Path.Combine(ThirdParty, "lib", "Mac", "libneuroforge.dylib"));
			// RuntimeDependencies.Add(Path.Combine(ThirdParty, "lib", "Mac", "libneuroforge.dylib"));
		}
		else if (Target.Platform == UnrealTargetPlatform.Linux)
		{
			// Placeholder: libneuroforge.so from CI. Not built or tested yet.
			// PublicAdditionalLibraries.Add(Path.Combine(ThirdParty, "lib", "Linux", "libneuroforge.so"));
			// RuntimeDependencies.Add("$(BinaryOutputDir)/libneuroforge.so", Path.Combine(ThirdParty, "lib", "Linux", "libneuroforge.so"));
		}
	}
}
