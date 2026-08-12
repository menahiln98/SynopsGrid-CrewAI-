"""
Custom Intelligent Summarizer Tool.

Takes the raw articles JSON produced by NewsFetcherTool and turns it into
clean, de-duplicated, *structured* stories: summary, why-it-matters,
category and a relevance score — via a direct LLM call (through litellm,
the same library CrewAI uses under the hood), independent of any
crewai-tools built-in.
"""

import json
import os
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ValidationError

from src.schemas import NewsFetchResult, SummaryResult

SUMMARIZER_SYSTEM_PROMPT = """You are an expert news editor for a business/tech \
intelligence desk. You will receive a JSON array of raw news articles (title, \
link, snippet, source, published_date, topic).

Your job:
1. Merge near-duplicate articles covering the same underlying story (keep the \
   best-sourced version, count the rest as duplicates removed).
2. For each remaining story, write:
   - a clean title
   - a 2-3 sentence plain-English summary based ONLY on the given snippet/title \
     (never invent facts not implied by the input)
   - one line on "why it matters" for a business/tech audience
   - a category label (Business, Technology, Funding, Markets, Policy, or Other)
   - a relevance_score from 1-10 for how significant/impactful the story is
3. Keep the original link, source, published_date, and topic (copy the "topic" \
   field verbatim from the source article — if two duplicates had different \
   topics, keep the topic of the article you chose to keep).

Respond with ONLY valid JSON matching this exact shape, no markdown fences, no \
commentary:
{
  "stories": [
    {
      "title": "...",
      "summary": "...",
      "why_it_matters": "...",
      "link": "...",
      "source": "...",
      "published_date": "...",
      "category": "...",
      "topic": "...",
      "relevance_score": 7
    }
  ],
  "duplicates_removed": 0
}
"""


class SummarizerInput(BaseModel):
    """Input schema for the Intelligent Summarizer Tool."""

    raw_articles_json: str = Field(
        ..., description="JSON string produced by the News Fetcher Tool (a NewsFetchResult)."
    )
    category_scope: str = Field(
        default="Business & Technology",
        description="Editorial scope to filter/tag stories against, e.g. 'Business & Technology'.",
    )


class SummarizerTool(BaseTool):
    name: str = "Intelligent Summarizer Tool"
    description: str = (
        "Summarizes and de-duplicates a batch of raw news articles into structured "
        "stories (title, summary, why-it-matters, category, relevance score) using "
        "an LLM call. Input must be the JSON output of the News Fetcher Tool."
    )
    args_schema: Type[BaseModel] = SummarizerInput

    def _run(self, raw_articles_json: str, category_scope: str = "Business & Technology") -> str:
        try:
            fetch_result = NewsFetchResult.model_validate_json(raw_articles_json)
        except (ValidationError, ValueError):
            return SummaryResult(stories=[], duplicates_removed=0).model_dump_json()

        if not fetch_result.articles:
            return SummaryResult(stories=[], duplicates_removed=0).model_dump_json()

        articles_payload = [a.model_dump() for a in fetch_result.articles]

        try:
            import litellm
        except ImportError as exc:
            raise ImportError("Missing dependency 'litellm'. Install it with: pip install litellm") from exc

        from src.config import get_settings

        settings = get_settings()
        model = settings.llm_model_string

        user_prompt = (
            f"Editorial scope: {category_scope}\n\n"
            f"Raw articles JSON:\n{json.dumps(articles_payload, ensure_ascii=False)}"
        )

        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": SUMMARIZER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        content = response["choices"][0]["message"]["content"]

        try:
            parsed = json.loads(content)
            result = SummaryResult.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError) as exc:
            print(f"[SummarizerTool] Failed to parse LLM output as SummaryResult: {exc}")
            return SummaryResult(stories=[], duplicates_removed=0, articles_fetched=len(fetch_result.articles)).model_dump_json()

        # Don't trust the LLM to count accurately — set this from ground truth.
        result.articles_fetched = len(fetch_result.articles)

        return result.model_dump_json()
