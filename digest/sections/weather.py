"""Daily min/max temperature per city (Open-Meteo, free, no key)."""
import logging

from digest import config
from digest.utils import get_json

log = logging.getLogger(__name__)
URL = "https://api.open-meteo.com/v1/forecast"


def weather_emoji(code: int) -> str:
    """WMO weather interpretation code -> emoji."""
    if code == 0:
        return "☀️"
    if code in (1, 2):
        return "🌤️"
    if code == 3:
        return "☁️"
    if code in (45, 48):
        return "🌫️"
    if 51 <= code <= 67 or 80 <= code <= 82:
        return "🌧️"
    if 71 <= code <= 77 or code in (85, 86):
        return "❄️"
    if code >= 95:
        return "⛈️"
    return "🌡️"


def city_line(city: dict) -> str:
    data = get_json(URL, params={
        "latitude": city["lat"],
        "longitude": city["lon"],
        "daily": "weather_code,temperature_2m_max,temperature_2m_min",
        "timezone": "auto",
        "forecast_days": 1,
    })["daily"]
    tmin = round(data["temperature_2m_min"][0])
    tmax = round(data["temperature_2m_max"][0])
    return f"{weather_emoji(data['weather_code'][0])} Mín {tmin}° Máx {tmax}° ({city['name']})"


def weather_lines() -> list[str]:
    lines = []
    for city in config.CITIES:
        try:
            lines.append(city_line(city))
        except Exception:
            log.exception("Weather failed for %s", city["name"])
    return lines
