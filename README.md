# text-to-cad

A natural language to 3D-printable CAD pipeline. Describe a functional part in plain English, get an STL file back in ~30 seconds.

**Stack:** FastAPI · CadQuery · Ollama (local) or Anthropic Claude (cloud)

---

## How it works

1. You POST a plain-language description to `/generate`
2. The LLM generates parametric CadQuery (Python) code
3. The code runs in a sandbox — if it fails, the error is fed back to the LLM and it retries (up to 4 attempts)
4. Three validation layers run: Python execution → geometry validity → printability checks
5. A timestamped STL file is returned

---

## Setup

### 1. Clone and create virtual environment

```bash
git clone <your-repo-url>
cd text-to-cad
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

Copy the example file and edit it with your settings:

```bash
cp .env.example .env
```

`.env` is gitignored — your API key stays local. The file is auto-loaded at startup.

### 3. Choose a backend

#### Option A — Local inference (free, no API key)

Leave `LLM_PROVIDER=ollama` in `.env`. Install Ollama from [ollama.com](https://ollama.com), pull the model, and run:

```bash
ollama pull qwen2.5-coder:7b
uvicorn app:app --reload
```

#### Option B — Anthropic Claude (better quality, pay-per-use)

Get an API key at [console.anthropic.com](https://console.anthropic.com), then in `.env` set:

```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_key_here
```

(Optional) switch to Sonnet for cheaper runs by setting `ANTHROPIC_MODEL=claude-sonnet-4-6`. Then:

```bash
uvicorn app:app --reload
```

---

## Usage

### Generate an STL (single shot)

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"description": "A shelf bracket 80mm wide, 60mm deep, 4mm thick with two M4 mounting holes"}' \
  -OJ
```

Saves a timestamped file like `part_20260607_143022.stl` in the current directory.

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
| `LLM_PROVIDER` | `ollama` | `ollama` or `anthropic` |
| `OLLAMA_MODEL` | `qwen2.5-coder:7b` | Any model available in your Ollama install |
| `ANTHROPIC_MODEL` | `claude-opus-4-8` | Any Anthropic model ID |
| `ANTHROPIC_API_KEY` | — | Required when `LLM_PROVIDER=anthropic` |

---

## Project structure

```
app.py          — FastAPI server (POST /generate, POST /chat, GET /health)
generator.py    — LLM call + retry loop, provider switching
validator.py    — 3-layer validation: exec sandbox, geometry, printability
prompts.py      — System prompt + few-shot CadQuery examples
requirements.txt
```

---

## Validation layers

1. **Execution** — runs the generated code in a sandboxed Python env, catches syntax errors and CadQuery exceptions
2. **Geometry** — checks the resulting shape is a valid solid with non-zero dimensions
3. **Printability** — warns if minimum dimension is below 1.5mm or part exceeds 300mm

---

## Tips for better results

- Specify screw sizes explicitly: *"two M3 mounting holes"* (the model knows standard clearance diameters)
- Give absolute dimensions in mm
- For complex shapes, describe the geometry: *"L-shaped"*, *"cylindrical"*, *"split clamp"*
- Use Anthropic backend for complex parts (enclosures, clips, multi-body geometry)

---

## Limitations

- No frontend — API only
- Complex freeform geometry (curves, organic shapes) is unreliable
- No persistence between sessions
- Local 7b model struggles with multi-body boolean operations — use Anthropic backend for those
