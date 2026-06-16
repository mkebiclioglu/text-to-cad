"""Generator agent: one part spec -> validated CadQuery shape.

Owns the inner feedback loop: code generation -> validator -> retry-with-error
up to MAX_RETRIES times. Each Generator call deals with exactly one part, so
the context window stays small and the model is less likely to skip details.
"""

import json
import re

from agents._client import call_text
from prompts.generator import EXAMPLES, SYSTEM_PROMPT
from tools.validate import validate_single_part

MAX_RETRIES = 4


class GeneratorError(ValueError):
    pass


def generate_part(part: dict, global_dims: dict) -> tuple[str, object, list[str]]:
    """
    Returns (code, shape, warnings).
    Raises GeneratorError if all retries are exhausted.
    """
    user_msg = _format_part_request(part, global_dims)

    messages = list(EXAMPLES)
    messages.append({"role": "user", "content": user_msg})

    last_error = None

    for attempt in range(MAX_RETRIES):
        assistant_text = call_text(
            role=f"generator[{part['name']}]",
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": assistant_text})

        code = _extract_code(assistant_text)
        shape, error, warnings = validate_single_part(code)

        if shape is not None:
            return code, shape, warnings

        last_error = error
        if attempt < MAX_RETRIES - 1:
            messages.append({
                "role": "user",
                "content": (
                    f"That code failed validation:\n{error}\n\n"
                    "Return only the corrected code block. Re-read the part spec above "
                    "and make sure every dimension uses the values listed there."
                ),
            })

    raise GeneratorError(
        f"Generator failed for part '{part['name']}' after {MAX_RETRIES} attempts. "
        f"Last error: {last_error}"
    )


def _format_part_request(part: dict, global_dims: dict) -> str:
    consumed = {k: global_dims[k] for k in part.get("shared_dims_used", []) if k in global_dims}
    lines = [
        "Part spec:",
        f"- name: {part['name']}",
        f"- description: {part['description']}",
        f"- geometry hint: {part.get('geometry_hint', 'custom')}",
        f"- qty: {part['qty']}",
        f"- print notes: {part['print_notes']}",
        f"- specific dimensions (mm): {json.dumps(part['specific_dims'])}",
        f"- shared dimensions used (mm): {json.dumps(consumed)}",
    ]
    if part.get("interfaces"):
        lines.append(f"- interfaces with other parts: {', '.join(part['interfaces'])}")
    return "\n".join(lines)


def _extract_code(text: str) -> str:
    match = re.search(r"```python\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()
