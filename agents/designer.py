"""Designer agent: vague description -> structured engineering spec."""

import json

from agents._client import call_structured
from prompts.designer import DESIGN_TOOL, SYSTEM_PROMPT


def design(description: str, critique: dict | None = None, prior_spec: dict | None = None) -> dict:
    """
    First pass: design(description) -> spec.
    Revision pass: design(description, critique, prior_spec) -> revised spec.

    Returns the validated dict matching DESIGN_TOOL.input_schema.
    """
    user_blocks = [f"User request:\n{description}"]

    if critique is not None and prior_spec is not None:
        user_blocks.append(
            "Your previous spec was reviewed and needs revision.\n\n"
            f"Previous spec:\n{json.dumps(prior_spec, indent=2)}\n\n"
            f"Critique:\n{json.dumps(critique, indent=2)}\n\n"
            "Produce a revised spec applying the fixes. Keep parts that weren't flagged "
            "unchanged. Apply the named instructions to the flagged parts."
        )

    messages = [{"role": "user", "content": "\n\n".join(user_blocks)}]

    return call_structured(
        role="designer",
        system=SYSTEM_PROMPT,
        messages=messages,
        tool=DESIGN_TOOL,
    )
