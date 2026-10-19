"""TEMPERATURA E INDICADORES FINANCEIROS block, in the order of the original layout."""
from datetime import date

from digest.sections import indicators, markets, weather


def weather_and_markets(d: date) -> str | None:
    lines: list[str | None] = []
    lines += weather.weather_lines()
    lines.append(markets.currency_line("USD"))
    lines.append(markets.currency_line("EUR"))
    lines += markets.index_lines()
    lines.append(markets.currency_line("BTC"))
    lines += indicators.indicator_lines(d)
    lines.append(markets.gold_line())
    body = [line for line in lines if line]
    if not body:
        return None
    return "*TEMPERATURA E INDICADORES FINANCEIROS*\n" + "\n".join(body)
