using UnrealBuildTool;

// Regression fixture: the .uplugin module is named "Alpha", but the Build.cs class is named
// "AlphaModule" -- checkUpluginModules() must flag this as a mismatch instead of silently passing
// because a file with the expected name exists.
public class AlphaModule : ModuleRules
{
	public AlphaModule(ReadOnlyTargetRules Target) : base(Target)
	{
	}
}
