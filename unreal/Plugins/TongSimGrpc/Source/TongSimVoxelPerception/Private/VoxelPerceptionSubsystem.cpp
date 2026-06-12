#include "VoxelPerceptionSubsystem.h"

#include "TSGrpcSubsystem.h"
#include "TSVoxelGridFuncLib.h"
#include "VoxelPerceptionComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "grpcpp/support/status.h"
#include "rpc_common.h"

using namespace tongos;

namespace
{
constexpr const char* kVoxelServicePrefix = "/tongsim_lite.voxel.VoxelService/";

bool BytesLEToGuid(const std::string& Bytes, FGuid& OutGuid)
{
	if (Bytes.size() != 16)
	{
		return false;
	}

	auto ReadLE32 = [](const uint8* Data) -> uint32
	{
		return static_cast<uint32>(Data[0])
			| (static_cast<uint32>(Data[1]) << 8)
			| (static_cast<uint32>(Data[2]) << 16)
			| (static_cast<uint32>(Data[3]) << 24);
	};

	const uint8* Data = reinterpret_cast<const uint8*>(Bytes.data());
	OutGuid = FGuid(
		static_cast<int32>(ReadLE32(Data + 0)),
		static_cast<int32>(ReadLE32(Data + 4)),
		static_cast<int32>(ReadLE32(Data + 8)),
		static_cast<int32>(ReadLE32(Data + 12)));
	return OutGuid.IsValid();
}

UWorld* GetGameWorld()
{
	if (!GEngine)
	{
		return nullptr;
	}

	for (const FWorldContext& Context : GEngine->GetWorldContexts())
	{
		if (Context.WorldType == EWorldType::Game || Context.WorldType == EWorldType::PIE)
		{
			return Context.World();
		}
	}
	return nullptr;
}

tongsim_lite::common::Vector3f ToProtoVector3f(const FVector& Vector)
{
	tongsim_lite::common::Vector3f Out;
	Out.set_x(static_cast<float>(Vector.X));
	Out.set_y(static_cast<float>(Vector.Y));
	Out.set_z(static_cast<float>(Vector.Z));
	return Out;
}

tongsim_lite::common::Rotatorf ToProtoRotatorf(const FRotator& Rotator)
{
	tongsim_lite::common::Rotatorf Out;
	Out.set_roll_deg(static_cast<float>(Rotator.Roll));
	Out.set_pitch_deg(static_cast<float>(Rotator.Pitch));
	Out.set_yaw_deg(static_cast<float>(Rotator.Yaw));
	return Out;
}

tongsim_lite::common::Transform ToProtoTransform(const FTransform& Transform)
{
	tongsim_lite::common::Transform Out;
	*Out.mutable_location() = ToProtoVector3f(Transform.GetLocation());
	*Out.mutable_rotation() = ToProtoRotatorf(Transform.Rotator());
	*Out.mutable_scale() = ToProtoVector3f(Transform.GetScale3D());
	return Out;
}

bool ResolveVoxelHalfNum(
	const bool bHasOverride,
	const int32 OverrideTotalNum,
	const int32 ComponentHalfNum,
	const char* FieldName,
	uint32& OutHalfNum,
	std::string& OutError)
{
	if (!bHasOverride)
	{
		OutHalfNum = static_cast<uint32>(ComponentHalfNum);
		return true;
	}

	if (OverrideTotalNum <= 0 || OverrideTotalNum % 2 != 0)
	{
		OutError = std::string(FieldName) + " must be a positive even voxel count.";
		return false;
	}

	OutHalfNum = static_cast<uint32>(OverrideTotalNum / 2);
	return true;
}

FVector ResolveBoxSize(const tongsim_lite::voxel::QueryAgentVoxelRequest& Request, const UVoxelPerceptionComponent& Component)
{
	if (!Request.has_extent())
	{
		return Component.BoxSize;
	}

	const tongsim_lite::common::Vector3f& Extent = Request.extent();
	return FVector(
		static_cast<double>(Extent.x()) * 2.0,
		static_cast<double>(Extent.y()) * 2.0,
		static_cast<double>(Extent.z()) * 2.0);
}
}

UVoxelPerceptionSubsystem* UVoxelPerceptionSubsystem::Instance = nullptr;

void UVoxelPerceptionSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	Instance = this;
	FWorldDelegates::OnPostWorldInitialization.AddUObject(this, &ThisClass::HandlePostWorldInit);
}

