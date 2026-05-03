"""
Summarization module using Google Gemini via LangChain.

Processes scraped articles through an LLM to generate factual,
neutral summaries with tags and sentiment analysis.
Rate-limited to respect API quotas.
"""

import asyncio
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from src.config import (
    GOOGLE_API_KEY,
    LLM_MODEL,
    LLM_RATE_LIMIT_DELAY,
    LLM_TEMPERATURE,
    SUMMARY_MAX_WORDS,
    SUMMARY_MIN_WORDS,
)
from src.models import LLMSummaryResponse, ScrapedArticle

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""You are a professional news editor specializing in renewable energy.
Your task is to summarize news articles accurately and neutrally.

STRICT RULES:
1. Summarize ONLY what is in the provided article text. Do NOT add any external information.
2. Keep the summary between {SUMMARY_MIN_WORDS} and {SUMMARY_MAX_WORDS} words.
3. Use a neutral, factual tone — no opinions or editorializing.
4. Do NOT hallucinate or fabricate any facts, numbers, names, or quotes.
5. If the article text is unclear or incomplete, summarize only what is clearly stated.

You must also:
- Assign 1-3 tags from this list: solar, wind, storage, policy, innovation, hybrid, hydrogen, grid, EV, nuclear
- Classify the overall sentiment as: positive, neutral, or negative

Respond in EXACTLY this JSON format (no markdown, no code fences):
{{
  "content_summary": "Your 80-200 word summary here",
  "tags": ["tag1", "tag2"],
  "sentiment": "neutral"
}}
"""


class ArticleSummarizer:
    """Summarizes articles using Google Gemini via LangChain."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or GOOGLE_API_KEY
        if not self.api_key:
            raise ValueError(
                "GOOGLE_API_KEY is required. Set it in your .env file."
            )
        self.llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            google_api_key=self.api_key,
            temperature=LLM_TEMPERATURE,
            max_output_tokens=512,  # Keep responses short to save tokens
        )
        logger.info(
            "Summarizer initialized with model: %s (temp: %.1f)",
            LLM_MODEL,
            LLM_TEMPERATURE,
        )

    async def summarize_all(
        self, articles: list[ScrapedArticle]
    ) -> list[tuple[ScrapedArticle, LLMSummaryResponse]]:
        """
        Summarize all articles sequentially with rate limiting.

        Returns list of (article, summary) tuples for successfully processed articles.
        """
        logger.info("Starting summarization of %d articles...", len(articles))
        results: list[tuple[ScrapedArticle, LLMSummaryResponse]] = []

        for i, article in enumerate(articles):
            logger.info(
                "Summarizing [%d/%d]: '%s'",
                i + 1,
                len(articles),
                article.title[:60],
            )

            try:
                summary = await self._summarize_single(article)
                if summary:
                    results.append((article, summary))
                    logger.info(
                        "  → Summary: %d words, tags: %s, sentiment: %s",
                        len(summary.content_summary.split()),
                        summary.tags,
                        summary.sentiment,
                    )
                else:
                    logger.warning("  → Failed to get valid summary")
            except Exception as e:
                logger.error(
                    "  → Error summarizing '%s': %s", article.title[:60], e
                )

            # Rate limiting — wait between API calls
            if i < len(articles) - 1:
                await asyncio.sleep(LLM_RATE_LIMIT_DELAY)

        logger.info(
            "Summarization complete: %d / %d succeeded",
            len(results),
            len(articles),
        )
        return results

    async def _summarize_single(
        self, article: ScrapedArticle
    ) -> LLMSummaryResponse | None:
        """Summarize a single article."""
        # Truncate article text to save tokens (first ~3000 chars is enough)
        truncated_text = article.full_text[:3000]
        if len(article.full_text) > 3000:
            truncated_text += "\n\n[Article truncated for processing]"

        user_prompt = f"""Summarize the following renewable energy news article.

TITLE: {article.title}
SOURCE: {article.source_domain}
DATE: {article.published_date or "Unknown"}

ARTICLE TEXT:
{truncated_text}
"""

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]

        try:
            # Run LLM call in executor since it may be blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, self.llm.invoke, messages
            )

            raw_text = response.content.strip()

            # Clean up response — remove markdown code fences if present
            if raw_text.startswith("```"):
                raw_text = raw_text.strip("`").strip()
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:].strip()

            # Parse JSON response
            import json

            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError:
                # Try to extract JSON from response
                import re
                json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                else:
                    logger.warning("Could not parse LLM response as JSON")
                    return None

            summary = LLMSummaryResponse(
                content_summary=data.get("content_summary", ""),
                tags=data.get("tags", []),
                sentiment=data.get("sentiment", "neutral"),
            )

            # Validate summary length
            word_count = len(summary.content_summary.split())
            if word_count < 20:
                logger.warning(
                    "Summary too short (%d words), discarding", word_count
                )
                return None

            return summary

        except Exception as e:
            logger.error("LLM call failed: %s", e)
            return None
