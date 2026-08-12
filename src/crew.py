"""
Assembles the Crew: Researcher -> Summarizer -> Publisher, sequential process.
"""

from crewai import Crew, Process

from src.agents import build_agents
from src.tasks import build_tasks
from src.config import get_settings, TOPICS, NEWS_CATEGORY_SCOPE, ARTICLES_PER_TOPIC, MAX_STORIES_TO_PUBLISH

# --- Workaround for CrewAI bug #5886 ---------------------------------------
# CrewAI's native tool-calling path tags every outgoing message with a
# `cache_breakpoint` marker intended for Anthropic's prompt-caching feature.
# Only the Anthropic provider adapter knows to strip that marker back out
# before the request goes out — every other provider (Groq, Gemini via
# OpenAI-compatible endpoints, etc.) gets sent the raw marker and rejects the
# request outright with a 400. We're not using Anthropic here, so disabling
# the marker entirely is safe and has no effect on summary quality.
# https://github.com/crewAIInc/crewAI/issues/5886 — remove this block once
# CrewAI ships a real fix and you've confirmed it works without it.
try:
    import crewai.llms.cache as _crewai_cache

    _crewai_cache.mark_cache_breakpoint = lambda msg: msg
except ImportError:
    pass
# -----------------------------------------------------------------------------


def build_crew(
    topics: list = None,
    category_scope: str = None,
    articles_per_topic: int = None,
    max_stories: int = None,
) -> Crew:
    settings = get_settings()

    topics = topics or TOPICS
    category_scope = category_scope or NEWS_CATEGORY_SCOPE
    articles_per_topic = articles_per_topic or ARTICLES_PER_TOPIC
    max_stories = max_stories or MAX_STORIES_TO_PUBLISH

    agents = build_agents(settings)
    tasks = build_tasks(agents, topics, category_scope, articles_per_topic, max_stories)

    return Crew(
        agents=[agents["researcher"], agents["summarizer"], agents["publisher"]],
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
    )


def run_crew(**kwargs) -> dict:
    """Runs the crew end-to-end and returns a plain dict result summary."""
    crew = build_crew(**kwargs)
    result = crew.kickoff()

    return {
        "raw": str(result),
        "pydantic": result.pydantic.model_dump() if result.pydantic else None,
        "token_usage": result.token_usage.model_dump() if getattr(result, "token_usage", None) else None,
    }