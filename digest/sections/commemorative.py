"""DATAS COMEMORATIVAS: official holidays (holidays lib) + Wikipedia's day page."""
import logging
from datetime import date

import holidays

from digest import wiki

log = logging.getLogger(__name__)
MAX_ITEMS = 6


def holiday_lines(d: date) -> list[str]:
    lines = []
    br = holidays.Brazil(years=d.year, language="pt_BR")
    if d in br:
        lines.append(f"🇧🇷 Feriado nacional: {br[d]}")
    return lines


def commemorative_dates(d: date) -> str | None:
    lines = holiday_lines(d)
    try:
        items = wiki.commemorations(wiki.fetch_day_page(d))
        lines += items[:MAX_ITEMS]
    except Exception:
        log.exception("Could not read commemorative dates from Wikipedia")
    if not lines:
        return None
    return "*DATAS COMEMORATIVAS*\n" + "\n".join(lines)
