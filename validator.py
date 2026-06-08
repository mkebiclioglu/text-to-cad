import cadquery as cq
from cadquery import Solid, Compound

MIN_WALL_MM = 1.5
MAX_DIMENSION_MM = 300.0


def validate(code: str) -> tuple[object | None, str | None, list[str]]:
    """
    Runs all three validation layers.
    Returns (cq_result, error, warnings).
    If error is not None, cq_result is None and the code should be retried.
    Warnings are non-fatal printability notes.
    """
    cq_result, error = _exec(code)
    if error:
        return None, error, []

    valid, error = _geometry(cq_result)
    if not valid:
        return None, error, []

    warnings = _printability(cq_result)
    return cq_result, None, warnings


def _exec(code: str) -> tuple[object | None, str | None]:
    sandbox = {"cq": cq}
    try:
        exec(code, sandbox)  # noqa: S102 — local sandbox only, not for user input in production
    except SyntaxError as e:
        return None, f"SyntaxError on line {e.lineno}: {e.msg}"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"

    result = sandbox.get("result")
    if result is None:
        return None, "Code ran but never assigned a variable named 'result'"
    return result, None


def _geometry(result) -> tuple[bool, str | None]:
    try:
        shape = result.val()
    except Exception as e:
        return False, f"Could not extract shape from result: {e}"

    if not isinstance(shape, (Solid, Compound)):
        return False, f"result.val() is {type(shape).__name__}, expected a Solid or Compound"

    if not shape.isValid():
        return False, "Shape failed CadQuery validity check (self-intersecting or degenerate geometry)"

    try:
        bb = shape.BoundingBox()
    except Exception as e:
        return False, f"Could not compute bounding box: {e}"

    if bb.xlen == 0 or bb.ylen == 0 or bb.zlen == 0:
        return False, f"Shape has a zero dimension (xlen={bb.xlen}, ylen={bb.ylen}, zlen={bb.zlen})"

    return True, None


def _printability(result) -> list[str]:
    warnings = []
    try:
        bb = result.val().BoundingBox()
        min_dim = min(bb.xlen, bb.ylen, bb.zlen)
        max_dim = max(bb.xlen, bb.ylen, bb.zlen)

        if min_dim < MIN_WALL_MM:
            warnings.append(
                f"Minimum dimension {min_dim:.2f}mm is below {MIN_WALL_MM}mm — "
                "walls this thin may fail during printing"
            )
        if max_dim > MAX_DIMENSION_MM:
            warnings.append(
                f"Part is {max_dim:.0f}mm in its longest dimension — "
                f"exceeds typical {MAX_DIMENSION_MM}mm print bed"
            )
    except Exception as e:
        warnings.append(f"Printability check skipped: {e}")

    return warnings
