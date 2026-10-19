"""Thin wrapper around the Anthropic API that returns parsed JSON."""
import json
import logging
import os

from digest import config

log = logging.getLogger(__name__)


def available() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def ask_json(system: str, prompt: str, max_tokens: int = 3000) -> dict:
    """Send a prompt and parse the first JSON object in the answer."""
    import anthropic  # imported lazily so the bot still runs without the package/key

    client = anthropic.Anthropic()
    model = os.getenv("ANTHROPIC_MODEL") or config.ANTHROPIC_MODEL
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in msg.content if block.type == "text")
    return extract_json(text)


def extract_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"No JSON object in model answer: {text[:200]!r}")
    return json.loads(text[start:end + 1])
