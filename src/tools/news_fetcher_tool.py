"""
Custom News Fetcher Tool — built from scratch on top of SerpAPI's Google
News engine (not crewai-tools' built-in SerperDevTool). This is what the
Researcher / "web searcher" agent uses.
"""

import os
from typing import List, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from src.schemas import RawArticle, NewsFetchResult


class NewsFetcherInput(BaseModel):
    """Input schema for the News Fetcher Tool."""

    topics: List[str] = Field(
        ...,
        description=(
            "List of search topics/queries to fetch fresh news for, e.g. "
            "['artificial intelligence business', 'startup funding Pakistan']."
        ),
    )
    articles_per_topic: int = Field(
        default=5, ge=1, le=15, description="Max number of articles to pull per topic."
    )


class NewsFetcherTool(BaseTool):
    name: str = "News Fetcher Tool"
    description: str = (
        "Fetches recent news articles for one or more topics using SerpAPI's Google "
        "News engine. Returns structured JSON (title, link, snippet, source, "
        "published_date, topic) for every article found — no scraping, no built-in "
        "CrewAI search tool involved."
    )
    args_schema: Type[BaseModel] = NewsFetcherInput

    def _run(self, topics: List[str], articles_per_topic: int = 5) -> str:
        try:
            from serpapi import GoogleSearch
        except ImportError as exc:
            raise ImportError(
                "Missing dependency 'google-search-results'. Install it with: "
                "pip install google-search-results"
            ) from exc

        api_key = os.getenv("SERPAPI_API_KEY")
        if not api_key:
            return NewsFetchResult(articles=[], topics_searched=[]).model_dump_json()

        all_articles: List[RawArticle] = []

        for topic in topics:
            params = {
                "engine": "google_news",
                "q": topic,
                "api_key": api_key,
                "gl": "us",
                "hl": "en",
            }
            try:
                search = GoogleSearch(params)
                results = search.get_dict()
            except Exception as exc:  # network / API errors shouldn't kill the whole run
                print(f"[NewsFetcherTool] SerpAPI error for topic '{topic}': {exc}")
                continue

            # Google News groups some hits into a "topic cluster": the top-level
            # item is just a cluster header (title = the topic name, link/snippet
            # empty) and the real articles live in its nested "stories" array.
            # Flatten those out before applying the per-topic limit.
            flat_entries = []
            for item in results.get("news_results", []):
                nested = item.get("stories") or []
                if nested:
                    flat_entries.extend(nested)
                else:
                    flat_entries.append(item)

            for entry in flat_entries[:articles_per_topic]:
                if not entry.get("link"):
                    continue
                source = entry.get("source")
                source_name = source.get("name", "Unknown") if isinstance(source, dict) else str(source or "Unknown")
                all_articles.append(
                    RawArticle(
                        title=entry.get("title", "Untitled"),
                        link=entry.get("link", ""),
                        snippet=entry.get("snippet", ""),
                        source=source_name,
                        published_date=entry.get("date", ""),
                        topic=topic,
                    )
                )

        result = NewsFetchResult(articles=all_articles, topics_searched=topics)
        return result.model_dump_json()