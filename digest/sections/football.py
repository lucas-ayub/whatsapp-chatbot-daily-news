"""Football results (yesterday) and today's games, from ESPN's public scoreboard API.

The API is unofficial (no key, no guarantees): if it changes, these sections
simply disappear from the message instead of breaking it.
"""
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

from digest import config
from digest.utils import get_json

log = logging.getLogger(__name__)
URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard"
BR = ZoneInfo(config.BR_TZ)


@dataclass
class Game:
    league: str
    start: datetime  # Brazilian time
    home: str
    away: str
    home_score: str | None
    away_score: str | None
    state: str        # "pre", "in" or "post"
    completed: bool
    note: str | None  # e.g. "Semifinal - Ida", when ESPN provides it


def _score(competitor: dict) -> str | None:
    s = competitor.get("score")
    if isinstance(s, dict):
        s = s.get("displayValue")
    return None if s in (None, "") else str(s)


def parse_events(data: dict, league: str) -> list[Game]:
    games = []
    for ev in data.get("events", []):
        try:
            comp = ev["competitions"][0]
            sides = {c["homeAway"]: c for c in comp["competitors"]}
            home, away = sides["home"], sides["away"]
            status = ev["status"]["type"]
            notes = comp.get("notes") or []
            home_score, away_score = _score(home), _score(away)
            if away_score and home.get("shootoutScore") is not None and away.get("shootoutScore") is not None:
                away_score += f" (pên. {home['shootoutScore']}x{away['shootoutScore']})"
            games.append(Game(
                league=league,
                start=datetime.fromisoformat(ev["date"].replace("Z", "+00:00")).astimezone(BR),
                home=home["team"]["displayName"],
                away=away["team"]["displayName"],
                home_score=home_score,
                away_score=away_score,
                state=status.get("state", ""),
                completed=bool(status.get("completed")),
                note=notes[0].get("headline") if notes else None,
            ))
        except (KeyError, IndexError, ValueError, TypeError):
            log.warning("Skipping malformed ESPN event %s", ev.get("id"))
    return games


@lru_cache(maxsize=4)
def all_games(d: date) -> tuple[Game, ...]:
    """Games of every configured league from the day before yesterday to tomorrow."""
    span = f"{(d - timedelta(days=2)):%Y%m%d}-{(d + timedelta(days=1)):%Y%m%d}"
    games: list[Game] = []
    for league in config.LEAGUES:
        try:
            data = get_json(URL.format(slug=league["slug"]), params={"dates": span, "limit": 300})
            games += parse_events(data, league["name"])
        except Exception:
            log.exception("ESPN failed for %s", league["slug"])
    return tuple(sorted(games, key=lambda g: g.start))


def _by_league(games: list[Game]) -> dict[str, list[Game]]:
    grouped: dict[str, list[Game]] = {}
    for league in config.LEAGUES:  # keep the configured order
        items = [g for g in games if g.league == league["name"]]
        if items:
            grouped[league["name"]] = items
    return grouped


def format_results(games: list[Game]) -> str | None:
    if not games:
        return None
    blocks = []
    for league, items in _by_league(games).items():
        lines = [f"⚽ *{league}*"]
        last_note = None
        for g in items:
            if g.note and g.note != last_note:
                lines.append(f"{g.note}:")
                last_note = g.note
            lines.append(f"{g.home} {g.home_score}x{g.away_score} {g.away}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def format_today(games: list[Game]) -> str | None:
    if not games:
        return None
    blocks = ["🔥 *Jogos de Hoje*"]
    for league, items in _by_league(games).items():
        lines = [f"🏆 {league}"]
        lines += [f"⏰ {g.start:%Hh%M} {g.home} x {g.away}" for g in items]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def football_results(d: date) -> str | None:
    yesterday = d - timedelta(days=1)
    games = [g for g in all_games(d) if g.completed and g.start.date() == yesterday]
    return format_results(games)


def football_today(d: date) -> str | None:
    games = [g for g in all_games(d) if g.state == "pre" and g.start.date() == d]
    return format_today(games)
