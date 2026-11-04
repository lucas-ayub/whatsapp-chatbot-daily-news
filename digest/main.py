"""Builds the daily digest and sends it to WhatsApp.

Usage (from the project root):
    python -m digest.main --dry-run            # print today's message, don't send
    python -m digest.main --dry-run --date 2026-10-14
    python -m digest.main                      # build and send
"""
import argparse
import logging
import sys
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from digest import config
from digest.sections import commemorative, finance, football, history, news
from digest.sections.header import date_header
from digest.sender import send_whatsapp

log = logging.getLogger("digest")

# Order of the blocks in the message. Each one takes the date and returns text or None.
SECTIONS = [
    date_header,
    commemorative.commemorative_dates,
    finance.weather_and_markets,
    football.football_results,
    football.football_today,
    news.national_news,
    news.geopolitics_news,
    news.startup_news,
    news.idea_of_the_day,
    news.science_news,
    history.historical_events,
]
FOOTER = "Bom Dia!!! 😉"


def build_message(d: date) -> str:
    blocks = []
    for section in SECTIONS:
        try:
            text = section(d)
        except Exception:
            log.exception("Section %s failed; skipping it", section.__name__)
            continue
        if text:
            blocks.append(text.strip())
    blocks.append(FOOTER)
    return "\n\n".join(blocks)


def should_send_now(schedule: str, now_utc: datetime | None = None) -> bool:
    """GitHub Actions only speaks UTC, so the workflow has one cron per DST offset.

    Only the run whose *scheduled* time equals SEND_LOCAL_TIME in SEND_TZ sends;
    the other one exits quietly. Using the scheduled time (not the real start time)
    makes this immune to GitHub's start delays.
    """
    minute, hour = (int(x) for x in schedule.split()[:2])
    now_utc = now_utc or datetime.now(timezone.utc)
    scheduled = now_utc.replace(hour=hour, minute=minute, second=0, microsecond=0)
    local = scheduled.astimezone(ZoneInfo(config.SEND_TZ))
    return local.strftime("%H:%M") == config.SEND_LOCAL_TIME


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Daily WhatsApp digest")
    parser.add_argument("--dry-run", action="store_true", help="print the message instead of sending it")
    parser.add_argument("--date", type=date.fromisoformat, help="build the digest for YYYY-MM-DD")
    parser.add_argument("--schedule", default="", help="cron string of the scheduled run (set by GitHub Actions)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    load_dotenv()

    if args.schedule and not should_send_now(args.schedule):
        log.info("Run for cron '%s' is the off-season duplicate; nothing to do.", args.schedule)
        return 0

    d = args.date or datetime.now(ZoneInfo(config.BR_TZ)).date()
    message = build_message(d)

    if args.dry_run:
        print(message)
        print(f"\n--- {len(message)} characters ---", file=sys.stderr)
        return 0

    send_whatsapp(message)
    log.info("Digest for %s sent.", d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
