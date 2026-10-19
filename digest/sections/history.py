"""EVENTOS HISTÓRICOS DO DIA, from the Portuguese Wikipedia day page.

Claude picks the most interesting events; without an API key a spread of
modern events is chosen automatically.
"""
import logging
import re
from datetime import date

from digest import config, llm, wiki

log = logging.getLogger(__name__)

SYSTEM = """Você seleciona efemérides para um resumo diário em português do Brasil, lido por um \
engenheiro interessado em ciência, espaço, tecnologia, história do Brasil e geopolítica.
Da lista fornecida, escolha os eventos mais marcantes e variados (prefira os séculos XIX a XXI, \
mas inclua algo mais antigo se for muito relevante) e reescreva cada um em UMA frase clara de \
até 30 palavras, explicando quem é a pessoa ou o que é a coisa quando ajudar. Use apenas as \
informações fornecidas. Mantenha a ordem cronológica. Responda somente com JSON no formato \
{"eventos": [{"ano": "1947", "texto": "..."}]}."""


def _year_value(year: str) -> int:
    n = int(re.match(r"\d+", year).group())
    return -n if "a" in year.lower() else n


def fallback_pick(events: list[tuple[str, str]], n: int) -> list[tuple[str, str]]:
    modern = [e for e in events if _year_value(e[0]) >= 1800] or events
    if len(modern) <= n:
        return modern
    step = len(modern) / n
    return [modern[int(i * step)] for i in range(n)]


def pick_events(events: list[tuple[str, str]], n: int) -> list[tuple[str, str]]:
    if llm.available():
        try:
            listing = "\n".join(f"{y} — {t}" for y, t in events)
            answer = llm.ask_json(SYSTEM, f"Escolha {n} eventos:\n\n{listing}")
            picked = [(str(e["ano"]), str(e["texto"]).strip()) for e in answer["eventos"]]
            if picked:
                return picked[:n]
        except Exception:
            log.exception("AI selection of historical events failed")
    return fallback_pick(events, n)


def historical_events(d: date) -> str | None:
    events = wiki.events(wiki.fetch_day_page(d))
    if not events:
        return None
    picked = pick_events(events, config.HISTORY_COUNT)
    lines = [f"-{year}: {text}" for year, text in picked]
    return "🌍 *EVENTOS HISTÓRICOS DO DIA*\n\n" + "\n\n".join(lines)
