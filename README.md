# WhatsApp Chatbot

Python bot that sends a daily digest of news and market indicators to my own WhatsApp,
every morning at ~08:00 (Germany time), via GitHub Actions.

## What the message contains

| Section | Source |
|---|---|
| Date header | Python (`datetime`) |
| Commemorative dates & holidays | Portuguese Wikipedia day page + `holidays` (Brazil) |
| Weather (São José dos Campos) | Open-Meteo |
| USD, EUR, Bitcoin | AwesomeAPI (Yahoo Finance as fallback) |
| Ibovespa, S&P 500, Dow Jones, Nasdaq, gold | Yahoo Finance (`yfinance`) |
| IGP-M, INPC, IPCA, Selic, TR | Banco Central (SGS API) |
| Football results & today's games | ESPN public scoreboard API |
| National news, geopolitics, tech & startups in Brazil and worldwide (+ idea of the day) and science | RSS feeds, curated and summarised by Claude, with links |
| Historical events | Portuguese Wikipedia, selected by Claude |

Every section is independent: if a source is down, that section is skipped and the
rest of the message is still sent. Long messages are split into several WhatsApp messages.

## Project layout

```
digest/
├── main.py          # builds the message (SECTIONS list) and sends it
├── config.py        # cities, tickers, leagues, RSS feeds, send time...
├── sender.py        # CallMeBot + message splitting
├── llm.py           # Anthropic API helper
├── wiki.py          # Wikipedia day-page parser
├── utils.py         # HTTP, Portuguese dates, number formatting
└── sections/        # one module per block of the message
tests/               # offline tests (no network)
.github/workflows/   # daily schedule
```

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your keys
python -m digest.main --dry-run                 # print today's digest
python -m digest.main --dry-run --date 2026-10-14
python -m digest.main                           # send it
pytest                                          # run the tests
```

## Activate CallMeBot (one time)

1. Get the bot's current phone number from
   https://www.callmebot.com/blog/free-api-whatsapp-messages/ (it changes from time to time)
   and save it in your phone's contacts (any name).
2. Send it this WhatsApp message: `I allow callmebot to send me messages`
3. You'll get a reply with your API key (it can take a couple of minutes).

## Punctual daily trigger (Cloudflare Cron)

GitHub's scheduled runs are best-effort and were often hours late or skipped. The Worker in
`relay/callmebot-worker.js` also has a `scheduled()` handler: Cron Triggers at
`55 5 * * *`, `55 6 * * *` and `55 7 * * *` (UTC) start this workflow with `scheduled=true`.
The workflow sends only after 07:55 Berlin and only once a day, so extra triggers are harmless.
The Worker needs a secret `GITHUB_TOKEN`: a fine-grained token for this repository with
*Actions: Read and write*.

## Sending path

Messages go straight from GitHub Actions to CallMeBot. Don't route them through the Cloudflare
Worker's `/whatsapp.php` relay: CallMeBot answers those requests with an empty HTTP 204 and
delivers nothing (the sender treats that as a failure). If you ever set the optional
`CALLMEBOT_URL` secret, keep it as `https://api.callmebot.com/whatsapp.php` or delete it.

## Secrets

| Name | What |
|---|---|
| `CALLMEBOT_PHONE` | Your WhatsApp number, e.g. `+5512999999999` |
| `CALLMEBOT_APIKEY` | Key received from CallMeBot after activation |
| `ANTHROPIC_API_KEY` | Optional. Without it: raw headlines and a simpler history selection |

Locally they go in `.env`; on GitHub in *Settings → Secrets and variables → Actions*.

## Schedule

GitHub cron only understands UTC, so the workflow runs at 05:55 and 06:55 UTC and the
script sends only from the run that corresponds to 07:55 in Berlin (`SEND_LOCAL_TIME` in
`config.py`). This keeps the 08:00 delivery correct across daylight-saving changes.
To change the time, edit both crons and `SEND_LOCAL_TIME`.

Run it manually from the *Actions* tab → *Daily digest* → *Run workflow*
(with *dry run* checked, the message only appears in the logs).
