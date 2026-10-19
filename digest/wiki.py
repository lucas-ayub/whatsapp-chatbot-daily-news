"""Reads the Portuguese Wikipedia page of a calendar day (e.g. '19 de outubro').

That page has the two lists we need: "Eventos" (historical events) and
"Feriados e eventos cíclicos" (commemorative dates).
"""
import re
from datetime import date
from functools import lru_cache

from digest.utils import MONTHS, get

RAW_URL = "https://pt.wikipedia.org/w/index.php"
HEADING = re.compile(r"^(={2,6})\s*(.*?)\s*\1\s*$")
BULLET = re.compile(r"^(\*+)\s*(.*)$")
YEAR_TEXT = re.compile(r"^(\d{1,4}(?:\s*a\.\s*C\.)?)\s*(?:[—–-]|:)\s*(.+)$")
YEAR_ONLY = re.compile(r"^(\d{1,4}(?:\s*a\.\s*C\.)?)\s*:?\s*$")


def page_title(d: date) -> str:
    return f"{d.day} de {MONTHS[d.month - 1].lower()}"


@lru_cache(maxsize=8)
def fetch_day_page(d: date) -> str:
    title = page_title(d)
    for _ in range(3):  # follow up to 2 redirects
        text = get(RAW_URL, params={"title": title, "action": "raw"}).text
        m = re.match(r"#(?:REDIRECIONAMENTO|REDIRECT)\s*\[\[([^\]|#]+)", text, re.I)
        if not m:
            return text
        title = m.group(1).strip()
    raise RuntimeError(f"Too many redirects for {page_title(d)}")


# ---------------------------------------------------------------- cleaning

def _strip_templates(s: str) -> str:
    # remove {{...}} including nested ones, innermost first
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    return s


def clean(s: str) -> str:
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"<ref[^>]*/>", "", s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = _strip_templates(s)
    s = re.sub(r"\[\[(?:Ficheiro|Arquivo|Imagem|File|Image):[^\]]*\]\]", "", s, flags=re.I)
    s = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", s)   # [[target|label]] -> label
    s = re.sub(r"\[\[([^\]]*)\]\]", r"\1", s)            # [[target]] -> target
    s = re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\1", s)  # [url label] -> label
    s = re.sub(r"\[https?://\S+\]", "", s)
    s = re.sub(r"'{2,}", "", s)                          # bold / italic
    s = re.sub(r"<[^>]+>", "", s)                        # leftover html tags
    s = s.replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------- sections

def sections(wikitext: str) -> list[tuple[int, str, list[str]]]:
    """Split into (level, heading, lines). Text before the first heading is skipped."""
    out: list[tuple[int, str, list[str]]] = []
    for line in wikitext.splitlines():
        m = HEADING.match(line.strip())
        if m:
            out.append((len(m.group(1)), clean(m.group(2)), []))
        elif out:
            out[-1][2].append(line)
    return out


def _section_tree(wikitext: str, match) -> list[tuple[str, list[str]]]:
    """Return [(subheading, lines)] for the level-2 section whose title satisfies `match`."""
    result: list[tuple[str, list[str]]] = []
    inside = False
    for level, title, lines in sections(wikitext):
        if level == 2:
            inside = match(title.lower())
            if inside:
                result.append(("", lines))
        elif inside:
            result.append((title, lines))
    return result


def events(wikitext: str) -> list[tuple[str, str]]:
    """[('1947', 'Chuck Yeager quebra a barreira do som...'), ...] in page order."""
    out: list[tuple[str, str]] = []
    for _, lines in _section_tree(wikitext, lambda t: t.startswith("eventos")):
        current_year = None
        for line in lines:
            b = BULLET.match(line.strip())
            if not b:
                continue
            depth, body = len(b.group(1)), clean(b.group(2))
            if not body:
                continue
            m = YEAR_TEXT.match(body)
            if depth == 1 and m:
                current_year = None
                out.append((m.group(1), m.group(2).strip()))
            elif depth == 1 and YEAR_ONLY.match(body):
                current_year = YEAR_ONLY.match(body).group(1)
            elif depth > 1 and current_year:
                out.append((current_year, body))
    return out


SKIP_SUBSECTIONS = ("cristianismo", "igreja", "santos", "religi", "calendário")
SKIP_ITEMS = ("aniversário do município", "aniversário da cidade", "no calendário")


def commemorations(wikitext: str) -> list[str]:
    """Commemorative dates listed in 'Feriados e eventos cíclicos'."""
    out: list[str] = []
    tree = _section_tree(wikitext, lambda t: "feriado" in t or "cíclico" in t or "celebra" in t)
    for sub, lines in tree:
        if any(k in sub.lower() for k in SKIP_SUBSECTIONS):
            continue
        for line in lines:
            b = BULLET.match(line.strip())
            if not b:
                continue
            item = clean(b.group(2)).rstrip(".;")
            if item and not any(k in item.lower() for k in SKIP_ITEMS) and item not in out:
                out.append(item)
    return out
