"""
Scraping module for extracting full article content.

Uses newspaper4k as primary scraper with BeautifulSoup + httpx as fallback.
Supports async concurrent scraping with rate limiting.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from src.cache import ArticleCache
from src.config import MAX_CONCURRENT_SCRAPES, SCRAPE_TIMEOUT_SECONDS
from src.models import ScrapedArticle, SearchResult

logger = logging.getLogger(__name__)


class ArticleScraper:
    """Scrapes full article content from URLs."""

    def __init__(self, cache: ArticleCache | None = None):
        self.cache = cache or ArticleCache()
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_SCRAPES)

    async def scrape_all(
        self, search_results: list[SearchResult]
    ) -> list[ScrapedArticle]:
        """Scrape all search results concurrently."""
        logger.info("Starting to scrape %d articles...", len(search_results))

        tasks = [
            self._scrape_with_semaphore(result) for result in search_results
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        articles: list[ScrapedArticle] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(
                    "Failed to scrape '%s': %s",
                    search_results[i].url,
                    result,
                )
            elif result is not None:
                articles.append(result)

        logger.info(
            "Successfully scraped %d / %d articles",
            len(articles),
            len(search_results),
        )
        return articles

    async def _scrape_with_semaphore(
        self, search_result: SearchResult
    ) -> ScrapedArticle | None:
        """Scrape with concurrency limiting."""
        async with self._semaphore:
            return await self._scrape_article(search_result)

    async def _scrape_article(
        self, search_result: SearchResult
    ) -> ScrapedArticle | None:
        """
        Scrape a single article. Strategy:
        1. Check cache
        2. Try newspaper4k
        3. Fall back to Tavily raw_content
        4. Fall back to BeautifulSoup + httpx
        """
        url = search_result.url
        logger.info("Scraping: %s", url)

        # ── Check cache ──────────────────────────────────────────────
        cached = self.cache.get(url)
        if cached:
            logger.info("  → Cache hit for: %s", url)
            try:
                return ScrapedArticle(**cached)
            except Exception:
                pass  # Cache entry invalid, re-scrape

        # ── Try newspaper4k ──────────────────────────────────────────
        article_data = await self._scrape_with_newspaper(url)

        # ── Fallback: use Tavily raw_content ─────────────────────────
        if article_data is None and search_result.raw_content:
            logger.info("  → Using Tavily raw_content for: %s", url)
            clean_text = self._clean_text(search_result.raw_content)
            if len(clean_text.strip()) >= 50:
                article_data = {
                    "title": search_result.title,
                    "url": url,
                    "full_text": clean_text,
                    "published_date": search_result.published_date,
                    "top_image": None,
                    "authors": [],
                    "source_domain": urlparse(url).netloc,
                }

        # ── Fallback: BeautifulSoup ──────────────────────────────────
        if article_data is None:
            article_data = await self._scrape_with_beautifulsoup(url)

        if article_data is None:
            logger.warning("  → All scraping methods failed for: %s", url)
            return None

        # Use search result published_date if scraper didn't find one
        if not article_data.get("published_date") and search_result.published_date:
            article_data["published_date"] = search_result.published_date

        # Validate published date is within last 7 days
        if not self._is_recent(article_data.get("published_date")):
            logger.info(
                "  → Article too old, skipping: %s (date: %s)",
                url,
                article_data.get("published_date"),
            )
            # Don't skip — date parsing can be unreliable.
            # We still include it since Tavily already filtered by time_range=week.

        # Build ScrapedArticle
        try:
            scraped = ScrapedArticle(
                title=article_data.get("title", search_result.title),
                url=url,
                full_text=article_data["full_text"],
                published_date=article_data.get("published_date"),
                top_image=article_data.get("top_image"),
                authors=article_data.get("authors", []),
                source_domain=article_data.get(
                    "source_domain", urlparse(url).netloc
                ),
            )

            # Cache the result
            self.cache.set(url, scraped.model_dump())
            return scraped

        except Exception as e:
            logger.warning("  → Failed to build ScrapedArticle for %s: %s", url, e)
            return None

    async def _scrape_with_newspaper(self, url: str) -> dict | None:
        """Scrape article using newspaper4k."""
        try:
            import newspaper

            loop = asyncio.get_event_loop()
            article = await loop.run_in_executor(None, newspaper.article, url)

            if not article.text or len(article.text.strip()) < 50:
                logger.debug("  → newspaper4k: text too short for %s", url)
                return None

            pub_date = None
            if article.publish_date:
                pub_date = article.publish_date.isoformat()

            return {
                "title": article.title or "",
                "url": url,
                "full_text": self._clean_text(article.text),
                "published_date": pub_date,
                "top_image": article.top_image,
                "authors": list(article.authors) if article.authors else [],
                "source_domain": urlparse(url).netloc,
            }

        except Exception as e:
            logger.debug("  → newspaper4k failed for %s: %s", url, e)
            return None

    async def _scrape_with_beautifulsoup(self, url: str) -> dict | None:
        """Fallback scraper using httpx + BeautifulSoup."""
        try:
            async with httpx.AsyncClient(
                timeout=SCRAPE_TIMEOUT_SECONDS,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"
                    )
                },
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove unwanted elements
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()

            # Try to find article body
            article_body = (
                soup.find("article")
                or soup.find("div", class_=re.compile(r"article|content|story|post"))
                or soup.find("main")
            )

            if article_body:
                paragraphs = article_body.find_all("p")
            else:
                paragraphs = soup.find_all("p")

            text = "\n\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
            text = self._clean_text(text)

            if len(text.strip()) < 50:
                return None

            # Extract title
            title_tag = soup.find("h1") or soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else ""

            # Extract main image
            img = None
            og_img = soup.find("meta", property="og:image")
            if og_img and og_img.get("content"):
                img = og_img["content"]

            return {
                "title": title,
                "url": url,
                "full_text": text,
                "published_date": None,
                "top_image": img,
                "authors": [],
                "source_domain": urlparse(url).netloc,
            }

        except Exception as e:
            logger.debug("  → BeautifulSoup failed for %s: %s", url, e)
            return None

    @staticmethod
    def _clean_text(text: str) -> str:
        """Remove HTML artifacts, excessive whitespace, and noise from text."""
        # Remove HTML tags if any remain
        text = re.sub(r"<[^>]+>", "", text)
        # Remove excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        # Remove common noise patterns
        text = re.sub(
            r"(Subscribe|Sign up|Newsletter|Advertisement|Cookie|Privacy Policy).*?\n",
            "",
            text,
            flags=re.IGNORECASE,
        )
        return text.strip()

    @staticmethod
    def _is_recent(date_str: str | None, days: int = 7) -> bool:
        """Check if a date string represents a date within the last N days."""
        if not date_str:
            return True  # Assume recent if no date available

        try:
            # Try common date formats
            for fmt in [
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d",
                "%B %d, %Y",
                "%b %d, %Y",
                "%d %B %Y",
                "%d %b %Y",
            ]:
                try:
                    parsed = datetime.strptime(date_str[:26], fmt)
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
                    return parsed >= cutoff
                except ValueError:
                    continue

            return True  # If we can't parse, assume recent
        except Exception:
            return True
