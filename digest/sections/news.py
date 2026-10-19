"""News sections: RSS headlines, curated and rewritten by Claude.

Without ANTHROPIC_API_KEY the bot falls back to the latest headlines per category.
"""
import calendar
import html
import logging
import re
import time
from datetime import date
from functools import lru_cache

import feedparser

from digest import config, llm
from digest.utils import get

log = logging.getLogger(__name__)

TITLES = {
    "nacionais": "🇧🇷📰 *NOTÍCIAS NACIONAIS*",
    "ciencia_tecnologia": "🔬 *CIÊNCIA E TECNOLOGIA*",
    "internacionais": "🌍📰 *NOTÍCIAS INTERNACIONAIS*",
}
MAX_CANDIDATES = 45

SYSTEM = """Você é o editor de um resumo diário de notícias enviado por WhatsApp a um leitor brasileiro, \
engenheiro e pesquisador, interessado em geopolítica, economia, ciência, espaço e empresas de tecnologia.
Escolha as notícias mais relevantes e reescreva cada uma como UMA linha em português do Brasil:
- comece com 1 ou 2 emojis (bandeira do país envolvido quando fizer sentido, ou um emoji do tema);
- uma frase informativa de 15 a 35 palavras, com o fato principal e o detalhe mais importante;
- tom neutro e factual, sem sensacionalismo, sem opinião;
- use APENAS informações presentes nas manchetes/resumos fornecidos; nunca invente números ou fatos;
- notícias em inglês devem ser traduzidas;
- não repita a mesma notícia em duas categorias e evite notícias quase iguais;
- prefira fatos de impacto (política, economia, conflitos, diplomacia, descobertas, lançamentos, \
resultados e movimentos de grandes empresas) a fofocas, crimes locais e curiosidades.
Exemplos do estilo esperado:
🇦🇷🇬🇧 Milei aciona o Tribunal Internacional do Direito do Mar para tentar suspender a exploração de petróleo do Reino Unido perto das Malvinas
🔴 Rover Perseverance, da Nasa, bate recorde de distância em Marte, com mais de 45 km percorridos, superando a marca do Opportunity
Responda somente com JSON."""


def _plain(s: str, limit: int = 280) -> str:
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit]


def fetch_category(urls: list[str]) -> list[dict]:
    now = time.time()
    seen, items = set(), []
    for url in urls:
        try:
            feed = feedparser.parse(get(url).content)
        except Exception:
            log.warning("Feed failed: %s", url, exc_info=True)
            continue
        source = _plain(feed.feed.get("title", url), 60)
        for e in feed.entries:
            title = _plain(e.get("title", ""), 200)
            key = title.lower()
            if not title or key in seen:
                continue
            published = e.get("published_parsed") or e.get("updated_parsed")
            ts = calendar.timegm(published) if published else now
            if now - ts > config.NEWS_MAX_AGE_HOURS * 3600:
                continue
            seen.add(key)
            items.append({"title": title, "summary": _plain(e.get("summary", "")),
                          "source": source, "ts": ts})
    items.sort(key=lambda i: i["ts"], reverse=True)
    return items[:MAX_CANDIDATES]


def build_prompt(candidates: dict[str, list[dict]]) -> str:
    parts = []
    for cat, items in candidates.items():
        parts.append(f"### Categoria: {cat} (escolha até {config.NEWS_COUNT[cat]})")
        for i, it in enumerate(items, 1):
            parts.append(f"{i}. [{it['source']}] {it['title']} — {it['summary']}")
        parts.append("")
    keys = ", ".join(f'"{c}": ["linha", ...]' for c in candidates)
    parts.append(f"Formato da resposta: {{{keys}}}")
    return "\n".join(parts)


@lru_cache(maxsize=2)
def curated_news(d: date) -> dict[str, list[str]]:
    candidates = {cat: fetch_category(urls) for cat, urls in config.NEWS_FEEDS.items()}
    if llm.available() and any(candidates.values()):
        try:
            answer = llm.ask_json(SYSTEM, build_prompt(candidates))
            return {cat: [str(x).strip() for x in answer.get(cat, []) if str(x).strip()]
                    for cat in candidates}
        except Exception:
            log.exception("AI curation failed, falling back to raw headlines")
    return {cat: [f"• {it['title']}" for it in items[:config.NEWS_COUNT[cat]]]
            for cat, items in candidates.items()}


def _section(cat: str, d: date) -> str | None:
    lines = curated_news(d).get(cat) or []
    if not lines:
        return None
    return TITLES[cat] + "\n\n" + "\n\n".join(lines)


def national_news(d: date) -> str | None:
    return _section("nacionais", d)


def science_tech_news(d: date) -> str | None:
    return _section("ciencia_tecnologia", d)


def international_news(d: date) -> str | None:
    return _section("internacionais", d)
