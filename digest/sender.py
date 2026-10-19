"""Sends text to your own WhatsApp via CallMeBot (https://www.callmebot.com)."""
import logging
import os
import re
import time

import requests

from digest import config

log = logging.getLogger(__name__)
CALLMEBOT_URL = "https://api.callmebot.com/whatsapp.php"


def split_message(text: str, limit: int) -> list[str]:
    """Split on blank lines (section/paragraph boundaries), then on lines if a block is still too long."""
    chunks: list[str] = []
    current = ""
    for block in _attach_titles(text.split("\n\n")):
        pieces = [block] if len(block) <= limit else _split_lines(block, limit)
        for piece in pieces:
            candidate = f"{current}\n\n{piece}" if current else piece
            if len(candidate) <= limit:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = piece
    if current:
        chunks.append(current)
    return chunks


TITLE = re.compile(r"^[^\n*]*\*[^*\n]+\*$")  # e.g. '🌍📰 *NOTÍCIAS INTERNACIONAIS*'


def _attach_titles(blocks: list[str]) -> list[str]:
    """Glue a stand-alone section title to the paragraph after it, so a split never orphans it."""
    out: list[str] = []
    pending = ""
    for block in blocks:
        if TITLE.match(block):
            pending = f"{pending}\n\n{block}" if pending else block
            continue
        out.append(f"{pending}\n\n{block}" if pending else block)
        pending = ""
    if pending:
        out.append(pending)
    return out


def _split_lines(block: str, limit: int) -> list[str]:
    out, current = [], ""
    for line in block.split("\n"):
        while len(line) > limit:  # pathological single line
            out.append(line[:limit])
            line = line[limit:]
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) <= limit:
            current = candidate
        else:
            out.append(current)
            current = line
    if current:
        out.append(current)
    return out


def _send_one(text: str, phone: str, apikey: str, attempts: int = 3) -> None:
    for attempt in range(1, attempts + 1):
        try:
            resp = requests.get(CALLMEBOT_URL, params={"phone": phone, "text": text, "apikey": apikey},
                                timeout=60)
            body = re.sub(r"<[^>]+>", " ", resp.text)
            if resp.status_code < 400 and not re.search(r"\bERROR\b|invalid|not\s+allowed", body, re.I):
                return
            raise RuntimeError(f"CallMeBot answered {resp.status_code}: {' '.join(body.split())[:200]}")
        except (requests.RequestException, RuntimeError):
            if attempt == attempts:
                raise
            log.warning("Send attempt %d failed, retrying", attempt, exc_info=True)
            time.sleep(10 * attempt)


def send_whatsapp(text: str) -> None:
    """Send `text` to your number via CallMeBot. Reads phone and API key from the environment."""
    phone = os.getenv("CALLMEBOT_PHONE")
    apikey = os.getenv("CALLMEBOT_APIKEY")
    if not phone or not apikey:
        raise RuntimeError("Set CALLMEBOT_PHONE and CALLMEBOT_APIKEY (in .env or GitHub Secrets).")
    chunks = split_message(text, config.MAX_CHARS_PER_MESSAGE)
    for i, chunk in enumerate(chunks, 1):
        _send_one(chunk, phone, apikey)
        log.info("Sent part %d/%d (%d chars)", i, len(chunks), len(chunk))
        if i < len(chunks):
            time.sleep(config.SECONDS_BETWEEN_MESSAGES)
