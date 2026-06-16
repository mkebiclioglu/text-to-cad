"""Shared Anthropic client used by every agent.

Two entry points:
- `call_text(role, system, messages)` for free-form text (the Generator's
  CadQuery output, with adaptive thinking and large enough max_tokens to fit
  thinking + code).
- `call_structured(role, system, messages, tool)` for guaranteed-JSON output
  via forced tool use (the Designer and Critic). The model MUST emit a
  tool_use block matching the schema, so callers get a validated dict back.

The `role` argument is for diagnostics only — it's woven into error messages
so when something fails, the traceback names which agent broke.
"""

import os
from functools import lru_cache

import anthropic
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-7")
MAX_TOKENS = 16000


@lru_cache(maxsize=1)
def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def call_text(role: str, system: str, messages: list[dict]) -> str:
    """Return the model's text response. Used by the Generator for CadQuery code."""
    response = _client().messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=MAX_TOKENS,
        thinking={"type": "adaptive"},
        system=system,
        messages=messages,
    )

    for block in response.content:
        if block.type == "text":
            return block.text

    raise ValueError(
        f"[{role}] Anthropic response contained no text block "
        f"(stop_reason={response.stop_reason}). "
        "Likely ran out of tokens during thinking — simplify the input."
    )


def call_structured(
    role: str,
    system: str,
    messages: list[dict],
    tool: dict,
) -> dict:
    """
    Force the model to emit a tool_use block matching `tool`'s schema.
    `tool` must be a dict with keys: name, description, input_schema.
    Returns the tool_use's `input` as a validated dict.
    """
    # Extended thinking is incompatible with forced tool_choice — omit it here.
    response = _client().messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=messages,
        tools=[tool],
        tool_choice={"type": "tool", "name": tool["name"]},
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == tool["name"]:
            return dict(block.input)

    raise ValueError(
        f"[{role}] Anthropic response had no '{tool['name']}' tool_use block "
        f"(stop_reason={response.stop_reason})."
    )
