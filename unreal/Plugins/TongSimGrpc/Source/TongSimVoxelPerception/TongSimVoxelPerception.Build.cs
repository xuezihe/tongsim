using UnrealBuildTool;

public class TongSimVoxelPerception : ModuleRules
{
	public TongSimVoxelPerception(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = ModuleRules.PCHUsageMode.UseExplicitOrSharedPCHs;
		bEnableExceptions = true;

		PublicDependencyModuleNames.AddRange(
			new string[]
			{
				"Core",
				"CoreUObject",
				"Engine",
				"TongosGrpc",
				"TongSimProto",
			}
		);

		PrivateDependencyModuleNames.AddRange(
			new string[]
			{
				"TongSimVoxelGrid",
			}
		);
	}
}
