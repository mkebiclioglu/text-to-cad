"""Critic agent: review generated assembly against original user request."""

import json

from agents._client import call_structured
from prompts.critic import CRITIC_TOOL, SYSTEM_PROMPT


def review(
    user_request: str,
    spec: dict,
    part_summaries: list[dict],
) -> dict:
    """
    part_summaries: one dict per generated part with keys
    {name, qty, print_notes, bbox_mm, triangle_count, warnings}.

    Returns the validated dict matching CRITIC_TOOL.input_schema.
    """
    message = (
        f"Original user request:\n{user_request}\n\n"
        f"Designer's spec:\n{json.dumps(spec, indent=2)}\n\n"
        f"Generated parts (actual geometry):\n{json.dumps(part_summaries, indent=2)}"
    )

    return call_structured(
        role="critic",
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": message}],
        tool=CRITIC_TOOL,
    )
