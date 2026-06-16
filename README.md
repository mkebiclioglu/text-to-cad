# text-to-cad

A natural language to 3D-printable CAD pipeline. Describe a functional part in plain English, get an STL file back. Multi-part assemblies get reviewed by a Critic agent before being returned.

**Stack:** FastAPI · CadQuery · Anthropic Claude · agent-based (Designer / Generator / Critic)

---

## Quickstart

You need an API key from [console.anthropic.com](https://console.anthropic.com).

```bash
git clone <your-repo-url>
cd text-to-cad
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# open .env and paste your key into ANTHROPIC_API_KEY=
uvicorn app:app --reload
```

In another terminal, confirm it's running:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

Then jump to [Usage](#usage) to generate your first STL.

---

## How it works

1. You POST a plain-language description to `/generate` or `/generate-assembly`.
2. The **Designer** agent turns the description into a structured engineering spec (parts, shared dimensions, interfaces, qty).
3. The **Generator** agent builds one part at a time, with an inner retry loop on validator errors (up to 4 attempts per part).
4. Three validation layers run per part: Python execution → geometry validity → printability checks.
5. For multi-part designs, the **Critic** agent compares the actual geometry (bounding boxes, triangle counts) to the spec and the original request. If it finds gaps, the Designer revises the spec and only affected parts are regenerated. Capped at 2 outer iterations.
6. STLs are written to `outputs/` and either returned as a single download (`/generate`) or as a JSON manifest (`/generate-assembly`).

---

## Setup detail

### 1. Clone and create virtual environment

```bash
git clone <your-repo-url>
cd text-to-cad
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` and paste your Anthropic API key into `ANTHROPIC_API_KEY=`. That's the only required change for the default setup. `.env` is gitignored — your key stays local. It's auto-loaded at startup.

(Optional) switch to Sonnet for cheaper / faster runs by setting `ANTHROPIC_MODEL=claude-sonnet-4-6`.

### 3. Run the server

```bash
uvicorn app:app --reload
```

---

**Note:** the agentic architecture (Designer / Critic via forced tool use) requires reliable Anthropic-style tool calling. The previous Ollama fallback has been removed — local 7b models can't reliably produce the structured JSON the Designer and Critic need.

---

## Usage

### Generate an STL (single shot)

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"description": "A shelf bracket 80mm wide, 60mm deep, 4mm thick with two M4 mounting holes"}' \
  -OJ
```

Saves a timestamped file like `part_20260607_143022.stl` in the current directory. The server also keeps a copy under `outputs/` in the repo (gitignored) so you can re-open recent prints without re-running.

If the description implies multiple printable parts, `/generate` returns `422 — Use POST /generate-assembly instead`. Switch endpoints.

### Generate a multi-part assembly

Use `/generate-assembly` when the description implies more than one printable part (e.g. a hinge, a drone, a peg-and-socket joint). Each part is exported as its own STL under `outputs/`, and the response is a JSON manifest with per-part qty, print notes, and warnings.

```bash
curl -X POST http://localhost:8000/generate-assembly \
  -H "Content-Type: application/json" \
  -d '{"description": "A 10mm shaft 50mm long with a separate retaining collar (20mm OD, 6mm thick) that slides onto it"}'
```

Response shape (abridged):

```json
{
  "design_type": "assembly",
  "summary": "A two-part mechanical assembly...",
  "iterations": 0,
  "spec": { "design_type": "assembly", "global_dims": {...}, "parts": [...] },
  "critique": {
    "approve": true,
    "summary": "Bounding boxes match spec exactly...",
    "missed_requirements": [],
    "fixes": []
  },
  "parts": [
    {
      "name": "shaft",
      "path": "outputs/shaft_20260615_204500.stl",
      "qty": 1,
      "print_notes": "Print vertical for best concentricity",
      "bbox_mm": {"x": 10.0, "y": 10.0, "z": 50.0},
      "size_bytes": 25084,
      "warnings": [],
      "code": "import cadquery as cq\nshaft_diameter = 10\n..."
    }
  ]
}
```

- `iterations` — how many Designer→Critic outer-loop rounds fired. 0 means the first design was approved.
- `critique` — the last Critic verdict. If `approve` is false, the response still contains the best-effort parts (after the outer loop hit its cap).
- `spec` — the final Designer spec the parts were built from. Useful for understanding what the Designer inferred from your description.

Print each STL separately, then assemble physically.

### Health check

```bash
curl http://localhost:8000/health
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required. |
| `ANTHROPIC_MODEL` | `claude-opus-4-7` | Any Anthropic model ID (e.g. `claude-sonnet-4-6` for cheaper runs). The same model is used by all three agents. |

---

## Project structure

```
app.py                  — FastAPI server (POST /generate, POST /generate-assembly, GET /health)

agents/                 — LLM-driven roles, one prompt per agent
  _client.py            — shared Anthropic client (call_text + call_structured)
  designer.py           — vague request → structured engineering spec (forced JSON)
  generator.py          — one part spec → validated CadQuery shape (inner retry loop)
  critic.py             — spec + actual geometry → approve/revise (forced JSON)
  orchestrator.py       — drives Designer → Generator (per part) → Critic loops

tools/                  — deterministic Python tools used by agents
  validate.py           — exec sandbox + geometry + printability for one part
  export.py             — STL writer; returns path + bbox + size

prompts/                — role-specific system prompts and tool schemas
  designer.py           — design rules + define_design tool schema
  generator.py          — CadQuery rules + few-shot single-part examples
  critic.py             — review heuristics + review_design tool schema

requirements.txt
```

---

## Agent architecture

Generation runs through four LLM-or-Python steps with **two feedback loops**:

```
description ──► Designer ──► [for each part] Generator ──► Critic ──► approve?
                  ▲              │     ▲                     │
                  │              ▼     │ (inner loop:        │
                  │           validate │  retry on error)    │
                  │              │     │                     │
                  └──────────────┴─────┴─────────────────────┘
                       outer loop: revised spec → regen affected parts
                              (max 2 iterations)
```

- **Designer** — turns a vague description into a structured spec: part list, shared/interface dimensions, qty, print notes. Output forced to JSON via Anthropic tool use. Infers missing engineering requirements ("aquatic" → hollow body, gasket lip, shaft seals).
- **Generator** — given *one* part's spec + the global shared dimensions, writes CadQuery for just that part. Smaller context = less hallucination, less likely to skip details. **Inner loop:** validator errors are fed back as a retry prompt (up to 4 attempts per part).
- **Critic** — given the original user request + spec + per-part bounding boxes + triangle counts, identifies missed requirements (e.g. "body has only 12 triangles, must be solid not hollow"). Output forced to JSON.
- **Orchestrator** — drives the flow. **Outer loop:** Critic findings flow back into the Designer for a revised spec; only affected parts are regenerated. Capped at 2 outer iterations. Single-part designs skip the Critic.

---

## Validation layers

1. **Execution** — runs the generated code in a sandboxed Python env, catches syntax errors and CadQuery exceptions
2. **Geometry** — checks the resulting shape is a valid solid with non-zero dimensions
3. **Printability** — warns if minimum dimension is below 1.5mm or part exceeds 300mm

Each part goes through these checks independently inside the Generator's inner loop. The Critic then sees bounding boxes and triangle counts to do a higher-level design review.

---

## Tips for better results

- Specify screw sizes explicitly: *"two M3 mounting holes"* (the model knows standard clearance diameters)
- Give absolute dimensions in mm
- For complex shapes, describe the geometry: *"L-shaped"*, *"cylindrical"*, *"split clamp"*
- The default Anthropic backend handles complex parts (enclosures, clips, multi-body geometry) much more reliably than the local Ollama option

---

## Limitations

- No frontend — API only
- Complex freeform geometry (curves, organic shapes) is unreliable
- No persistence between sessions
- The local 7b Ollama model struggles with multi-body boolean operations — the default Anthropic backend handles these reliably
