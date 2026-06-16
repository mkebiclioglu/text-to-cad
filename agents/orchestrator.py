"""Orchestrator: drives Designer -> Generator (per part) -> Critic loops.

The two feedback loops:
  Inner — Generator <-> validator. Already inside generator.generate_part.
  Outer — Critic findings flow back into the Designer, which produces a revised
          spec; only affected parts are regenerated. Capped at MAX_OUTER_ITERATIONS.

Single-part designs skip the Critic entirely — there's nothing for it to compare
spec-vs-result against beyond what validate_single_part already caught.
"""

from agents import critic, designer
from agents.generator import GeneratorError, generate_part

MAX_OUTER_ITERATIONS = 2  # Designer -> regen -> Critic cycles after the initial pass


def run(description: str) -> dict:
    """
    Returns:
        {
          "design_type": "single" | "assembly",
          "spec": <final designer spec>,
          "parts": [
            {"name", "spec", "code", "shape", "warnings", "summary"}, ...
          ],
          "critique": <last critic response, or None for single-part>,
          "iterations": <number of outer loops that fired>,
        }
    """
    spec = designer.design(description)
    parts_state: dict[str, dict] = {}
    parts_to_generate = [p["name"] for p in spec["parts"]]

    iterations = 0
    last_critique = None

    while True:
        for name in parts_to_generate:
            part_spec = _find_part(spec, name)
            if part_spec is None:
                continue
            try:
                code, shape, warnings = generate_part(part_spec, spec["global_dims"])
            except GeneratorError:
                # No graceful per-part recovery — bubble up. The HTTP layer
                # turns this into a 422 the user can act on.
                raise
            parts_state[name] = {
                "spec": part_spec,
                "code": code,
                "shape": shape,
                "warnings": warnings,
                "summary": _summarize(name, part_spec, shape, warnings),
            }

        if spec["design_type"] == "single":
            break

        if iterations >= MAX_OUTER_ITERATIONS:
            break

        summaries = [parts_state[n]["summary"] for n in parts_state]
        last_critique = critic.review(description, spec, summaries)

        if last_critique["approve"]:
            break

        iterations += 1

        spec = designer.design(description, critique=last_critique, prior_spec=spec)

        # Reconcile state with the revised spec
        new_names = {p["name"] for p in spec["parts"]}
        for stale in list(parts_state.keys()):
            if stale not in new_names:
                parts_state.pop(stale)

        affected = {fix["part_name"] for fix in last_critique["fixes"] if fix["action"] != "remove"}
        # Anything in the revised spec that we haven't built yet must be (re)generated
        for part_spec in spec["parts"]:
            if part_spec["name"] not in parts_state:
                affected.add(part_spec["name"])
        parts_to_generate = [n for n in affected if n in new_names]

    return {
        "design_type": spec["design_type"],
        "spec": spec,
        "parts": [parts_state[p["name"]] for p in spec["parts"] if p["name"] in parts_state],
        "critique": last_critique,
        "iterations": iterations,
    }


def _find_part(spec: dict, name: str) -> dict | None:
    for p in spec["parts"]:
        if p["name"] == name:
            return p
    return None


def _summarize(name: str, part_spec: dict, shape, warnings: list[str]) -> dict:
    """Per-part summary fed to the Critic — geometry truth, not the spec's intent."""
    solid = shape.val() if hasattr(shape, "val") else shape
    bb = solid.BoundingBox()
    try:
        _, tris = solid.tessellate(0.5)
        triangle_count = len(tris)
    except Exception:
        triangle_count = -1

    return {
        "name": name,
        "qty": part_spec["qty"],
        "print_notes": part_spec["print_notes"],
        "bbox_mm": {
            "x": round(bb.xlen, 2),
            "y": round(bb.ylen, 2),
            "z": round(bb.zlen, 2),
        },
        "triangle_count": triangle_count,
        "warnings": list(warnings),
    }
