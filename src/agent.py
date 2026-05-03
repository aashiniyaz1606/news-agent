"""
Agent orchestrator — ties all modules together into a pipeline.

Pipeline: Search -> Deduplicate -> Scrape -> Summarize -> Validate -> Store -> Export
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.cache import ArticleCache
from src.config import MIN_ARTICLES, OUTPUT_DIR
from src.database import NewsDatabase
from src.models import ProcessedArticle, ScrapedArticle
from src.scraper import ArticleScraper
from src.search import NewsSearcher

logger = logging.getLogger(__name__)


class NewsAgent:
    """
    Orchestrates the full news collection pipeline.

    Coordinates search, scraping, summarization, and storage
    to produce a clean set of processed renewable energy news articles.
    """

    def __init__(self):
        self.cache = ArticleCache()
        self.searcher = NewsSearcher()
        self.scraper = ArticleScraper(cache=self.cache)
        self.database = NewsDatabase()

    async def run(self) -> list[ProcessedArticle]:
        """
        Execute the full pipeline and return processed articles.

        Steps:
        1. Search for articles via Tavily
        2. Scrape full content
        3. Build ProcessedArticle objects directly from text
        4. Store in database
        5. Export to JSON
        """
        logger.info("=" * 60)
        logger.info("RENEWABLE ENERGY NEWS AGENT - Starting pipeline")
        logger.info("=" * 60)

        # ── Step 1: Initialize database ──────────────────────────────
        logger.info("Step 1: Initializing database...")
        await self.database.init_db()

        # ── Step 2: Search ───────────────────────────────────────────
        logger.info("Step 2: Searching for articles...")
        search_results = await self.searcher.search_all()

        if not search_results:
            logger.error("No search results found. Aborting.")
            return []

        # Limit to 30 for scraping to save time
        search_results = search_results[:30]

        logger.info("Selected %d search results to scrape", len(search_results))

        # ── Step 3: Scrape ───────────────────────────────────────────
        logger.info("Step 3: Scraping full article content...")
        scraped_articles = await self.scraper.scrape_all(search_results)

        if not scraped_articles:
            logger.error("No articles could be scraped. Aborting.")
            return []

        logger.info("Successfully scraped %d articles", len(scraped_articles))

        # ── Step 4: Build ProcessedArticles ──────────────────────────
        logger.info("Step 4: Building final article objects (Skipping LLM)...")
        processed_articles = self._build_processed_articles(scraped_articles)
        logger.info("Built %d processed articles", len(processed_articles))

        # ── Step 5: Store in database ────────────────────────────────
        logger.info("Step 5: Storing in database...")
        inserted, skipped = await self.database.insert_articles_batch(
            processed_articles
        )
        logger.info("Database: %d new, %d skipped (duplicates)", inserted, skipped)

        # ── Step 6: Export to JSON ───────────────────────────────────
        logger.info("Step 6: Exporting to JSON...")
        output_path = self._export_json(processed_articles)
        logger.info("Exported to: %s", output_path)

        # ── Summary ─────────────────────────────────────────────────
        self._print_summary(
            search_count=len(search_results),
            scraped_count=len(scraped_articles),
            summarized_count=0,
            final_count=len(processed_articles),
            inserted=inserted,
            skipped=skipped,
        )

        if len(processed_articles) < MIN_ARTICLES:
            logger.warning(
                "Only %d articles collected (target: %d). "
                "Consider broadening search queries.",
                len(processed_articles),
                MIN_ARTICLES,
            )

        return processed_articles

    def _build_processed_articles(
        self, scraped_articles: list[ScrapedArticle]
    ) -> list[ProcessedArticle]:
        """Convert scraped articles into ProcessedArticle objects directly."""
        processed: list[ProcessedArticle] = []
        now = datetime.now(timezone.utc).isoformat()

        for article in scraped_articles:
            if not article.published_date:
                continue

            if len(processed) >= 20:
                break

            images = []
            if article.top_image:
                images.append(article.top_image)

            # Generate a summary by extracting the first 500 characters
            text_preview = article.full_text[:500]
            if len(article.full_text) > 500:
                text_preview += "..."

            try:
                pa = ProcessedArticle(
                    title=article.title,
                    content_summary=text_preview,
                    link=article.url,
                    images_links=images,
                    published_date=article.published_date,
                    created_at=now,
                    tags=["news"],
                    sentiment="neutral",
                )
                processed.append(pa)
            except Exception as e:
                logger.warning(
                    "Failed to build ProcessedArticle for '%s': %s",
                    article.title[:60],
                    e,
                )

        return processed

    def _export_json(self, articles: list[ProcessedArticle]) -> str:
        """Export articles to a JSON file."""
        output_dir = Path(OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / "results.json"
        data = [a.to_dict() for a in articles]

        output_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return str(output_path)

    @staticmethod
    def _print_summary(
        search_count: int,
        scraped_count: int,
        summarized_count: int,
        final_count: int,
        inserted: int,
        skipped: int,
    ) -> None:
        """Print a formatted pipeline summary."""
        print("\n" + "=" * 60)
        print("  PIPELINE SUMMARY")
        print("=" * 60)
        print(f"  Search results:     {search_count}")
        print(f"  Scraped articles:   {scraped_count}")
        print(f"  Summarized:         {summarized_count}")
        print(f"  Final articles:     {final_count}")
        print(f"  New in database:    {inserted}")
        print(f"  Skipped (dupes):    {skipped}")
        print("=" * 60)
