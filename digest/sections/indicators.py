"""Brazilian economic indicators from the Banco Central SGS API."""
import logging
from datetime import date, datetime, timedelta

from digest import config
from digest.utils import arrow, br_number, get_json, pct, pt_date, pt_month

log = logging.getLogger(__name__)
SGS_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"


def fetch_series(code: int, today: date, days_back: int = 400) -> list[tuple[date, float]]:
    """[(date, value), ...] oldest first."""
    rows = get_json(SGS_URL.format(code=code), params={
        "formato": "json",
        "dataInicial": (today - timedelta(days=days_back)).strftime("%d/%m/%Y"),
        "dataFinal": today.strftime("%d/%m/%Y"),
    })
    return [(datetime.strptime(r["data"], "%d/%m/%Y").date(), float(r["valor"])) for r in rows]


def monthly_line(label: str, series: list[tuple[date, float]]) -> str:
    """'💲IPCA ⬆️ 0,82% Setembro de 2026' (arrow = sign of the monthly rate)."""
    ref, value = series[-1]
    return f"💲{label} {pct(value)} {pt_month(ref)}"


def selic_line(series: list[tuple[date, float]]) -> str:
    """Current target rate, the direction of its last change and when it took effect."""
    current = series[-1][1]
    since, direction = series[0][0], 0.0
    for (d_prev, v_prev), (d, v) in zip(series, series[1:]):
        if v != v_prev:
            since, direction = d, v - v_prev
    return f"💲SELIC {arrow(direction)} {br_number(current, 2)}% {pt_date(since)}"


def tr_line(series: list[tuple[date, float]]) -> str:
    ref, value = series[-1]
    return f"💲TR {pct(value)} {pt_date(ref)}"


def indicator_lines(today: date) -> list[str]:
    lines = []
    for item in config.BCB_MONTHLY:
        try:
            lines.append(monthly_line(item["label"], fetch_series(item["code"], today)))
        except Exception:
            log.exception("BCB series %s failed", item["label"])
    daily = (
        (config.BCB_SELIC, selic_line, "SELIC", 1500),  # long window to find the last Copom change
        (config.BCB_TR, tr_line, "TR", 60),
    )
    for code, builder, name, days_back in daily:
        try:
            lines.append(builder(fetch_series(code, today, days_back)))
        except Exception:
            log.exception("BCB series %s failed", name)
    return lines
