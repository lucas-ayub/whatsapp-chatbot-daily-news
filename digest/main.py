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
from digest.email_sender import email_configured, send_email
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


def should_send_now(now_utc: datetime | None = None) -> bool:
    """For scheduled runs: is it between SEND_LOCAL_TIME and SEND_LATEST_LOCAL_TIME in SEND_TZ?

    GitHub cron is UTC-only, best-effort and often late, so the workflow fires several
    times each morning. Runs before the send time (e.g. the summer cron in winter) exit;
    the first one after it sends, and the workflow's daily marker stops the rest.
    """
    local = (now_utc or datetime.now(timezone.utc)).astimezone(ZoneInfo(config.SEND_TZ))
    return config.SEND_LOCAL_TIME <= local.strftime("%H:%M") <= config.SEND_LATEST_LOCAL_TIME


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Daily WhatsApp digest")
    parser.add_argument("--dry-run", action="store_true", help="print the message instead of sending it")
    parser.add_argument("--date", type=date.fromisoformat, help="build the digest for YYYY-MM-DD")
    parser.add_argument("--schedule", default="", help="cron string of the scheduled run (set by GitHub Actions)")
    parser.add_argument("--sent-marker", default="", help="file to create after a real send (used by the workflow)")
    parser.add_argument("--probe", default="", help="send only this text to test CallMeBot (\\n = new line)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    load_dotenv()

    if args.probe:
        from digest.sender import probe
        return 0 if probe(args.probe.replace("\\n", "\n")) else 1

    if args.schedule and not should_send_now():
        log.info("Scheduled run '%s' is outside the send window in %s; nothing to do.",
                 args.schedule, config.SEND_TZ)
        return 0

    d = args.date or datetime.now(ZoneInfo(config.BR_TZ)).date()
    message = build_message(d)

    if args.dry_run:
        print(message)
        print(f"\n--- {len(message)} characters ---", file=sys.stderr)
        return 0

    if email_configured():
        send_email(message, d)  # e-mail is the delivery channel when configured
    else:
        send_whatsapp(message)
    log.info("Digest for %s sent.", d)
    if args.sent_marker:
        with open(args.sent_marker, "w") as f:
            f.write(f"{d}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
