"""STL export for validated shapes."""

from pathlib import Path

import cadquery as cq


def export_stl(shape, output_dir: Path, name: str) -> dict:
    """
    Write `shape` to `{output_dir}/{name}.stl`. Returns metadata including
    path, bounding box, and triangle count — what the Critic needs to review
    the design without reading the binary STL.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{name}.stl"

    cq.exporters.export(shape, str(path))

    bb = shape.val().BoundingBox() if hasattr(shape, "val") else shape.BoundingBox()

    return {
        "path": str(path),
        "filename": path.name,
        "bbox_mm": {
            "x": round(bb.xlen, 2),
            "y": round(bb.ylen, 2),
            "z": round(bb.zlen, 2),
        },
        "bbox_min_mm": {
            "x": round(bb.xmin, 2),
            "y": round(bb.ymin, 2),
            "z": round(bb.zmin, 2),
        },
        "size_bytes": path.stat().st_size,
    }
