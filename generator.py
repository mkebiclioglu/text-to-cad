import os
import re

from dotenv import load_dotenv

from prompts import SYSTEM_PROMPT, EXAMPLES
from validator import validate

load_dotenv()

MAX_RETRIES = 4

PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")       # "anthropic" or "ollama"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-7")


def _call_llm(messages: list[dict]) -> str:
    if PROVIDER == "anthropic":
        return _call_anthropic(messages)
    return _call_ollama(messages)


def _call_ollama(messages: list[dict]) -> str:
    from openai import OpenAI
    client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
    response = client.chat.completions.create(
        model=OLLAMA_MODEL,
        messages=messages,
        temperature=0.1,
    )
    return response.choices[0].message.content


def _call_anthropic(messages: list[dict]) -> str:
    import anthropic
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user_messages = [m for m in messages if m["role"] != "system"]

    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=system,
        messages=user_messages,
    )
    # adaptive thinking may prepend a thinking block — find the text block
    for block in response.content:
        if block.type == "text":
            return block.text
    return response.content[-1].text


def _extract_code(text: str) -> str:
    match = re.search(r"```python\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def generate_cad(
    description: str,
    history: list[dict] | None = None,
) -> tuple[str, object, list[str], dict[str, dict] | None, list[dict]]:
    """
    Returns (code, cq_result, warnings, parts_meta, updated_history).
    parts_meta is None for single-part results and a dict per part for assemblies.
    Raises ValueError if all retries are exhausted.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(EXAMPLES)

    if history:
        messages.extend(history)

    messages.append({"role": "user", "content": description})

    last_error = None

    for attempt in range(MAX_RETRIES):
        assistant_text = _call_llm(messages)
        messages.append({"role": "assistant", "content": assistant_text})

        code = _extract_code(assistant_text)
        cq_result, error, warnings, parts_meta = validate(code)

        if cq_result is not None:
            user_history = messages[len(EXAMPLES) + 1:]  # strip system + examples
            return code, cq_result, warnings, parts_meta, user_history

        last_error = error
        if attempt < MAX_RETRIES - 1:
            retry_msg = f"That code failed with this error:\n{error}\nPlease fix it and return only the corrected code block."
            messages.append({"role": "user", "content": retry_msg})

    raise ValueError(
        f"Failed to generate valid CadQuery code after {MAX_RETRIES} attempts. "
        f"Last error: {last_error}"
    )
