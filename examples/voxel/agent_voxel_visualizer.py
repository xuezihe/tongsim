"""Render saved QueryAgentVoxel JSON snapshots as PNG frames.

Run:
    uv run --with numpy,matplotlib examples/agent_voxel_visualizer.py
"""

from __future__ import annotations

import argparse
import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_INPUT_DIR = Path("testData/0610data-2")
MAX_DIM_TO_RENDER = 32
DEFAULT_DPI = 150


@dataclass(frozen=True)
class VoxelSample:
    path: Path
    document: dict[str, Any]

    @property
    def sample_index(self) -> int:
        sample = self.document.get("sample") or {}
        value = sample.get("index")
        return int(value) if value is not None else 0

    @property
    def is_final(self) -> bool:
        sample = self.document.get("sample") or {}
        return bool(sample.get("is_final", False))


def discover_sample_files(input_dir: Path) -> list[Path]:
    files = sorted(input_dir.glob("sample_*.json"))
    if not files:
        raise FileNotFoundError(f"No sample_*.json files found under {input_dir}")
    return sorted(files, key=_sample_sort_key)


def _sample_sort_key(path: Path) -> tuple[int, str]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        sample = document.get("sample") or {}
        return int(sample.get("index", 0)), path.name
    except Exception:
        return 0, path.name


def load_sample(path: Path) -> VoxelSample:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema") != "tongsim-lite.query-agent-voxel.live-snapshot.v1":
        raise ValueError(f"{path} is not a QueryAgentVoxel live snapshot")
    return VoxelSample(path=path, document=document)


def decode_sample_voxels(sample: VoxelSample):
    np = _require_numpy()
    metadata = sample.document["voxel_metadata"]
    if metadata.get("encoding") != "bitpacked-lsb-z":
        raise ValueError(f"{sample.path} uses unsupported encoding: {metadata.get('encoding')}")

    dimensions = metadata["dimensions"]
    x_count = int(dimensions["x"])
    y_count = int(dimensions["y"])
    z_count = int(dimensions["z"])
    aligned_z = int(metadata["aligned_z"])
    expected_bytes = x_count * y_count * (aligned_z // 8)
    declared_bytes = int(metadata["byte_length"])
    if declared_bytes != expected_bytes:
        raise ValueError(
            f"{sample.path} byte_length mismatch: metadata={declared_bytes}, expected={expected_bytes}"
        )

    payload = sample.document["response"]["voxel"]["voxel_buffer_base64"]
    voxel_bytes = base64.b64decode(payload)
    if len(voxel_bytes) != declared_bytes:
        raise ValueError(
            f"{sample.path} payload length mismatch: got {len(voxel_bytes)}, expected {declared_bytes}"
        )

    buffer = np.frombuffer(voxel_bytes, dtype=np.uint8, count=declared_bytes)
    bits = np.unpackbits(buffer, bitorder="little")
    grid = bits.reshape((x_count, y_count, aligned_z), order="C")
    return grid[:, :, :z_count].astype(bool, copy=False)


def output_path_for_sample(output_dir: Path, sample_file: Path) -> Path:
    return output_dir / f"{sample_file.stem}.png"


def render_sample(sample: VoxelSample, output_path: Path, max_dim: int, dpi: int) -> Path:
    np = _require_numpy()
    _, plt = _require_matplotlib()

    voxels = decode_sample_voxels(sample)
    downsampled = _downsample_voxels(voxels, max_dim)
    xy_projection = voxels.max(axis=2)

    fig = plt.figure(figsize=(10, 5))
    ax_3d = fig.add_subplot(121, projection="3d")
    ax_xy = fig.add_subplot(122)

    ax_3d.voxels(downsampled)
    ax_3d.set_xlabel("X")
    ax_3d.set_ylabel("Y")
    ax_3d.set_zlabel("Z")

    ax_xy.imshow(xy_projection.T, origin="lower", interpolation="nearest", cmap="gray_r")
    ax_xy.set_title("XY max projection")
    ax_xy.set_xlabel("X")
    ax_xy.set_ylabel("Y")

    title = _sample_title(sample, voxels, np.count_nonzero(voxels))
    fig.suptitle(title)
    fig.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi)
    plt.close(fig)
    return output_path


def render_directory(input_dir: Path, output_dir: Path | None, max_dim: int, dpi: int) -> list[Path]:
    resolved_output_dir = output_dir or (input_dir / "frames")
    rendered: list[Path] = []
    for sample_file in discover_sample_files(input_dir):
        sample = load_sample(sample_file)
        output_path = output_path_for_sample(resolved_output_dir, sample_file)
        rendered.append(render_sample(sample, output_path, max_dim=max_dim, dpi=dpi))
    return rendered


def _downsample_voxels(voxels, max_dim: int):
    np = _require_numpy()
    if max_dim <= 0:
        raise ValueError("max_dim must be positive")
    stride_x = max(1, int(np.ceil(voxels.shape[0] / max_dim)))
    stride_y = max(1, int(np.ceil(voxels.shape[1] / max_dim)))
    stride_z = max(1, int(np.ceil(voxels.shape[2] / max_dim)))
    return voxels[::stride_x, ::stride_y, ::stride_z]


def _sample_title(sample: VoxelSample, voxels, occupied_count: int) -> str:
    response = sample.document.get("response") or {}
    transform = response.get("agent_transform") or {}
    location = transform.get("location") or {}
    timestamp = response.get("timestamp")
    final_suffix = " final" if sample.is_final else ""
    return (
        f"{sample.path.name} | sample={sample.sample_index}{final_suffix} | "
        f"timestamp={float(timestamp):.3f} | "
        f"loc=({float(location.get('x', 0.0)):.1f}, "
        f"{float(location.get('y', 0.0)):.1f}, "
        f"{float(location.get('z', 0.0)):.1f}) | "
        f"shape={tuple(voxels.shape)} | occupied={occupied_count}"
    )


def _require_numpy():
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError(
            "numpy is required. Run: uv run --with numpy,matplotlib examples/agent_voxel_visualizer.py"
        ) from exc
    return np


def _require_matplotlib():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "matplotlib is required. Run: uv run --with numpy,matplotlib examples/agent_voxel_visualizer.py"
        ) from exc
    return matplotlib, plt


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render saved QueryAgentVoxel JSON snapshots as PNG frames."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--max-dim", type=int, default=MAX_DIM_TO_RENDER)
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI)
    args = parser.parse_args()

    rendered = render_directory(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        max_dim=args.max_dim,
        dpi=args.dpi,
    )
    for path in rendered:
        print(f"[RENDER] Saved: {path}")


if __name__ == "__main__":
    main()
