# text-to-cad

A natural language to 3D-printable CAD pipeline. Describe a functional part in plain English, get an STL file back in ~30 seconds.

**Stack:** FastAPI · CadQuery · Anthropic Claude (default) or Ollama (local alternative)

---

## Quickstart

The default backend is Anthropic Claude. You need an API key from [console.anthropic.com](https://console.anthropic.com).

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

Prefer running a local model with no API key? See [Alternative: local Ollama backend](#alternative-local-ollama-backend).

---

## How it works

1. You POST a plain-language description to `/generate`
2. The LLM generates parametric CadQuery (Python) code
3. The code runs in a sandbox — if it fails, the error is fed back to the LLM and it retries (up to 4 attempts)
4. Three validation layers run: Python execution → geometry validity → printability checks
5. A timestamped STL file is returned

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

## Alternative: local Ollama backend

Run inference on your own machine — free, no API key, but lower quality and slower (especially for complex parts).

1. Install Ollama from [ollama.com](https://ollama.com) and make sure it's running.
2. Pull the model:
   ```bash
   ollama pull qwen2.5-coder:7b
   ```
3. In `.env`, set:
   ```
   LLM_PROVIDER=ollama
   ```
4. Run the server as usual: `uvicorn app:app --reload`.

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

Response shape:

```json
{
  "code": "...full CadQuery script...",
  "parts": [
    {
      "name": "shaft",
      "path": "outputs/shaft_20260615_204500.stl",
      "qty": 1,
      "print_notes": "Print vertical for best concentricity",
      "warnings": []
    },
    {
      "name": "collar",
      "path": "outputs/collar_20260615_204500.stl",
      "qty": 1,
      "print_notes": "Print flat on bed, bore facing up",
      "warnings": []
    }
  ]
}
```

Print each STL separately, then assemble physically.

**Note:** Assemblies are realistically only usable with the Anthropic backend. The local 7b Ollama model struggles to reason about interface fits between parts.

### Multi-turn chat

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"description": "A drawer handle 120mm long, 25mm wide, 20mm tall with two M3 holes 80mm apart", "history": []}'
```

Returns JSON with `code`, `warnings`, and `history`. Pass `history` back on the next turn to continue the conversation.

### Health check

```bash
curl http://localhost:8000/health
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | `anthropic` or `ollama` |
| `ANTHROPIC_API_KEY` | — | Required when `LLM_PROVIDER=anthropic` |
| `ANTHROPIC_MODEL` | `claude-opus-4-7` | Any Anthropic model ID (e.g. `claude-sonnet-4-6` for cheaper runs) |
| `OLLAMA_MODEL` | `qwen2.5-coder:7b` | Any model available in your Ollama install |

---

## Project structure

```
app.py          — FastAPI server (POST /generate, POST /generate-assembly, POST /chat, GET /health)
generator.py    — LLM call + retry loop, provider switching
validator.py    — 3-layer validation: exec sandbox, geometry, printability (single parts and assemblies)
prompts.py      — System prompt + few-shot CadQuery examples (incl. assembly mode)
requirements.txt
```

---

## Validation layers

1. **Execution** — runs the generated code in a sandboxed Python env, catches syntax errors and CadQuery exceptions
2. **Geometry** — checks the resulting shape is a valid solid with non-zero dimensions
3. **Printability** — warns if minimum dimension is below 1.5mm or part exceeds 300mm

For assemblies, geometry and printability checks run against each child part individually; warnings come back per part in the `/generate-assembly` response.

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
