"""News sections: RSS headlines curated, summarised and linked by Claude.

The model only returns the *number* of each chosen candidate; the link is attached
here from the feed itself, so URLs are never invented.
Without ANTHROPIC_API_KEY the bot falls back to the latest headlines (with links).
"""
import calendar
import html
import logging
import re
import time
from datetime import date
from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser

from digest import config, llm
from digest.utils import get

log = logging.getLogger(__name__)

TITLES = {
    "nacionais": "🇧🇷📰 *NOTÍCIAS NACIONAIS*",
    "geopolitica": "🌍 *GEOPOLÍTICA E MUNDO*",
    "startups": "🚀 *TECNOLOGIA, STARTUPS E VALE DO SILÍCIO*",
    "ciencia": "🔬 *CIÊNCIA E ESPAÇO*",
}
IDEA_TITLE = "💡 *IDEIA DO DIA*"
IDEA_KEY = "ideia_do_dia"
MAX_CANDIDATES = 45

SYSTEM = """Você é o editor de um resumo diário de notícias enviado por WhatsApp a um leitor brasileiro, \
engenheiro e pesquisador, que quer ficar por dentro de tecnologia de ponta, startups do Vale do Silício, \
boas ideias, geopolítica, economia e ciência.

Para cada categoria você recebe candidatas numeradas. Escolha as mais relevantes e devolva, para cada uma:
- "n": o número da candidata na sua categoria (o link é anexado a partir dele; NUNCA escreva URLs);
- "titulo": 1 ou 2 emojis (bandeira do país quando fizer sentido, ou emoji do tema) + uma frase de \
12 a 30 palavras com o fato principal;
- "resumo": SOMENTE nas categorias marcadas "COM RESUMO": 2 ou 3 frases (40 a 70 palavras) com contexto \
e por que isso importa; nas outras categorias, omita este campo.

Regras:
- português do Brasil; traduza o que estiver em inglês; tom neutro e factual, sem sensacionalismo;
- use APENAS informações das manchetes/resumos fornecidos; nunca invente números, nomes ou fatos;
- não repita a mesma notícia em duas categorias e evite notícias quase iguais;
- "startups": priorize rodadas de investimento relevantes, lançamentos de produtos e modelos de IA, \
movimentos estratégicos de big techs, aquisições, IPOs, tecnologias emergentes e ideias novas; evite \
reviews de gadgets, promoções e listas de compras;
- "geopolitica": priorize conflitos, diplomacia, eleições, sanções, comércio, energia e a relação entre \
grandes potências; no resumo, deixe claro quem são os atores e o que está em jogo;
- nas demais, prefira fatos de impacto a fofocas, crimes locais e curiosidades.

Além disso, em "ideia_do_dia" escolha UMA candidata da categoria startups que traga uma ideia, produto, \
tecnologia ou modelo de negócio especialmente criativo ou promissor (de preferência uma que não esteja na \
lista de startups) e explique em 2 ou 3 frases o que é e por que é interessante: {"n": número, "texto": "..."}.

Exemplo de item:
{"n": 7, "titulo": "🇺🇸🤖 Startup de robótica Figure levanta US$ 1 bilhão para produzir humanoides em escala", \
"resumo": "A rodada ..."}
Responda somente com JSON."""


def _plain(s: str, limit: int = 280) -> str:
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit]


def clean_link(url: str) -> str:
    """Drop tracking parameters (utm_*, etc.) so links stay short."""
    if not url:
        return ""
    url = url.strip()
    if "/*http" in url:  # Folha wraps links in a redirect: .../rss091/*https://www1.folha...
        url = url[url.index("/*http") + 2:]
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith(("utm_", "fbclid", "gclid"))]
    return urlunsplit(parts._replace(query=urlencode(query), fragment=""))


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
                          "source": source, "link": clean_link(e.get("link", "")), "ts": ts})
    items.sort(key=lambda i: i["ts"], reverse=True)
    return items[:MAX_CANDIDATES]


