"""Currencies, Bitcoin, stock indices and gold.

Currencies/BTC come from AwesomeAPI (Brazilian quotes, already with % change);
Yahoo Finance (yfinance) covers the indices, gold and acts as a fallback.
"""
import logging
from functools import lru_cache

from digest import config
from digest.utils import br_number, get_json, pct

log = logging.getLogger(__name__)

AWESOME_URL = "https://economia.awesomeapi.com.br/json/last/USD-BRL,EUR-BRL,BTC-BRL"
TROY_OUNCE_GRAMS = 31.1034768

# label, AwesomeAPI key, Yahoo fallback ticker, decimals
CURRENCIES = {
    "USD": ("💵 Dólar Com", "USDBRL", "BRL=X", 2),
    "EUR": ("💶 Euro", "EURBRL", "EURBRL=X", 2),
    "BTC": ("🪙 Bitcoin", "BTCBRL", "BTC-BRL", 2),
}


@lru_cache(maxsize=1)
def awesome_quotes() -> dict:
    return get_json(AWESOME_URL)


@lru_cache(maxsize=1)
def yahoo_closes() -> dict[str, tuple[float, float]]:
    """{ticker: (last_close, previous_close)} for every ticker we use, in one request."""
    import yfinance as yf

    tickers = [i["ticker"] for i in config.INDICES] + ["GC=F"] + [c[2] for c in CURRENCIES.values()]
    df = yf.download(tickers, period="10d", interval="1d", group_by="ticker",
                     auto_adjust=False, progress=False, threads=False)
    out = {}
    for t in tickers:
        try:
            closes = df[t]["Close"].dropna()
            if len(closes) >= 2:
                out[t] = (float(closes.iloc[-1]), float(closes.iloc[-2]))
        except KeyError:
            log.warning("No Yahoo data for %s", t)
    return out


def _change(last: float, prev: float) -> float:
    return (last / prev - 1) * 100


def currency_line(code: str) -> str | None:
    label, awesome_key, yahoo_ticker, decimals = CURRENCIES[code]
    try:
        q = awesome_quotes()[awesome_key]
        value, change = float(q["bid"]), float(q["pctChange"])
    except Exception:
        log.warning("AwesomeAPI failed for %s, falling back to Yahoo", code, exc_info=True)
        try:
            last, prev = yahoo_closes()[yahoo_ticker]
        except Exception:
            log.exception("Yahoo fallback failed for %s", code)
            return None
        value, change = last, _change(last, prev)
    return f"{label} {pct(change)} R$ {br_number(value, decimals)}"


def index_lines() -> list[str]:
    try:
        closes = yahoo_closes()
    except Exception:
        log.exception("Yahoo Finance download failed")
        return []
    lines = []
    for idx in config.INDICES:
        if idx["ticker"] in closes:
            last, prev = closes[idx["ticker"]]
            lines.append(f"{idx['label']} {pct(_change(last, prev))} {br_number(last, 0)} pts")
    return lines


def gold_line() -> str | None:
    """Gold per gram in BRL = COMEX gold (USD/troy oz) x USD/BRL / 31.1 g."""
    try:
        closes = yahoo_closes()
        g_last, g_prev = closes["GC=F"]
        u_last, u_prev = closes["BRL=X"]
    except Exception:
        log.exception("Gold quote failed")
        return None
    last = g_last * u_last / TROY_OUNCE_GRAMS
    prev = g_prev * u_prev / TROY_OUNCE_GRAMS
    return f"🟨 Ouro (grama) {pct(_change(last, prev))} R$ {br_number(last, 2)}"
