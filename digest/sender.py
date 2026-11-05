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


ZWSP = "\u200b"  # zero-width space: invisible in WhatsApp


def waf_safe(text: str) -> str:
    """Defuse CallMeBot's web firewall, which answers 403 when a line break (or ; | ` &)
    is followed by a word that looks like a shell command, e.g. "\\nFC Porto" ("fc" is a
    shell builtin). An invisible zero-width space before the word avoids the match."""
    return re.sub(r"([\n;|`&][ \t]*)(?=[A-Za-z])", lambda m: m.group(1) + ZWSP, text)


def _strip_markup(t: str) -> str:
    return re.sub(r"[*_~]", "", t)


def _strip_emoji(t: str) -> str:
    return "".join(c for c in t if not (ord(c) > 0xFFFF or unicodedata.category(c) in ("So", "Sk", "Cf")
                                        or 0xFE00 <= ord(c) <= 0xFE0F))


def _ascii(t: str) -> str:
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()


VARIANTS = [("original", lambda t: t), ("sem *", _strip_markup),
            ("sem emoji", _strip_emoji), ("so ASCII", _ascii)]


def _send_lines(text: str, phone: str, apikey: str) -> int:
    """Last resort for a short piece CallMeBot refuses: send it line by line, trying
    cleaner variants of each line; skip (and log) lines no variant gets through."""
    sent, skipped = 0, []
    for line in [l for l in text.split("\n") if l.strip()]:
        for label, fn in VARIANTS:
            variant = waf_safe(fn(line).strip())
            if not variant:
                continue
            time.sleep(config.SECONDS_BETWEEN_MESSAGES)
            try:
                _send_one(variant, phone, apikey, attempts=1)
                sent += 1
                if label != "original":
                    log.warning("Line sent only %s: %r", label, line)
                break
            except Forbidden:
                continue
        else:
            skipped.append(line)
    if skipped:
        log.warning("CallMeBot refused these lines in every form; skipped: %r", skipped)
    if not sent:
        raise Forbidden("CallMeBot refused every line, even cleaned up: the server is probably "
                        "blocking this origin. Try CALLMEBOT_URL (relay) or another machine.")
    return sent


def _send_adaptive(text: str, phone: str, apikey: str) -> int:
    """Send `text`; if CallMeBot refuses it (403), resend it in smaller pieces, and
    finally line by line (see _send_lines). Returns how many messages were sent."""
    try:
        _send_one(text, phone, apikey)
        return 1
    except Forbidden:
        if len(text) <= MIN_PIECE_CHARS:
            log.warning("CallMeBot refused a %d-char piece; sending it line by line", len(text))
            return _send_lines(text, phone, apikey)
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


def probe(text: str) -> bool:
    """Send one text as-is and log whether CallMeBot accepted it (for debugging)."""
    phone, apikey = os.getenv("CALLMEBOT_PHONE"), os.getenv("CALLMEBOT_APIKEY")
    try:
        _send_one(text, phone, apikey, attempts=1)
        log.warning("PROBE OK      (%d chars) %r", len(text), text)
        return True
    except Exception as e:
        log.warning("PROBE REFUSED (%d chars) %r: %s", len(text), text, str(e)[:80])
        return False


def send_whatsapp(text: str) -> None:
    """Send `text` to your number via CallMeBot. Reads phone and API key from the environment."""
    phone = os.getenv("CALLMEBOT_PHONE")
    apikey = os.getenv("CALLMEBOT_APIKEY")
    if not phone or not apikey:
        raise RuntimeError("Set CALLMEBOT_PHONE and CALLMEBOT_APIKEY (in .env or GitHub Secrets).")
    chunks = [waf_safe(c) for c in split_message(text, config.MAX_CHARS_PER_MESSAGE)]
    for i, chunk in enumerate(chunks, 1):
        n = _send_adaptive(chunk, phone, apikey)
        log.info("Sent part %d/%d (%d chars, %d message(s))", i, len(chunks), len(chunk), n)
        if i < len(chunks):
            time.sleep(config.SECONDS_BETWEEN_MESSAGES)
