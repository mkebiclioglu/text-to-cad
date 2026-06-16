import cadquery as cq
from cadquery import Assembly, Solid, Compound

MIN_WALL_MM = 1.5
MAX_DIMENSION_MM = 300.0


def validate(
    code: str,
) -> tuple[object | None, str | None, list[str], dict[str, dict] | None]:
    """
    Runs all three validation layers.
    Returns (cq_result, error, warnings, parts_meta).
    - If error is not None, cq_result is None and the code should be retried.
    - warnings is a flat list of non-fatal notes (assembly warnings are prefixed with "<part>: ").
    - parts_meta is None for single-part results; for assemblies it maps
      part name -> {"qty": int, "print_notes": str, "warnings": list[str]}.
    """
    cq_result, parts_meta_raw, error = _exec(code)
    if error:
        return None, error, [], None

    if isinstance(cq_result, Assembly):
        warnings, parts_meta, error = _validate_assembly(cq_result, parts_meta_raw)
        if error:
            return None, error, [], None
        return cq_result, None, warnings, parts_meta

    valid, error = _geometry(cq_result)
    if not valid:
        return None, error, [], None

    return cq_result, None, _printability_workplane(cq_result), None


def _exec(code: str) -> tuple[object | None, dict | None, str | None]:
    sandbox = {"cq": cq}
    try:
        exec(code, sandbox)  # noqa: S102 — local sandbox only, not for user input in production
    except SyntaxError as e:
        return None, None, f"SyntaxError on line {e.lineno}: {e.msg}"
    except Exception as e:
        return None, None, f"{type(e).__name__}: {e}"

    result = sandbox.get("result")
    if result is None:
        return None, None, "Code ran but never assigned a variable named 'result'"

    parts_meta = sandbox.get("PARTS")
    if parts_meta is not None and not isinstance(parts_meta, dict):
        return None, None, "PARTS must be a dict keyed by part name"

    return result, parts_meta, None


def _geometry(result) -> tuple[bool, str | None]:
    try:
        shape = result.val()
    except Exception as e:
        return False, f"Could not extract shape from result: {e}"

    return _check_shape(shape)


def _check_shape(shape) -> tuple[bool, str | None]:
    if not isinstance(shape, (Solid, Compound)):
        return False, f"shape is {type(shape).__name__}, expected a Solid or Compound"

    if not shape.isValid():
        return False, "Shape failed CadQuery validity check (self-intersecting or degenerate geometry)"

    try:
        bb = shape.BoundingBox()
    except Exception as e:
        return False, f"Could not compute bounding box: {e}"

    if bb.xlen == 0 or bb.ylen == 0 or bb.zlen == 0:
        return False, f"Shape has a zero dimension (xlen={bb.xlen}, ylen={bb.ylen}, zlen={bb.zlen})"

    return True, None


def _printability_workplane(result) -> list[str]:
    try:
        return _printability_bb(result.val().BoundingBox())
    except Exception as e:
        return [f"Printability check skipped: {e}"]


def _printability_bb(bb) -> list[str]:
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


def _validate_assembly(
    assembly, parts_meta_raw: dict | None
) -> tuple[list[str], dict[str, dict], str | None]:
    if not assembly.children:
        return [], {}, "Assembly has no children — add parts with .add(shape, name=...)"

    flat_warnings: list[str] = []
    parts_meta: dict[str, dict] = {}

    for idx, child in enumerate(assembly.children):
        name = child.name or f"part_{idx}"
        try:
            shape = child.obj.val() if hasattr(child.obj, "val") else child.obj
        except Exception as e:
            return [], {}, f"[{name}] could not extract shape: {e}"

        valid, error = _check_shape(shape)
        if not valid:
            return [], {}, f"[{name}] {error}"

        try:
            part_warnings = _printability_bb(shape.BoundingBox())
        except Exception as e:
            part_warnings = [f"Printability check skipped: {e}"]

        raw = (parts_meta_raw or {}).get(name, {})
        parts_meta[name] = {
            "qty": int(raw.get("qty", 1)),
            "print_notes": str(raw.get("print_notes", "")),
            "warnings": part_warnings,
        }
        flat_warnings.extend(f"{name}: {w}" for w in part_warnings)

    return flat_warnings, parts_meta, None
