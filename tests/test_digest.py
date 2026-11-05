"""Offline tests: no network, all external data is faked."""
from datetime import date, datetime, timezone

from digest import main, sender, wiki
from digest.sections import football, header, history, indicators
from digest.utils import br_number, pct

WIKITEXT = """{{Calendário}}
'''19 de outubro''' é o 292.º dia do ano.

== Eventos ==
* [[202 a.C.]] — [[Batalha de Zama]]: vitória romana.<ref>Fonte</ref>
=== Século XX ===
* [[1947]] — [[Chuck Yeager]] quebra a [[barreira do som]] no [[Bell X-1]].
* [[1962]]:
** Começa a [[Crise dos mísseis de Cuba|Crise dos Mísseis]].
** Outro fato do mesmo ano.
* [[2024]] – A sonda ''[[Europa Clipper]]'' é lançada.{{Carece de fontes|data=2024}}

== Nascimentos ==
* [[1900]] — Alguém nasce.

== Feriados e eventos cíclicos ==
* [[Dia do Profissional de Informática|Dia do Profissional de TI]]
* Dia do [[Piauí]]
* Aniversário do município de [[Ijuí]]
=== Cristianismo ===
* [[São Paulo da Cruz]]
* No calendário romano era o 14.º dia antes das calendas de novembro.
"""


def test_header():
    assert header.date_header(date(2026, 10, 14)) == "✅ Dia 14 de Outubro de 2026, Quarta-Feira"
    assert header.date_header(date(2026, 3, 1)).endswith("Março de 2026, Domingo")


def test_number_formatting():
    assert br_number(206887.4, 0) == "206.887"
    assert br_number(419224, 2) == "419.224,00"
    assert pct(0.71) == "⬆️ 0,71%"
    assert pct(-1.04) == "⬇️ 1,04%"


def test_wiki_events():
    ev = wiki.events(WIKITEXT)
    assert ev[0] == ("202 a.C.", "Batalha de Zama: vitória romana.")
    assert ("1947", "Chuck Yeager quebra a barreira do som no Bell X-1.") in ev
    assert ("1962", "Começa a Crise dos Mísseis.") in ev
    assert ("2024", "A sonda Europa Clipper é lançada.") in ev
    assert not any("nasce" in t for _, t in ev)


def test_wiki_commemorations():
    assert wiki.commemorations(WIKITEXT) == ["Dia do Profissional de TI", "Dia do Piauí"]