void UVoxelPerceptionSubsystem::Deinitialize()
{
	FWorldDelegates::OnPostWorldInitialization.RemoveAll(this);
	Instance = nullptr;
	Super::Deinitialize();
}

void UVoxelPerceptionSubsystem::HandlePostWorldInit(UWorld*, const UWorld::InitializationValues)
{
	if (UTSGrpcSubsystem* Grpc = ResolveGrpcSubsystem())
	{
		Grpc->RegisterUnaryHandler(std::string(kVoxelServicePrefix) + "QueryAgentVoxel", &ThisClass::QueryAgentVoxel);
	}
}

UTSGrpcSubsystem* UVoxelPerceptionSubsystem::ResolveGrpcSubsystem() const
{
	return UTSGrpcSubsystem::GetInstance();
}

ResponseStatus UVoxelPerceptionSubsystem::QueryAgentVoxel(
	tongsim_lite::voxel::QueryAgentVoxelRequest& Request,
	tongsim_lite::voxel::QueryAgentVoxelResponse& Response)
{
	UWorld* World = GetGameWorld();
	if (!World)
	{
		return ResponseStatus(grpc::StatusCode::UNAVAILABLE, "No valid UWorld.");
	}

	if (!Instance)
	{
		return ResponseStatus(grpc::StatusCode::UNAVAILABLE, "VoxelPerception subsystem unavailable.");
	}

	UTSGrpcSubsystem* Grpc = Instance->ResolveGrpcSubsystem();
	if (!Grpc)
	{
		return ResponseStatus(grpc::StatusCode::UNAVAILABLE, "No valid TongSim gRPC Subsystem.");
	}

	FGuid AgentGuid;
	if (!BytesLEToGuid(Request.agent_id().guid(), AgentGuid))
	{
		return ResponseStatus(grpc::StatusCode::NOT_FOUND, "Actor not found.");
	}

	AActor* Agent = Grpc->FindActorByGuid(AgentGuid);
	if (!IsValid(Agent))
	{
		return ResponseStatus(grpc::StatusCode::NOT_FOUND, "Actor not found.");
	}

	UVoxelPerceptionComponent* Component = Agent->FindComponentByClass<UVoxelPerceptionComponent>();
	if (!IsValid(Component))
	{
		return ResponseStatus(grpc::StatusCode::NOT_FOUND, "Agent has no VoxelPerceptionComponent.");
	}

	const FTransform QueryTransform = Agent->GetActorTransform();

	uint32 VoxelHalfNumX = 0;
	uint32 VoxelHalfNumY = 0;
	uint32 VoxelHalfNumZ = 0;
	std::string OverrideError;
	if (!ResolveVoxelHalfNum(Request.has_voxel_num_x(), Request.voxel_num_x(), Component->VoxelHalfNumX, "voxel_num_x", VoxelHalfNumX, OverrideError)
		|| !ResolveVoxelHalfNum(Request.has_voxel_num_y(), Request.voxel_num_y(), Component->VoxelHalfNumY, "voxel_num_y", VoxelHalfNumY, OverrideError)
		|| !ResolveVoxelHalfNum(Request.has_voxel_num_z(), Request.voxel_num_z(), Component->VoxelHalfNumZ, "voxel_num_z", VoxelHalfNumZ, OverrideError))
	{
		return ResponseStatus(grpc::StatusCode::INVALID_ARGUMENT, OverrideError);
	}

	const FVector BoxSize = ResolveBoxSize(Request, *Component);

	FVoxelGridQueryParam QueryParam{World};
	UGameplayStatics::GetAllActorsOfClass(World, AActor::StaticClass(), QueryParam.Actors);
	QueryParam.Actors.Remove(Agent);
	QueryParam.GridBox = FVoxelBox(
		QueryTransform,
		VoxelHalfNumX,
		VoxelHalfNumY,
		VoxelHalfNumZ,
		BoxSize);

	TArray<uint8> VoxelGrids;
	TSVoxelGridFuncLib::QueryVoxelGrids(QueryParam, VoxelGrids, World);

	Response.mutable_voxel()->set_voxel_buffer(
		reinterpret_cast<const char*>(VoxelGrids.GetData()),
		VoxelGrids.Num());
	*Response.mutable_agent_transform() = ToProtoTransform(QueryTransform);
	Response.set_timestamp(FPlatformTime::Seconds());

	return ResponseStatus::OK;
}
