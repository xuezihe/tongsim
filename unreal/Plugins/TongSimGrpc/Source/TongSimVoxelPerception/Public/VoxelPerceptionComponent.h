#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "VoxelPerceptionComponent.generated.h"

UCLASS(ClassGroup=(TongSim), meta=(BlueprintSpawnableComponent))
class TONGSIMVOXELPERCEPTION_API UVoxelPerceptionComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "VoxelPerception")
	FVector BoxSize = FVector(400.f, 400.f, 400.f);

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "VoxelPerception", meta=(ClampMin=1))
	int32 VoxelHalfNumX = 20;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "VoxelPerception", meta=(ClampMin=1))
	int32 VoxelHalfNumY = 20;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "VoxelPerception", meta=(ClampMin=1))
	int32 VoxelHalfNumZ = 20;
};
