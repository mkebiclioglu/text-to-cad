# CLAUDE.md

Notes for Claude Code when working in this repo.

## Commit style

- Keep commit messages simple and short — a single descriptive line is usually enough.
- Do **not** add the `Co-Authored-By: Claude` trailer or any "Generated with Claude Code" sign-off.
- Only create commits when explicitly asked.

## Project shape

- Small FastAPI service: `app.py` (routes), `generator.py` (LLM + retry loop), `validator.py` (sandbox + geometry + printability), `prompts.py` (system prompt + few-shot).
- Two generation modes: `/generate` for single STL downloads, `/generate-assembly` for multi-part assemblies (returns JSON manifest, exports each child to its own STL in `outputs/`). The LLM is told to use `cq.Assembly` + a `PARTS` metadata dict when the request implies multiple printable parts.
- Two backends behind `LLM_PROVIDER`: `anthropic` (cloud, default) or `ollama` (local alternative).
- Config comes from environment variables loaded from `.env` via `python-dotenv` (`load_dotenv()` in `generator.py`). `.env.example` is the committed template; real `.env` is gitignored.

## Conventions

- No frontend — API only.
- Don't add a Makefile or other wrapper tooling unless asked; the repo is small enough that raw commands are clearer.
- Prefer editing existing files over adding new ones.
