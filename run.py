"""
Renewable Energy News Research Agent — Entry Point

Collects, scrapes, summarizes, and stores the latest weekly
renewable energy news articles using Tavily, newspaper4k, and Google Gemini.

Usage:
    python run.py
"""

import asyncio
import io
import json
import logging
import sys
from datetime import datetime, timezone

# Fix Windows console encoding for Unicode output
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from src.agent import NewsAgent
from src.config import LOG_LEVEL


def setup_logging() -> None:
    """Configure logging with a clean, readable format."""
    log_format = "%(asctime)s | %(levelname)-7s | %(name)-20s | %(message)s"
    date_format = "%H:%M:%S"

    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("newspaper").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)


async def main() -> None:
    """Run the news agent pipeline."""
    setup_logging()
    logger = logging.getLogger("run")

    print()
    print("=" * 60)
    print("  Renewable Energy News Research Agent")
    print("  Collecting the latest weekly news...")
    print(f"  Started at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)
    print()

    try:
        agent = NewsAgent()
        articles = await agent.run()

        if articles:
            print(f"\n[OK] Successfully collected {len(articles)} articles!")
            print("[OUTPUT] Saved to: output/results.json")

            # Print preview of first 3 articles
            print("\n" + "-" * 60)
            print("ARTICLE PREVIEWS (first 3)")
            print("-" * 60)
            for i, article in enumerate(articles[:3], 1):
                print(f"\n  [{i}] {article.title}")
                print(f"      Link: {article.link}")
                print(f"      Date: {article.published_date or 'N/A'}")
                print(f"      Tags: {', '.join(article.tags) if article.tags else 'N/A'}")
                print(f"      Sentiment: {article.sentiment}")
                # Show first 100 chars of summary
                preview = article.content_summary[:100]
                if len(article.content_summary) > 100:
                    preview += "..."
                print(f"      Summary: {preview}")
            print()
        else:
            print("\n[WARN] No articles were collected. Check logs for details.")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n[STOP] Interrupted by user.")
        sys.exit(0)
    except Exception as e:
        logger.exception("Pipeline failed with error: %s", e)
        print(f"\n[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