def test_history_fallback_without_ai(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(wiki, "fetch_day_page", lambda d: WIKITEXT)
    text = history.historical_events(date(2026, 10, 19))
    assert text.startswith("🌍 *EVENTOS HISTÓRICOS DO DIA*")
    assert "-1947: Chuck Yeager" in text
    assert "202 a.C." not in text  # fallback prefers modern events


def test_bcb_lines():
    monthly = [(date(2026, 8, 1), 0.31), (date(2026, 9, 1), 0.82)]
    assert indicators.monthly_line("IPCA", monthly) == "💲IPCA ⬆️ 0,82% Setembro de 2026"
    selic = [(date(2026, 7, 1), 14.25), (date(2026, 9, 16), 13.75), (date(2026, 10, 19), 13.75)]
    assert indicators.selic_line(selic) == "💲SELIC ⬇️ 13,75% 16 de Setembro de 2026"


ESPN = {"events": [
    {"id": "1", "date": "2026-10-19T00:30Z",  # 21h30 of the 18th in Brazil
     "status": {"type": {"state": "post", "completed": True}},
     "competitions": [{"notes": [{"headline": "Semifinal - Ida"}], "competitors": [
         {"homeAway": "home", "score": "0", "team": {"displayName": "Boca Juniors"}},
         {"homeAway": "away", "score": "1", "team": {"displayName": "Vasco da Gama"}}]}]},
    {"id": "2", "date": "2026-10-19T22:00Z",
     "status": {"type": {"state": "pre", "completed": False}},
     "competitions": [{"competitors": [
         {"homeAway": "home", "score": "0", "team": {"displayName": "Fluminense"}},
         {"homeAway": "away", "score": "0", "team": {"displayName": "Palmeiras"}}]}]},
]}


def test_football(monkeypatch):
    games = football.parse_events(ESPN, "Copa Sul-Americana")
    monkeypatch.setattr(football, "all_games", lambda d: tuple(games))
    d = date(2026, 10, 19)
    assert football.football_results(d) == (
        "⚽ *Copa Sul-Americana*\nSemifinal - Ida:\nBoca Juniors 0x1 Vasco da Gama")
    assert football.football_today(d) == (
        "🔥 *Jogos de Hoje*\n\n🏆 Copa Sul-Americana\n⏰ 19h00 Fluminense x Palmeiras")


def test_split_message():
    text = "\n\n".join(["a" * 600, "b" * 600, "c" * 600, "d\n" * 900])
    chunks = sender.split_message(text, 1500)
    assert all(len(c) <= 1500 for c in chunks)
    assert "".join(chunks).replace("\n", "") == text.replace("\n", "")


def test_split_never_orphans_a_title():
    text = "x" * 1400 + "\n\n🌍📰 *NOTÍCIAS INTERNACIONAIS*\n\n" + "y" * 200
    chunks = sender.split_message(text, 1500)
    assert chunks[0] == "x" * 1400
    assert chunks[1].startswith("🌍📰 *NOTÍCIAS INTERNACIONAIS*\n\ny")


def test_schedule_gate():
    utc = timezone.utc
    # winter (CET, UTC+1): 05:55 UTC is 06:55 local -> too early; 06:55 UTC sends
    assert not main.should_send_now(datetime(2026, 12, 1, 5, 55, tzinfo=utc))
    assert main.should_send_now(datetime(2026, 12, 1, 6, 55, tzinfo=utc))
    # summer (CEST, UTC+2): 05:55 UTC is 07:55 local -> sends
    assert main.should_send_now(datetime(2026, 7, 1, 5, 55, tzinfo=utc))
    # GitHub hours late: still sends (once a day is enforced by the workflow)
    assert main.should_send_now(datetime(2026, 11, 5, 13, 40, tzinfo=utc))
    # too late in the evening: skip
    assert not main.should_send_now(datetime(2026, 11, 5, 21, 30, tzinfo=utc))


def test_failing_section_is_skipped(monkeypatch):
    def boom(d):
        raise RuntimeError("API down")
    monkeypatch.setattr(main, "SECTIONS", [header.date_header, boom])
    msg = main.build_message(date(2026, 10, 14))
    assert msg == "✅ Dia 14 de Outubro de 2026, Quarta-Feira\n\nBom Dia!!! 😉"


# --- news ---------------------------------------------------------------
from digest import llm
from digest.sections import news


def _fake_candidates():
    def item(i, cat):
        return {"title": f"{cat} headline {i}", "summary": "s", "source": "src",
                "link": f"https://example.com/{cat}/{i}", "ts": 0}
    return {cat: [item(i, cat) for i in range(1, 4)] for cat in news.config.NEWS_FEEDS}


def test_clean_link_drops_tracking():
    assert news.clean_link("https://x.com/a?id=3&utm_source=rss#top") == "https://x.com/a?id=3"


def test_news_links_attached_by_index(monkeypatch):
    news.curated_news.cache_clear()
    cands = _fake_candidates()
    monkeypatch.setattr(news, "fetch_category", lambda urls, _c=iter(cands.values()): next(_c))
    monkeypatch.setattr(llm, "available", lambda: True)
    answer = {
        "startups": [{"n": 2, "titulo": "🚀 Startup X levanta US$ 10 mi", "resumo": "Contexto."},
                     {"n": 99, "titulo": "índice inválido"}],
        "geopolitica": [{"n": 1, "titulo": "🌍 Cúpula", "resumo": "Atores."}],
        "nacionais": [{"n": 3, "titulo": "🇧🇷 Fato", "resumo": "não deve aparecer"}],
        "ideia_do_dia": {"n": 1, "texto": "Ideia boa."},
    }
    monkeypatch.setattr(llm, "ask_json", lambda system, prompt, max_tokens=0: answer)
    d = date(2026, 10, 24)
    startups = news.startup_news(d)
    assert "*🚀 Startup X levanta US$ 10 mi*\nContexto.\n🔗 https://example.com/startups/2" in startups
    assert "inválido" not in startups
    assert "🔗 https://example.com/geopolitica/1" in news.geopolitics_news(d)
    assert news.national_news(d).endswith("🇧🇷 Fato\n🔗 https://example.com/nacionais/3")
    assert "Ideia boa.\n🔗 https://example.com/startups/1" in news.idea_of_the_day(d)
    assert news.science_news(d) is None
    news.curated_news.cache_clear()


def test_news_fallback_without_ai(monkeypatch):
    news.curated_news.cache_clear()
    monkeypatch.setattr(news, "fetch_category", lambda urls: _fake_candidates()["startups"])
    monkeypatch.setattr(llm, "available", lambda: False)
    text = news.startup_news(date(2026, 10, 24))
    assert "• startups headline 1\n🔗 https://example.com/startups/1" in text
    assert news.idea_of_the_day(date(2026, 10, 24)) is None
    news.curated_news.cache_clear()


# --- markets / football fallbacks -------------------------------------
from digest.sections import markets


def test_bitcoin_falls_back_to_usd_times_brl(monkeypatch):
    def down():
        raise RuntimeError("429")
    monkeypatch.setattr(markets, "awesome_quotes", down)
    monkeypatch.setattr(markets, "yahoo_closes",
                        lambda: {"BTC-USD": (100000.0, 100000.0), "BRL=X": (5.5, 5.0)})
    assert markets.currency_line("BTC") == "🪙 Bitcoin ⬆️ 10,00% R$ 550.000,00"


def test_football_queries_each_day_and_dedups(monkeypatch):
    calls = []

    def fake_get_json(url, params):
        calls.append(params)
        return ESPN  # same two games every day -> must be de-duplicated

    football.all_games.cache_clear()
    monkeypatch.setattr(football, "get_json", fake_get_json)
    monkeypatch.setattr(football.config, "LEAGUES", [{"slug": "x", "name": "Copa Sul-Americana"}])
    games = football.all_games(date(2026, 10, 19))
    football.all_games.cache_clear()
    assert [p["dates"] for p in calls] == ["20261017", "20261018", "20261019", "20261020"]
    assert len(games) == 2


def test_clean_link_unwraps_folha_redirect():
    url = "https://redir.folha.com.br/redir/online/emcimadahora/rss091/*https://www1.folha.uol.com.br/poder/x.shtml"
    assert news.clean_link(url) == "https://www1.folha.uol.com.br/poder/x.shtml"
