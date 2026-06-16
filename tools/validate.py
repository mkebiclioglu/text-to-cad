"""Deterministic validation of generated CadQuery code for a single part.

The orchestrator generates parts one at a time and validates each one. Assembly
composition happens outside this module — here we only check that one piece of
code produces a single valid printable shape.
"""

import cadquery as cq
from cadquery import Solid, Compound

MIN_WALL_MM = 1.5
MAX_DIMENSION_MM = 300.0


def validate_single_part(code: str) -> tuple[object | None, str | None, list[str]]:
    """
    Execute code in a sandbox, return (shape, error, warnings).
    - shape: the Workplane assigned to `result`, or None if validation failed.
    - error: human-readable error string, suitable for feeding back to the LLM.
    - warnings: non-fatal printability notes (ASCII-safe for HTTP headers).
    """
    sandbox = {"cq": cq}
    try:
        exec(code, sandbox)  # noqa: S102 — local sandbox, not for production user input
    except SyntaxError as e:
        return None, f"SyntaxError on line {e.lineno}: {e.msg}", []
    except Exception as e:
        return None, f"{type(e).__name__}: {e}", []

    result = sandbox.get("result")
    if result is None:
        return None, "Code ran but never assigned a variable named 'result'", []

    if isinstance(result, cq.Assembly):
        return None, (
            "Code produced a cq.Assembly. Each Generator call must produce one "
            "part as a Workplane assigned to `result`, not an Assembly."
        ), []

    try:
        shape = result.val()
    except Exception as e:
        return None, f"Could not extract shape from result: {e}", []

    if not isinstance(shape, (Solid, Compound)):
        return None, f"result.val() is {type(shape).__name__}, expected Solid or Compound", []

    if not shape.isValid():
        return None, "Shape failed CadQuery validity check (self-intersecting or degenerate)", []

    try:
        bb = shape.BoundingBox()
    except Exception as e:
        return None, f"Could not compute bounding box: {e}", []

    if bb.xlen == 0 or bb.ylen == 0 or bb.zlen == 0:
        return None, f"Shape has a zero dimension (xlen={bb.xlen}, ylen={bb.ylen}, zlen={bb.zlen})", []

    return result, None, _printability(bb)


def _printability(bb) -> list[str]:
    warnings = []
    min_dim = min(bb.xlen, bb.ylen, bb.zlen)
    max_dim = max(bb.xlen, bb.ylen, bb.zlen)

    if min_dim < MIN_WALL_MM:
        warnings.append(
            f"Minimum dimension {min_dim:.2f}mm is below {MIN_WALL_MM}mm - "
            "walls this thin may fail during printing"
        )
    if max_dim > MAX_DIMENSION_MM:
        warnings.append(
            f"Part is {max_dim:.0f}mm in its longest dimension - "
            f"exceeds typical {MAX_DIMENSION_MM}mm print bed"
        )
    return warnings
