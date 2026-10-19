"""Shared helpers: HTTP session, Portuguese dates and Brazilian number formatting."""
from datetime import date

import requests

MONTHS = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
          "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
WEEKDAYS = ["Segunda-Feira", "Terça-Feira", "Quarta-Feira", "Quinta-Feira",
            "Sexta-Feira", "Sábado", "Domingo"]

USER_AGENT = "whatsapp-daily-digest/1.0 (personal project; https://github.com)"
TIMEOUT = 20

_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT


def get(url: str, **kwargs) -> requests.Response:
    """GET with a default timeout and User-Agent; raises on HTTP errors."""
    kwargs.setdefault("timeout", TIMEOUT)
    resp = _session.get(url, **kwargs)
    resp.raise_for_status()
    return resp


def get_json(url: str, **kwargs):
    return get(url, **kwargs).json()


def pt_date(d: date) -> str:
    """date(2026, 9, 16) -> '16 de Setembro de 2026'"""
    return f"{d.day} de {MONTHS[d.month - 1]} de {d.year}"


def pt_month(d: date) -> str:
    """date(2026, 9, 1) -> 'Setembro de 2026'"""
    return f"{MONTHS[d.month - 1]} de {d.year}"


def br_number(x: float, decimals: int = 2) -> str:
    """1234567.891 -> '1.234.567,89'"""
    s = f"{x:,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def arrow(change: float) -> str:
    if change > 0:
        return "⬆️"
    if change < 0:
        return "⬇️"
    return "➡️"


def pct(change: float) -> str:
    """Takes percentage points: 0.71 -> '⬆️ 0,71%'"""
    return f"{arrow(change)} {br_number(abs(change), 2)}%"
