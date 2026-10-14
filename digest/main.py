from datetime import date
from digest.sections.header import date_header
from digest.sections.history import historical_events
from digest.sections.markets import market_quotes
from digest.sender import send_whatsapp

SECTIONS = [date_header, market_quotes, historical_events]

def build_message(d: date) -> str:
    # TODO: call each section; if one fails, log it and continue without it
    raise NotImplementedError

if __name__ == "__main__":
    # TODO: --dry-run flag that prints instead of sending
    ...