def build_prompt(candidates: dict[str, list[dict]]) -> str:
    parts = []
    for cat, items in candidates.items():
        style = "COM RESUMO" if cat in config.NEWS_WITH_SUMMARY else "só título"
        parts.append(f"### Categoria: {cat} (escolha até {config.NEWS_COUNT[cat]}; {style})")
        for i, it in enumerate(items, 1):
            parts.append(f"{i}. [{it['source']}] {it['title']} — {it['summary']}")
        parts.append("")
    fields = {c: '"n": 1, "titulo": "...", "resumo": "..."' if c in config.NEWS_WITH_SUMMARY
              else '"n": 1, "titulo": "..."' for c in candidates}
    keys = ", ".join(f'"{c}": [{{{fields[c]}}}, ...]' for c in candidates)
    if config.NEWS_IDEA_OF_THE_DAY and "startups" in candidates:
        keys += f', "{IDEA_KEY}": {{"n": 1, "texto": "..."}}'
    parts.append(f"Formato da resposta: {{{keys}}}")
    return "\n".join(parts)


def format_item(title: str, link: str = "", summary: str = "", bold: bool = False) -> str:
    """One news item = one paragraph, so message splitting never separates its link."""
    lines = [f"*{title}*" if bold and summary else title]
    if summary:
        lines.append(summary)
    if link:
        lines.append(f"🔗 {link}")
    return "\n".join(lines)


def _pick(items: list[dict], n) -> dict | None:
    try:
        i = int(n) - 1
    except (TypeError, ValueError):
        return None
    return items[i] if 0 <= i < len(items) else None


def render_answer(answer: dict, candidates: dict[str, list[dict]]) -> dict[str, list[str]]:
    """Turn the model's JSON into ready-to-send paragraphs, attaching links by index."""
    out: dict[str, list[str]] = {}
    used: set[str] = set()
    for cat, items in candidates.items():
        blocks = []
        for entry in answer.get(cat) or []:
            if not isinstance(entry, dict):
                continue
            item = _pick(items, entry.get("n"))
            title = str(entry.get("titulo", "")).strip()
            if not item or not title or item["link"] in used:
                continue
            if item["link"]:
                used.add(item["link"])
            summary = str(entry.get("resumo", "")).strip() if cat in config.NEWS_WITH_SUMMARY else ""
            blocks.append(format_item(title, item["link"], summary, bold=True))
        out[cat] = blocks[:config.NEWS_COUNT[cat]]

    idea = answer.get(IDEA_KEY)
    if config.NEWS_IDEA_OF_THE_DAY and isinstance(idea, dict):
        item = _pick(candidates.get("startups", []), idea.get("n"))
        text = str(idea.get("texto", "")).strip()
        if item and text:
            out[IDEA_KEY] = [format_item(text, item["link"])]
    return out


def fallback(candidates: dict[str, list[dict]]) -> dict[str, list[str]]:
    return {cat: [format_item(f"• {it['title']}", it["link"]) for it in items[:config.NEWS_COUNT[cat]]]
            for cat, items in candidates.items()}


@lru_cache(maxsize=2)
def curated_news(d: date) -> dict[str, list[str]]:
    candidates = {cat: fetch_category(urls) for cat, urls in config.NEWS_FEEDS.items()}
    if llm.available() and any(candidates.values()):
        try:
            answer = llm.ask_json(SYSTEM, build_prompt(candidates), max_tokens=6000)
            return render_answer(answer, candidates)
        except Exception:
            log.exception("AI curation failed, falling back to raw headlines")
    return fallback(candidates)


def _section(key: str, title: str, d: date) -> str | None:
    blocks = curated_news(d).get(key) or []
    if not blocks:
        return None
    return title + "\n\n" + "\n\n".join(blocks)


def national_news(d: date) -> str | None:
    return _section("nacionais", TITLES["nacionais"], d)


def geopolitics_news(d: date) -> str | None:
    return _section("geopolitica", TITLES["geopolitica"], d)


def startup_news(d: date) -> str | None:
    return _section("startups", TITLES["startups"], d)


def idea_of_the_day(d: date) -> str | None:
    return _section(IDEA_KEY, IDEA_TITLE, d)


def science_news(d: date) -> str | None:
    return _section("ciencia", TITLES["ciencia"], d)
