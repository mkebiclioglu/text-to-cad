# CLAUDE.md

Notes for Claude Code when working in this repo.

## Commit style

- Keep commit messages simple and short — a single descriptive line is usually enough.
- Do **not** add the `Co-Authored-By: Claude` trailer or any "Generated with Claude Code" sign-off.
- Only create commits when explicitly asked.

## Project shape

FastAPI service with an agent-based brain. Three packages do all the work:

- `agents/` — LLM roles. `designer.py` produces a structured spec via forced JSON tool use, `generator.py` writes CadQuery for one part at a time (owns the inner retry loop), `critic.py` reviews the generated assembly vs. the original request, `orchestrator.py` drives the loop, `_client.py` is the shared Anthropic client (`call_text` for free-form, `call_structured` for forced tool use — note: thinking is incompatible with forced tool use, so `call_structured` omits it).
- `tools/` — deterministic Python tools used by agents. `validate.py` runs the exec sandbox + geometry + printability checks for one part. `export.py` writes STLs and returns bounding-box metadata.
- `prompts/` — one system prompt per agent, plus the Designer/Critic tool schemas.
- `app.py` — thin FastAPI shim. `/generate` returns single-part STL downloads; `/generate-assembly` returns a JSON manifest with the Designer spec, Critic verdict, iteration count, and per-part code/bbox/STL paths.
- `outputs/` — gitignored, all STLs land here.

Two feedback loops:
- **Inner** (per-part) — Generator ↔ validator, retries up to 4 times on errors. Same idea as the original retry loop, now scoped to one part.
- **Outer** (whole assembly) — Critic flags missed requirements → Designer revises spec → only affected parts are regenerated. Capped at 2 iterations. Single-part designs skip the Critic.

Backend is Anthropic-only (the agent architecture leans on reliable tool use which 7b local models can't deliver). Config from `.env` via `python-dotenv`, loaded in `agents/_client.py`. `.env.example` is the committed template.

## Conventions

- No frontend — API only.
- Don't add a Makefile or other wrapper tooling unless asked; the repo is small enough that raw commands are clearer.
- Prefer editing existing files over adding new ones.
- Each agent's prompt lives in `prompts/<agent>.py` — keep them focused on that agent's job. Don't mix concerns across prompts.
