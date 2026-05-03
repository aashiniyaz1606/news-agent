"""
Pydantic data models for the news agent pipeline.

Defines typed, validated data structures for search results,
scraped articles, and final processed output.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


class SearchResult(BaseModel):
    """Raw search result returned from Tavily."""

    title: str
    url: str
    content: str = ""  # Tavily snippet
    raw_content: Optional[str] = None  # Full page content if available
    published_date: Optional[str] = None
    score: float = 0.0

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"Invalid URL: {v}")
        return v


class ScrapedArticle(BaseModel):
    """Article after full-text scraping."""

    title: str
    url: str
    full_text: str
    published_date: Optional[str] = None
    top_image: Optional[str] = None
    authors: list[str] = Field(default_factory=list)
    source_domain: str = ""

    @field_validator("full_text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v or len(v.strip()) < 50:
            raise ValueError("Article text is too short or empty")
        return v


class LLMSummaryResponse(BaseModel):
    """Structured response from the LLM summarization."""

    content_summary: str = Field(
        ..., description="Factual, neutral summary of the article in 80-200 words"
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Relevant tags: solar, wind, storage, policy, innovation, hybrid, hydrogen, grid, EV, nuclear",
    )
    sentiment: str = Field(
        default="neutral",
        description="Sentiment of the article: positive, neutral, or negative",
    )

    @field_validator("sentiment")
    @classmethod
    def validate_sentiment(cls, v: str) -> str:
        valid = {"positive", "neutral", "negative"}
        v_lower = v.lower().strip()
        if v_lower not in valid:
            return "neutral"
        return v_lower

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        valid_tags = {
            "solar", "wind", "storage", "policy", "innovation",
            "hybrid", "hydrogen", "grid", "EV", "nuclear",
        }
        return [t.lower().strip() for t in v if t.lower().strip() in valid_tags]


class ProcessedArticle(BaseModel):
    """Final processed article ready for output and database storage."""

    title: str
    content_summary: str
    link: str
    images_links: list[str] = Field(default_factory=list)
    published_date: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    tags: list[str] = Field(default_factory=list)
    sentiment: str = "neutral"

    def to_dict(self) -> dict:
        """Convert to plain dictionary for JSON serialization."""
        return {
            "title": self.title,
            "content_summary": self.content_summary,
            "link": self.link,
            "images_links": self.images_links,
            "published_date": self.published_date,
            "created_at": self.created_at,
            "tags": self.tags,
            "sentiment": self.sentiment,
        }
