# 🌿 Renewable Energy News Research Agent

An autonomous Python agent that collects, scrapes, summarizes, and stores the latest weekly news about renewable energy — covering solar, wind, storage, policy, innovation, and more.

## Architecture

```
Search (Tavily) → Scrape (newspaper4k) → Summarize (Gemini) → Store (SQLite)
```

| Module | Description |
|--------|-------------|
| `src/search.py` | Multi-query Tavily search with deduplication |
| `src/scraper.py` | Full article extraction (newspaper4k + BS4 fallback) |
| `src/summarizer.py` | LLM summarization with tags & sentiment via Gemini |
| `src/database.py` | Async SQLite storage with upsert logic |
| `src/cache.py` | File-based caching to avoid re-scraping |
| `src/agent.py` | Pipeline orchestrator |
| `src/config.py` | Central configuration |
| `src/models.py` | Pydantic data models |

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API keys

Copy the example env file and fill in your keys:

```bash
cp .env.example .env
```

Edit `.env`:
```env
TAVILY_API_KEY=tvly-your-key-here
GOOGLE_API_KEY=your-gemini-api-key-here
```

- **Tavily API Key**: Get one at [tavily.com](https://tavily.com)
- **Google Gemini API Key**: Get one at [Google AI Studio](https://aistudio.google.com/)

### 3. Run the agent

```bash
python run.py
```

## Output

The agent outputs:
- **Console**: Pipeline stats and article previews
- **`output/results.json`**: Full structured output
- **`data/news.db`**: SQLite database with all articles

### Output format

```json
[
  {
    "title": "Solar Energy Hits Record Capacity in Q1 2026",
    "content_summary": "A factual 80-200 word summary...",
    "link": "https://example.com/article",
    "images_links": ["https://example.com/image.jpg"],
    "published_date": "2026-05-01T10:00:00",
    "created_at": "2026-05-03T15:00:00+00:00",
    "tags": ["solar", "innovation"],
    "sentiment": "positive"
  }
]
```

## Features

- ✅ **10+ unique articles** per run
- ✅ **Deduplication** by URL and fuzzy title matching
- ✅ **Multi-strategy scraping**: newspaper4k → Tavily raw → BeautifulSoup
- ✅ **Rate-limited** LLM calls (respects Gemini quotas)
- ✅ **Caching** to avoid redundant scraping
- ✅ **Tagging**: solar, wind, storage, policy, innovation, hybrid, hydrogen, grid, EV
- ✅ **Sentiment analysis**: positive / neutral / negative
- ✅ **Async pipeline** for performance
- ✅ **Comprehensive logging**

## Configuration

Key settings in `src/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `LLM_MODEL` | `gemini-2.0-flash` | Gemini model for summarization |
| `LLM_RATE_LIMIT_DELAY` | `1.5s` | Delay between LLM calls |
| `SUMMARY_MAX_WORDS` | `200` | Maximum summary length |
| `MAX_RESULTS_PER_QUERY` | `10` | Results per Tavily query |
| `SEARCH_TIME_RANGE` | `week` | Time filter for searches |
| `CACHE_TTL_HOURS` | `24` | Cache expiry time |

## License

MIT
