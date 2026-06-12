#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"

#include <tongsim_lite_protobuf/voxel.pb.h>

#include "VoxelPerceptionSubsystem.generated.h"

namespace tongos
{
	class ResponseStatus;
}

class UTSGrpcSubsystem;

UCLASS()
class TONGSIMVOXELPERCEPTION_API UVoxelPerceptionSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	void HandlePostWorldInit(UWorld* World, const UWorld::InitializationValues IVS);

	static tongos::ResponseStatus QueryAgentVoxel(
		tongsim_lite::voxel::QueryAgentVoxelRequest& Request,
		tongsim_lite::voxel::QueryAgentVoxelResponse& Response);

private:
	static UVoxelPerceptionSubsystem* Instance;

	UTSGrpcSubsystem* ResolveGrpcSubsystem() const;
};
