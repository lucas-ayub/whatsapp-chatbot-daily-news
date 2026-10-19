"""All user-tunable settings live here."""

# --- Time ---------------------------------------------------------------
# The digest "day" follows Brazilian time (holidays, football, news).
BR_TZ = "America/Sao_Paulo"
# Scheduling is anchored to Germany: the GitHub Actions run whose scheduled
# time maps to this local time is the one that sends (handles DST changes).
SEND_TZ = "Europe/Berlin"
SEND_LOCAL_TIME = "07:55"  # message lands around 08:00 (Actions starts with a few minutes of delay)

# --- Weather ------------------------------------------------------------
CITIES = [
    {"name": "São José dos Campos-SP", "lat": -23.1896, "lon": -45.8841},
    {"name": "Munique", "lat": 48.1374, "lon": 11.5755},
]

# --- Markets (Yahoo Finance tickers) ------------------------------------
INDICES = [
    {"ticker": "^BVSP", "label": "📊 Ibovespa"},
    {"ticker": "^GSPC", "label": "🇺🇸 S&P 500"},
    {"ticker": "^DJI", "label": "🇺🇸 Dow Jones"},
    {"ticker": "^IXIC", "label": "🇺🇸 Nasdaq"},
]

# --- Banco Central (SGS series codes) ----------------------------------
BCB_MONTHLY = [
    {"code": 189, "label": "IGP-M"},
    {"code": 188, "label": "INPC"},
    {"code": 433, "label": "IPCA"},
]
BCB_SELIC = 432  # Meta Selic (% a.a.)
BCB_TR = 226     # Taxa Referencial

# --- Football (ESPN public API league slugs) ---------------------------
LEAGUES = [
    {"slug": "conmebol.libertadores", "name": "Copa Libertadores"},
    {"slug": "conmebol.sudamericana", "name": "Copa Sul-Americana"},
    {"slug": "bra.1", "name": "Campeonato Brasileiro - Série A"},
    {"slug": "bra.2", "name": "Campeonato Brasileiro - Série B"},
    {"slug": "bra.copa_do_brazil", "name": "Copa do Brasil"},
    {"slug": "uefa.champions", "name": "Champions League"},
]

# --- News (RSS feeds per category) -------------------------------------
NEWS_FEEDS = {
    "nacionais": [
        "https://g1.globo.com/rss/g1/",
        "https://g1.globo.com/rss/g1/politica/",
        "https://g1.globo.com/rss/g1/economia/",
        "https://feeds.folha.uol.com.br/emcimadahora/rss091.xml",
        "https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml",
    ],
    "internacionais": [
        "https://g1.globo.com/rss/g1/mundo/",
        "https://feeds.bbci.co.uk/portuguese/rss.xml",
        "https://feeds.folha.uol.com.br/mundo/rss091.xml",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
    ],
    "ciencia_tecnologia": [
        "https://g1.globo.com/rss/g1/tecnologia/",
        "https://g1.globo.com/rss/g1/ciencia/",
        "https://rss.tecmundo.com.br/feed",
        "https://techcrunch.com/feed/",
        "https://www.theverge.com/rss/index.xml",
        "https://feeds.arstechnica.com/arstechnica/science",
    ],
}
NEWS_MAX_AGE_HOURS = 30
NEWS_COUNT = {"nacionais": 5, "internacionais": 5, "ciencia_tecnologia": 4}

# --- History ------------------------------------------------------------
HISTORY_COUNT = 9

# --- AI -----------------------------------------------------------------
ANTHROPIC_MODEL = "claude-sonnet-5-5"  # override with ANTHROPIC_MODEL in .env

# --- Sending ------------------------------------------------------------
MAX_CHARS_PER_MESSAGE = 1500  # long digests are split into several WhatsApp messages
SECONDS_BETWEEN_MESSAGES = 4
