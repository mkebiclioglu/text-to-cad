# CLAUDE.md

Notes for Claude Code when working in this repo.

## Commit style

- Keep commit messages simple and short — a single descriptive line is usually enough.
- Do **not** add the `Co-Authored-By: Claude` trailer or any "Generated with Claude Code" sign-off.
- Only create commits when explicitly asked.

## Project shape

- Small FastAPI service: `app.py` (routes), `generator.py` (LLM + retry loop), `validator.py` (sandbox + geometry + printability), `prompts.py` (system prompt + few-shot).
- Two backends behind `LLM_PROVIDER`: `ollama` (local, default) or `anthropic` (cloud).
- Config comes from environment variables loaded from `.env` via `python-dotenv` (`load_dotenv()` in `generator.py`). `.env.example` is the committed template; real `.env` is gitignored.

## Conventions

- No frontend — API only.
- Don't add a Makefile or other wrapper tooling unless asked; the repo is small enough that raw commands are clearer.
- Prefer editing existing files over adding new ones.
