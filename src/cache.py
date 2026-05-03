"""
File-based caching module to avoid redundant scraping.

Stores scraped article content keyed by URL hash with a configurable TTL.
"""

import hashlib
import json
import logging
import time
from pathlib import Path

from src.config import CACHE_DIR, CACHE_TTL_HOURS

logger = logging.getLogger(__name__)


class ArticleCache:
    """Simple file-based cache for scraped article content."""

    def __init__(self, cache_dir: str | None = None, ttl_hours: int | None = None):
        self.cache_dir = Path(cache_dir or CACHE_DIR)
        self.ttl_seconds = (ttl_hours or CACHE_TTL_HOURS) * 3600
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Cache directory: %s (TTL: %dh)", self.cache_dir, ttl_hours or CACHE_TTL_HOURS)

    def _url_to_key(self, url: str) -> str:
        """Generate a cache key from a URL."""
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    def _cache_path(self, url: str) -> Path:
        """Get the file path for a cached URL."""
        return self.cache_dir / f"{self._url_to_key(url)}.json"

    def is_cached(self, url: str) -> bool:
        """Check if a URL is cached and not expired."""
        path = self._cache_path(url)
        if not path.exists():
            return False

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            cached_at = data.get("cached_at", 0)
            if time.time() - cached_at > self.ttl_seconds:
                logger.debug("Cache expired for: %s", url)
                path.unlink(missing_ok=True)
                return False
            return True
        except (json.JSONDecodeError, KeyError):
            path.unlink(missing_ok=True)
            return False

    def get(self, url: str) -> dict | None:
        """Retrieve cached content for a URL."""
        if not self.is_cached(url):
            return None

        path = self._cache_path(url)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            logger.debug("Cache hit for: %s", url)
            return data.get("content")
        except (json.JSONDecodeError, KeyError):
            return None

    def set(self, url: str, content: dict) -> None:
        """Store content in cache for a URL."""
        path = self._cache_path(url)
        cache_entry = {
            "url": url,
            "cached_at": time.time(),
            "content": content,
        }
        try:
            path.write_text(
                json.dumps(cache_entry, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.debug("Cached content for: %s", url)
        except OSError as e:
            logger.warning("Failed to write cache for %s: %s", url, e)

    def clear(self) -> int:
        """Clear all cached files. Returns count of files removed."""
        count = 0
        for path in self.cache_dir.glob("*.json"):
            path.unlink(missing_ok=True)
            count += 1
        logger.info("Cleared %d cached files", count)
        return count

    def clear_expired(self) -> int:
        """Remove only expired cache entries. Returns count of files removed."""
        count = 0
        for path in self.cache_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                cached_at = data.get("cached_at", 0)
                if time.time() - cached_at > self.ttl_seconds:
                    path.unlink(missing_ok=True)
                    count += 1
            except (json.JSONDecodeError, OSError):
                path.unlink(missing_ok=True)
                count += 1
        logger.info("Cleared %d expired cache files", count)
        return count
