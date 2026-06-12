import argparse
import asyncio

from tongsim.connection.grpc.core import GrpcConnection
from tongsim.connection.grpc.utils import proto_to_sdk
from tongsim_lite_protobuf.object_pb2 import ObjectId
from tongsim_lite_protobuf.voxel_pb2 import QueryAgentVoxelRequest
from tongsim_lite_protobuf.voxel_pb2_grpc import VoxelServiceStub


DEFAULT_VOXEL_RESOLUTION = (40, 40, 40)


def expected_voxel_byte_length(voxel_resolution: tuple[int, int, int]) -> int:
    voxel_num_x, voxel_num_y, voxel_num_z = voxel_resolution
    aligned_z = ((voxel_num_z + 7) // 8) * 8
    return voxel_num_x * voxel_num_y * (aligned_z // 8)


def _guid_string_to_fguid_bytes(guid: str) -> bytes:
    value = guid.replace("-", "").strip()
    if len(value) != 32:
        raise ValueError("agent_id must be a canonical GUID string.")

    raw = bytes.fromhex(value)
    return raw[0:4][::-1] + raw[4:6][::-1] + raw[6:8][::-1] + raw[8:16]


def _to_object_id(agent_id: bytes | str | dict) -> ObjectId:
    if isinstance(agent_id, dict):
        agent_id = agent_id.get("guid", b"")

    if isinstance(agent_id, bytes | bytearray):
        guid = bytes(agent_id)
    elif isinstance(agent_id, str):
        guid = _guid_string_to_fguid_bytes(agent_id)
    else:
        guid = b""

    if len(guid) != 16:
        raise ValueError("agent_id must be 16-byte FGuid bytes or a canonical GUID string.")

    return ObjectId(guid=guid)


async def query_agent_voxel_once(
    conn: GrpcConnection,
    agent_id: bytes | str | dict,
    voxel_resolution: tuple[int, int, int] | None = None,
    extent_cm: tuple[float, float, float] | None = None,
    timeout: float = 5.0,
) -> dict:
    stub = conn.get_stub(VoxelServiceStub)
    request = QueryAgentVoxelRequest(agent_id=_to_object_id(agent_id))
    resolved_resolution = voxel_resolution or DEFAULT_VOXEL_RESOLUTION
    if voxel_resolution is not None:
        request.voxel_num_x, request.voxel_num_y, request.voxel_num_z = voxel_resolution
    if extent_cm is not None:
        request.extent.x, request.extent.y, request.extent.z = extent_cm
    response = await stub.QueryAgentVoxel(request, timeout=timeout)
    expected_bytes = expected_voxel_byte_length(resolved_resolution)
    actual_bytes = len(response.voxel.voxel_buffer)
    return {
        "voxel_buffer": response.voxel.voxel_buffer,
        "voxel_resolution": resolved_resolution,
        "expected_voxel_bytes": expected_bytes,
        "actual_voxel_bytes": actual_bytes,
        "buffer_size_matches_resolution": actual_bytes == expected_bytes,
        "agent_transform": proto_to_sdk(response.agent_transform),
        "timestamp": float(response.timestamp),
    }


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Query agent-centered voxel perception once.")
    parser.add_argument("agent_id", help="Agent GUID in canonical string form.")
    parser.add_argument("--endpoint", default="localhost:5726")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--voxel-num-x", type=int)
    parser.add_argument("--voxel-num-y", type=int)
    parser.add_argument("--voxel-num-z", type=int)
    parser.add_argument("--extent-x-cm", type=float)
    parser.add_argument("--extent-y-cm", type=float)
    parser.add_argument("--extent-z-cm", type=float)
    args = parser.parse_args()

    voxel_resolution = None
    if None not in (args.voxel_num_x, args.voxel_num_y, args.voxel_num_z):
        voxel_resolution = (args.voxel_num_x, args.voxel_num_y, args.voxel_num_z)

    extent_cm = None
    if None not in (args.extent_x_cm, args.extent_y_cm, args.extent_z_cm):
        extent_cm = (args.extent_x_cm, args.extent_y_cm, args.extent_z_cm)

    async with GrpcConnection(args.endpoint) as conn:
        snapshot = await query_agent_voxel_once(
            conn,
            args.agent_id,
            voxel_resolution=voxel_resolution,
            extent_cm=extent_cm,
            timeout=args.timeout,
        )
        print(
            f"voxel_bytes={len(snapshot['voxel_buffer'])} "
            f"expected_voxel_bytes={snapshot['expected_voxel_bytes']} "
            f"buffer_size_matches_resolution={snapshot['buffer_size_matches_resolution']} "
            f"timestamp={snapshot['timestamp']:.6f} "
            f"agent_transform={snapshot['agent_transform']}"
        )


if __name__ == "__main__":
    asyncio.run(_main())
