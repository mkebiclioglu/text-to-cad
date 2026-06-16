from datetime import datetime
from pathlib import Path

import cadquery as cq
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from generator import generate_cad

OUTPUTS_DIR = Path(__file__).parent / "outputs"

app = FastAPI(title="text-to-cad")


def _ascii_header(value: str) -> str:
    # HTTP header values must be latin-1 encodable; strip anything else.
    return value.encode("ascii", "replace").decode("ascii")


class GenerateRequest(BaseModel):
    description: str


class ChatRequest(BaseModel):
    description: str
    history: list[dict] = []


class ChatResponse(BaseModel):
    code: str
    warnings: list[str]
    history: list[dict]


class AssemblyPart(BaseModel):
    name: str
    path: str
    qty: int
    print_notes: str
    warnings: list[str]


class AssemblyResponse(BaseModel):
    code: str
    parts: list[AssemblyPart]


@app.post("/generate")
async def generate(req: GenerateRequest):
    """Single-shot: description → STL file download. For multi-part requests, use /generate-assembly."""
    try:
        code, cq_result, warnings, parts_meta, _ = generate_cad(req.description)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if parts_meta is not None:
        raise HTTPException(
            status_code=422,
            detail="Request produced a multi-part assembly. Use POST /generate-assembly instead.",
        )

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"part_{timestamp}.stl"
    output_path = OUTPUTS_DIR / filename

    try:
        cq.exporters.export(cq_result, str(output_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"STL export failed: {e}")

    return FileResponse(
        path=str(output_path),
        media_type="model/stl",
        filename=filename,
        headers={"X-Warnings": _ascii_header("; ".join(warnings))} if warnings else {},
    )


@app.post("/generate-assembly", response_model=AssemblyResponse)
async def generate_assembly(req: GenerateRequest):
    """Multi-part: description → set of STLs in outputs/ + JSON manifest."""
    try:
        code, cq_result, _, parts_meta, _ = generate_cad(req.description)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if parts_meta is None:
        raise HTTPException(
            status_code=422,
            detail="Request produced a single part, not an assembly. Use POST /generate instead.",
        )

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    parts: list[AssemblyPart] = []
    for idx, child in enumerate(cq_result.children):
        name = child.name or f"part_{idx}"
        filename = f"{name}_{timestamp}.stl"
        output_path = OUTPUTS_DIR / filename
        try:
            cq.exporters.export(child.obj, str(output_path))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"STL export failed for {name}: {e}")

        meta = parts_meta.get(name, {})
        parts.append(
            AssemblyPart(
                name=name,
                path=f"outputs/{filename}",
                qty=int(meta.get("qty", 1)),
                print_notes=str(meta.get("print_notes", "")),
                warnings=list(meta.get("warnings", [])),
            )
        )

    return AssemblyResponse(code=code, parts=parts)


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Multi-turn: returns code + warnings + updated history for the next turn."""
    try:
        code, _, warnings, _, updated_history = generate_cad(
            req.description, history=req.history or None
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return ChatResponse(code=code, warnings=warnings, history=updated_history)


@app.get("/health")
async def health():
    return {"status": "ok"}
