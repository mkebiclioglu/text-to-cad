from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agents import orchestrator
from agents.generator import GeneratorError
from tools.export import export_stl

OUTPUTS_DIR = Path(__file__).parent / "outputs"

app = FastAPI(title="text-to-cad")


def _ascii_header(value: str) -> str:
    # HTTP header values must be latin-1 encodable; strip anything else.
    return value.encode("ascii", "replace").decode("ascii")


class GenerateRequest(BaseModel):
    description: str


class AssemblyPart(BaseModel):
    name: str
    path: str
    qty: int
    print_notes: str
    bbox_mm: dict
    size_bytes: int
    warnings: list[str]
    code: str


class CritiqueFix(BaseModel):
    part_name: str
    action: str
    issue: str
    instruction: str


class Critique(BaseModel):
    approve: bool
    summary: str
    missed_requirements: list[str]
    fixes: list[CritiqueFix]


class AssemblyResponse(BaseModel):
    summary: str
    design_type: str
    iterations: int
    spec: dict
    required_hardware: list[str]
    assembly_instructions: list[str]
    critique: Critique | None
    critique_history: list[Critique]
    parts: list[AssemblyPart]


@app.post("/generate")
async def generate(req: GenerateRequest):
    """Single-part designs only — returns STL download. Multi-part requests get 422."""
    try:
        result = orchestrator.run(req.description)
    except GeneratorError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=502, detail=f"Agent failure: {e}")

    if result["design_type"] != "single":
        raise HTTPException(
            status_code=422,
            detail="Request produced a multi-part assembly. Use POST /generate-assembly instead.",
        )

    part = result["parts"][0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    info = export_stl(part["shape"], OUTPUTS_DIR, f"{part['spec']['name']}_{timestamp}")

    warnings = part["warnings"]
    return FileResponse(
        path=info["path"],
        media_type="model/stl",
        filename=info["filename"],
        headers={"X-Warnings": _ascii_header("; ".join(warnings))} if warnings else {},
    )


@app.post("/generate-assembly", response_model=AssemblyResponse)
async def generate_assembly(req: GenerateRequest):
    """Multi-part: orchestrated Designer/Generator/Critic flow. Returns JSON manifest + per-part STLs in outputs/."""
    try:
        result = orchestrator.run(req.description)
    except GeneratorError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=502, detail=f"Agent failure: {e}")

    if result["design_type"] == "single":
        raise HTTPException(
            status_code=422,
            detail="Request produced a single part, not an assembly. Use POST /generate instead.",
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    parts_payload: list[AssemblyPart] = []
    for part in result["parts"]:
        name = part["spec"]["name"]
        info = export_stl(part["shape"], OUTPUTS_DIR, f"{name}_{timestamp}")
        parts_payload.append(
            AssemblyPart(
                name=name,
                path=f"outputs/{info['filename']}",
                qty=part["spec"]["qty"],
                print_notes=part["spec"]["print_notes"],
                bbox_mm=info["bbox_mm"],
                size_bytes=info["size_bytes"],
                warnings=part["warnings"],
                code=part["code"],
            )
        )

    critique = Critique(**result["critique"]) if result.get("critique") else None
    critique_history = [Critique(**c) for c in result.get("critique_history", [])]
    return AssemblyResponse(
        summary=result["spec"]["summary"],
        design_type=result["design_type"],
        iterations=result["iterations"],
        spec=result["spec"],
        required_hardware=result["spec"].get("required_hardware", []),
        assembly_instructions=result["spec"].get("assembly_instructions", []),
        critique=critique,
        critique_history=critique_history,
        parts=parts_payload,
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
