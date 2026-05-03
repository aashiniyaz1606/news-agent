"""
Database module for storing processed articles in SQLite.

Uses aiosqlite for async operations. Handles schema creation,
article insertion with upsert logic, and querying.
"""

import json
import logging
from pathlib import Path

import aiosqlite

from src.config import DB_PATH
from src.models import ProcessedArticle

logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content_summary TEXT NOT NULL,
    link TEXT UNIQUE NOT NULL,
    images_links TEXT,
    published_date TEXT,
    created_at TEXT NOT NULL,
    tags TEXT,
    sentiment TEXT
);
"""

INSERT_SQL = """
INSERT OR IGNORE INTO articles
    (title, content_summary, link, images_links, published_date, created_at, tags, sentiment)
VALUES
    (?, ?, ?, ?, ?, ?, ?, ?);
"""

SELECT_ALL_SQL = """
SELECT id, title, content_summary, link, images_links, published_date, created_at, tags, sentiment
FROM articles
ORDER BY created_at DESC;
"""

CHECK_EXISTS_SQL = """
SELECT 1 FROM articles WHERE link = ? LIMIT 1;
"""


class NewsDatabase:
    """Async SQLite database for storing news articles."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or DB_PATH
        # Ensure parent directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        logger.info("Database path: %s", self.db_path)

    async def init_db(self) -> None:
        """Create the articles table if it doesn't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(CREATE_TABLE_SQL)
            await db.commit()
        logger.info("Database initialized")

    async def insert_article(self, article: ProcessedArticle) -> bool:
        """
        Insert a single article into the database.
        Returns True if inserted, False if already exists (duplicate link).
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                INSERT_SQL,
                (
                    article.title,
                    article.content_summary,
                    article.link,
                    json.dumps(article.images_links),
                    article.published_date,
                    article.created_at,
                    json.dumps(article.tags),
                    article.sentiment,
                ),
            )
            await db.commit()

            if cursor.rowcount > 0:
                logger.debug("Inserted article: %s", article.title[:60])
                return True
            else:
                logger.debug("Article already exists: %s", article.link)
                return False

    async def insert_articles_batch(
        self, articles: list[ProcessedArticle]
    ) -> tuple[int, int]:
        """
        Insert multiple articles in a single transaction.
        Returns (inserted_count, skipped_count).
        """
        inserted = 0
        skipped = 0

        async with aiosqlite.connect(self.db_path) as db:
            for article in articles:
                try:
                    cursor = await db.execute(
                        INSERT_SQL,
                        (
                            article.title,
                            article.content_summary,
                            article.link,
                            json.dumps(article.images_links),
                            article.published_date,
                            article.created_at,
                            json.dumps(article.tags),
                            article.sentiment,
                        ),
                    )
                    if cursor.rowcount > 0:
                        inserted += 1
                    else:
                        skipped += 1
                except Exception as e:
                    logger.warning(
                        "Failed to insert article '%s': %s",
                        article.title[:60],
                        e,
                    )
                    skipped += 1

            await db.commit()

        logger.info(
            "Batch insert: %d inserted, %d skipped", inserted, skipped
        )
        return inserted, skipped

    async def article_exists(self, link: str) -> bool:
        """Check if an article with the given link already exists."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(CHECK_EXISTS_SQL, (link,))
            row = await cursor.fetchone()
            return row is not None

    async def get_all_articles(self) -> list[dict]:
        """Retrieve all articles from the database."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(SELECT_ALL_SQL)
            rows = await cursor.fetchall()

            articles = []
            for row in rows:
                articles.append(
                    {
                        "id": row["id"],
                        "title": row["title"],
                        "content_summary": row["content_summary"],
                        "link": row["link"],
                        "images_links": json.loads(row["images_links"] or "[]"),
                        "published_date": row["published_date"],
                        "created_at": row["created_at"],
                        "tags": json.loads(row["tags"] or "[]"),
                        "sentiment": row["sentiment"],
                    }
                )
            return articles

    async def get_article_count(self) -> int:
        """Get the total number of articles in the database."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM articles")
            row = await cursor.fetchone()
            return row[0] if row else 0
