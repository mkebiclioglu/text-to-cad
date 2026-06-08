import os
import tempfile
from datetime import datetime

import cadquery as cq
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from generator import generate_cad

app = FastAPI(title="text-to-cad")


class GenerateRequest(BaseModel):
    description: str


class ChatRequest(BaseModel):
    description: str
    history: list[dict] = []


class ChatResponse(BaseModel):
    code: str
    warnings: list[str]
    history: list[dict]


@app.post("/generate")
async def generate(req: GenerateRequest):
    """Single-shot: description → STL file download."""
    try:
        code, cq_result, warnings, _ = generate_cad(req.description)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"part_{timestamp}.stl"

    tmp = tempfile.NamedTemporaryFile(suffix=".stl", delete=False)
    try:
        cq.exporters.export(cq_result, tmp.name)
        return FileResponse(
            path=tmp.name,
            media_type="model/stl",
            filename=filename,
            headers={"X-Warnings": "; ".join(warnings)} if warnings else {},
        )
    except Exception as e:
        os.unlink(tmp.name)
        raise HTTPException(status_code=500, detail=f"STL export failed: {e}")


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Multi-turn: returns code + warnings + updated history for the next turn."""
    try:
        code, _, warnings, updated_history = generate_cad(
            req.description, history=req.history or None
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return ChatResponse(code=code, warnings=warnings, history=updated_history)


@app.get("/health")
async def health():
    return {"status": "ok"}
