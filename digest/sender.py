"""Sends text to your own WhatsApp via CallMeBot (https://www.callmebot.com)."""
import logging
import os
import re
import time
import unicodedata

import requests

from digest import config
from digest.utils import USER_AGENT

log = logging.getLogger(__name__)
DEFAULT_CALLMEBOT_URL = "https://api.callmebot.com/whatsapp.php"


def callmebot_url() -> str:
    """Same API through a relay (e.g. a Cloudflare Worker) if CallMeBot blocks the runner's IP."""
    return os.getenv("CALLMEBOT_URL") or DEFAULT_CALLMEBOT_URL


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


class Forbidden(RuntimeError):
    """CallMeBot's web server refused the request (HTTP 403)."""


MIN_PIECE_CHARS = 150  # below this, a 403 can't be about message size


def _send_one(text: str, phone: str, apikey: str, attempts: int = 3) -> None:
    for attempt in range(1, attempts + 1):
        try:
            # Identify the project: CallMeBot's Apache answers 403 to some library User-Agents.
            resp = requests.get(callmebot_url(), params={"phone": phone, "text": text, "apikey": apikey},
                                headers={"User-Agent": USER_AGENT}, timeout=60)
            body = " ".join(re.sub(r"<[^>]+>", " ", resp.text).split())
            if resp.status_code == 403:  # retrying the same request won't help
                raise Forbidden(f"CallMeBot answered 403: {body[:200]}")
            if resp.status_code < 400 and not re.search(r"\bERROR\b|invalid|not\s+allowed|too\s+many\s+requests|too\s+often", body, re.I):
                return
            raise RuntimeError(f"CallMeBot answered {resp.status_code}: {body[:200]}")
        except Forbidden:
            raise
        except (requests.RequestException, RuntimeError):
            if attempt == attempts:
                raise
            log.warning("Send attempt %d failed, retrying", attempt, exc_info=True)
            time.sleep(10 * attempt)


def _strip_markup(t: str) -> str:
    return re.sub(r"[*_~]", "", t)


def _strip_emoji(t: str) -> str:
    return "".join(c for c in t if not (ord(c) > 0xFFFF or unicodedata.category(c) in ("So", "Sk", "Cf")
                                        or 0xFE00 <= ord(c) <= 0xFE0F))


def _ascii(t: str) -> str:
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()


VARIANTS = [("sem *", _strip_markup), ("sem emoji", _strip_emoji), ("so ASCII", _ascii)]
_diagnosed = False


def _diagnose(text: str, phone: str, apikey: str) -> None:
    """Find out what CallMeBot refuses, logging it; runs once per process.

    Sends a plain canary, then each line of `text` on its own, then cleaned-up
    variants of every refused line. Results go to the log (WARNING level).
    """
    global _diagnosed
    if _diagnosed:
        return
    _diagnosed = True

    def attempt(label: str, t: str) -> bool:
        time.sleep(config.SECONDS_BETWEEN_MESSAGES)
        try:
            _send_one(t, phone, apikey, attempts=1)
            log.warning("DIAGNOSE %-10s OK      %r", label, t)
            return True
        except Exception as e:
            log.warning("DIAGNOSE %-10s REFUSED %r (%s)", label, t, str(e)[:60])
            return False

    if not attempt("canary", "teste de conexao do bot (diagnostico)"):
        log.warning("DIAGNOSE result: even plain ASCII is refused -> the server blocks this origin")
        return
    for line in [l for l in text.split("\n") if l.strip()]:
        if attempt("line", line):
            continue
        for label, fn in VARIANTS:
            variant = fn(line).strip()
            if variant and variant != line and attempt(label, variant):
                break
    log.warning("DIAGNOSE done")


def _send_adaptive(text: str, phone: str, apikey: str) -> int:
    """Send `text`; if CallMeBot refuses it (403), resend it in smaller pieces.

    Returns how many WhatsApp messages were sent. If even a short piece is refused,
    runs a one-off diagnosis (see _diagnose) and raises Forbidden.
    """
    try:
        _send_one(text, phone, apikey)
        return 1
    except Forbidden:
        if len(text) <= MIN_PIECE_CHARS:
            _diagnose(text, phone, apikey)
            raise Forbidden(
                f"CallMeBot refused even a {len(text)}-character message; see the DIAGNOSE lines "
                "above for what it accepts.")
    pieces = split_message(text, max(MIN_PIECE_CHARS, len(text) // 2))
    if len(pieces) < 2:  # can't be split on line boundaries: cut it
        half = len(text) // 2
        pieces = [text[:half], text[half:]]
    log.warning("CallMeBot refused a %d-char message; resending it as %d smaller ones",
                len(text), len(pieces))
    sent = 0
    for piece in pieces:
        if sent:
            time.sleep(config.SECONDS_BETWEEN_MESSAGES)
        sent += _send_adaptive(piece, phone, apikey)
    return sent


def send_whatsapp(text: str) -> None:
    """Send `text` to your number via CallMeBot. Reads phone and API key from the environment."""
    phone = os.getenv("CALLMEBOT_PHONE")
    apikey = os.getenv("CALLMEBOT_APIKEY")
    if not phone or not apikey:
        raise RuntimeError("Set CALLMEBOT_PHONE and CALLMEBOT_APIKEY (in .env or GitHub Secrets).")
    chunks = split_message(text, config.MAX_CHARS_PER_MESSAGE)
    for i, chunk in enumerate(chunks, 1):
        n = _send_adaptive(chunk, phone, apikey)
        log.info("Sent part %d/%d (%d chars, %d message(s))", i, len(chunks), len(chunk), n)
        if i < len(chunks):
            time.sleep(config.SECONDS_BETWEEN_MESSAGES)
