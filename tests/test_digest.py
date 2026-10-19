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
    summer = datetime(2026, 7, 1, 6, 10, tzinfo=timezone.utc)
    winter = datetime(2026, 12, 1, 7, 20, tzinfo=timezone.utc)
    assert main.should_send_now("55 5 * * *", summer)
    assert not main.should_send_now("55 6 * * *", summer)
    assert main.should_send_now("55 6 * * *", winter)
    assert not main.should_send_now("55 5 * * *", winter)


def test_failing_section_is_skipped(monkeypatch):
    def boom(d):
        raise RuntimeError("API down")
    monkeypatch.setattr(main, "SECTIONS", [header.date_header, boom])
    msg = main.build_message(date(2026, 10, 14))
    assert msg == "✅ Dia 14 de Outubro de 2026, Quarta-Feira\n\nBom Dia!!! 😉"
