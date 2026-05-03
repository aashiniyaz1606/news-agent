"""
Configuration module for the Renewable Energy News Agent.

Loads environment variables and defines constants for search queries,
trusted sources, and application settings.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ─── API Keys ───────────────────────────────────────────────────────────────
TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")

# ─── Paths ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH: str = os.getenv("DB_PATH", str(PROJECT_ROOT / "data" / "news.db"))
CACHE_DIR: str = os.getenv("CACHE_DIR", str(PROJECT_ROOT / ".cache"))
OUTPUT_DIR: str = str(PROJECT_ROOT / "output")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ─── Search Configuration ──────────────────────────────────────────────────
SEARCH_QUERIES: list[str] = [
    "latest renewable energy news this week",
    "solar energy industry updates last 7 days",
    "wind energy policy news recent",
    "energy storage battery technology news this week",
    "renewable energy policy regulation news recent",
    "clean energy innovation technology breakthroughs this week",
]

# Maximum results per query from Tavily
MAX_RESULTS_PER_QUERY: int = 20

# Time range filter for Tavily ("day", "week", "month", "year")
SEARCH_TIME_RANGE: str = "day"

# Minimum total unique articles to collect
MIN_ARTICLES: int = 10

# ─── Trusted Sources ───────────────────────────────────────────────────────
TRUSTED_DOMAINS: list[str] = [
    "reuters.com",
    "bloomberg.com",
    "theguardian.com",
    "bbc.com",
    "bbc.co.uk",
    "cnbc.com",
    "nytimes.com",
    "washingtonpost.com",
    "apnews.com",
    "aljazeera.com",
    # Energy-specific publications
    "cleantechnica.com",
    "pvmagazine.com",
    "pv-magazine.com",
    "renewableenergyworld.com",
    "greentechmedia.com",
    "energymonitor.ai",
    "utilitydive.com",
    "solarpowerworldonline.com",
    "windpowermonthly.com",
    "rechargenews.com",
    "energypost.eu",
    "iea.org",
    "irena.org",
    "carbonbrief.org",
    "electrek.co",
    "canarymedian.com",
    "canarymedia.com",
    "theenergymix.com",
    "seia.org",
    "solarpowereurope.org",
]

# ─── Scraping Configuration ────────────────────────────────────────────────
SCRAPE_TIMEOUT_SECONDS: int = 15
MAX_CONCURRENT_SCRAPES: int = 5

# ─── Summarization Configuration ───────────────────────────────────────────
LLM_MODEL: str = "gemini-2.0-flash"
LLM_TEMPERATURE: float = 0.1
SUMMARY_MAX_WORDS: int = 200
SUMMARY_MIN_WORDS: int = 80

# Rate limiting: delay between LLM calls (seconds)
LLM_RATE_LIMIT_DELAY: float = 35.0

# ─── Deduplication ─────────────────────────────────────────────────────────
# Fuzzy title similarity threshold (0.0 to 1.0)
TITLE_SIMILARITY_THRESHOLD: float = 0.85

# ─── Cache ──────────────────────────────────────────────────────────────────
CACHE_TTL_HOURS: int = 24

# ─── Renewable Energy Tags ─────────────────────────────────────────────────
VALID_TAGS: list[str] = [
    "solar",
    "wind",
    "storage",
    "policy",
    "innovation",
    "hybrid",
    "hydrogen",
    "grid",
    "EV",
    "nuclear",
]

VALID_SENTIMENTS: list[str] = ["positive", "neutral", "negative"]
