"""
Search module using Tavily Search API.

Executes multiple renewable energy queries, deduplicates results
by URL and fuzzy title matching, and returns unique SearchResult objects.
"""

import asyncio
import logging
from difflib import SequenceMatcher
from urllib.parse import urlparse

from tavily import TavilyClient

from src.config import (
    MAX_RESULTS_PER_QUERY,
    SEARCH_QUERIES,
    SEARCH_TIME_RANGE,
    TAVILY_API_KEY,
    TITLE_SIMILARITY_THRESHOLD,
    TRUSTED_DOMAINS,
)
from src.models import SearchResult

logger = logging.getLogger(__name__)


class NewsSearcher:
    """Searches for renewable energy news using the Tavily API."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or TAVILY_API_KEY
        if not self.api_key:
            raise ValueError(
                "TAVILY_API_KEY is required. Set it in your .env file."
            )
        self.client = TavilyClient(api_key=self.api_key)

    def _execute_search(self, query: str) -> list[dict]:
        """Execute a single Tavily search query."""
        try:
            logger.info("Searching: '%s'", query)
            response = self.client.search(
                query=query,
                search_depth="advanced",
                time_range=SEARCH_TIME_RANGE,
                max_results=MAX_RESULTS_PER_QUERY,
                include_raw_content=True,
            )
            results = response.get("results", [])
            logger.info("  → Found %d results for: '%s'", len(results), query)
            return results
        except Exception as e:
            logger.error("Search failed for '%s': %s", query, e)
            return []

    async def search_all(
        self, queries: list[str] | None = None
    ) -> list[SearchResult]:
        """
        Execute all search queries and return deduplicated results.

        Uses asyncio to run searches concurrently via thread executor
        since the Tavily SDK is synchronous.
        """
        queries = queries or SEARCH_QUERIES
        logger.info("Starting search with %d queries...", len(queries))

        # Run searches concurrently using thread pool
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(None, self._execute_search, query)
            for query in queries
        ]
        all_raw_results = await asyncio.gather(*tasks)

        # Flatten results
        raw_results: list[dict] = []
        for results in all_raw_results:
            raw_results.extend(results)

        logger.info("Total raw results: %d", len(raw_results))

        # Convert to SearchResult models
        search_results = []
        for r in raw_results:
            try:
                sr = SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    content=r.get("content", ""),
                    raw_content=r.get("raw_content"),
                    published_date=r.get("published_date"),
                    score=r.get("score", 0.0),
                )
                search_results.append(sr)
            except Exception as e:
                logger.warning("Skipping invalid result: %s", e)

        # Deduplicate
        unique = self._deduplicate(search_results)
        logger.info(
            "After deduplication: %d unique articles (removed %d duplicates)",
            len(unique),
            len(search_results) - len(unique),
        )

        return unique

    def _deduplicate(self, results: list[SearchResult]) -> list[SearchResult]:
        """Remove duplicates by exact URL match and fuzzy title similarity."""
        seen_urls: set[str] = set()
        seen_titles: list[str] = []
        unique: list[SearchResult] = []

        for result in results:
            # Normalize URL (strip trailing slash, fragments)
            normalized_url = self._normalize_url(result.url)

            # Skip if URL already seen
            if normalized_url in seen_urls:
                logger.debug("Duplicate URL skipped: %s", result.url)
                continue

            # Skip if title is too similar to an already-seen title
            if self._is_title_duplicate(result.title, seen_titles):
                logger.debug("Duplicate title skipped: '%s'", result.title)
                continue

            seen_urls.add(normalized_url)
            seen_titles.append(result.title)
            unique.append(result)

        return unique

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Normalize URL for dedup comparison."""
        parsed = urlparse(url)
        # Remove fragment and trailing slash
        path = parsed.path.rstrip("/")
        return f"{parsed.scheme}://{parsed.netloc}{path}"

    @staticmethod
    def _is_title_duplicate(
        title: str, seen_titles: list[str]
    ) -> bool:
        """Check if a title is too similar to any previously seen title."""
        if not title:
            return False
        for seen in seen_titles:
            ratio = SequenceMatcher(None, title.lower(), seen.lower()).ratio()
            if ratio >= TITLE_SIMILARITY_THRESHOLD:
                return True
        return False

    def _is_trusted_source(self, url: str) -> bool:
        """Check if a URL belongs to a trusted news source."""
        domain = urlparse(url).netloc.lower()
        # Remove 'www.' prefix
        if domain.startswith("www."):
            domain = domain[4:]
        return any(trusted in domain for trusted in TRUSTED_DOMAINS)
