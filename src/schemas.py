"""
Pydantic models used as `output_pydantic` / `output_json` schemas on CrewAI
Tasks, and as the args_schema / return payloads for the custom tools.

Forcing every stage of the pipeline through a schema is what gives you
"structured data from agents" instead of free-text blobs you have to
regex apart later.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Stage 1 — News Fetcher Tool / Researcher Agent output
# ---------------------------------------------------------------------------

class RawArticle(BaseModel):
    title: str = Field(..., description="Headline as returned by the search engine")
    link: str = Field(..., description="Canonical URL of the article")
    snippet: str = Field(default="", description="Short excerpt / description from search results")
    source: str = Field(default="Unknown", description="Publisher name, e.g. Reuters, TechCrunch")
    published_date: str = Field(default="", description="Raw published date/time string from the source")
    topic: str = Field(..., description="The search query / topic this article was fetched for")


class NewsFetchResult(BaseModel):
    articles: List[RawArticle] = Field(default_factory=list)
    topics_searched: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 2 — Summarizer Tool / Intelligent Summarizer Agent output
# ---------------------------------------------------------------------------

class SummarizedStory(BaseModel):
    title: str = Field(..., description="Clean, de-duplicated headline")
    summary: str = Field(..., description="2-3 sentence plain-English summary")
    why_it_matters: str = Field(..., description="One-line takeaway on business/industry relevance")
    link: str = Field(..., description="Source URL")
    source: str = Field(default="Unknown")
    published_date: str = Field(default="")
    category: str = Field(..., description="e.g. Business, Technology, Funding, Markets")
    topic: str = Field(default="", description="Original search topic this story came from")
    relevance_score: int = Field(
        ..., ge=1, le=10, description="Agent-assigned relevance/impact score, 1 (low) - 10 (high)"
    )


class SummaryResult(BaseModel):
    stories: List[SummarizedStory] = Field(default_factory=list)
    duplicates_removed: int = Field(default=0)
    articles_fetched: int = Field(default=0, description="Raw article count before dedup/summarization")


# ---------------------------------------------------------------------------
# Stage 3 — Publisher / Distribution Agent output
# ---------------------------------------------------------------------------

class PublishReceipt(BaseModel):
    slack_posted: bool = False
    slack_message_count: int = 0
    sheet_rows_appended: int = 0
    errors: List[str] = Field(default_factory=list)


class PublishResult(BaseModel):
    stories_published: int
    receipt: PublishReceipt
    run_timestamp_utc: str
