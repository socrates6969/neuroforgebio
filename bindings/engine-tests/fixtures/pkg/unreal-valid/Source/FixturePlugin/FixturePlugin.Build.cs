using UnrealBuildTool;

public class FixturePlugin : ModuleRules
{
	public FixturePlugin(ReadOnlyTargetRules Target) : base(Target)
	{
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine" });
	}
}
