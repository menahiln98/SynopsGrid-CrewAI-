"""
Central configuration for the News Automation Crew.

Everything that changes between environments (local vs Vercel) or between
runs (which topics, how far back, where to post) lives here so the rest
of the codebase never touches os.environ directly.
"""

import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

load_dotenv()  # no-op on Vercel (env vars are injected directly), used for local dev


def _get_env(name: str, required: bool = True, default: str = "") -> str:
    value = os.getenv(name, default)
    if required and not value:
        raise EnvironmentError(
            f"Missing required environment variable: {name}. "
            f"Set it in your .env file (local) or Vercel project settings (deployed)."
        )
    return value


@dataclass
class Settings:
    # --- Search / research ---
    serpapi_api_key: str = field(default_factory=lambda: _get_env("SERPAPI_API_KEY"))

    # --- LLM (used by the Summarizer agent + the CrewAI agents themselves) ---
    # LLM_PROVIDER: "groq" (openai/gpt-oss-120b, free tier) or "gemini" (Flash / Flash-Lite, free tier)
    llm_provider: str = field(default_factory=lambda: _get_env("LLM_PROVIDER", default="groq"))
    groq_api_key: str = field(default_factory=lambda: _get_env("GROQ_API_KEY", required=False))
    gemini_api_key: str = field(default_factory=lambda: _get_env("GEMINI_API_KEY", required=False))
    openai_api_key: str = field(default_factory=lambda: _get_env("OPENAI_API_KEY", required=False))
    model_name: str = field(default_factory=lambda: _get_env("MODEL_NAME", required=False, default=""))

    # --- Slack ---
    slack_webhook_url: str = field(default_factory=lambda: _get_env("SLACK_WEBHOOK_URL"))

    # --- Google Sheets ---
    google_sheets_credentials_json: str = field(
        default_factory=lambda: _get_env("GOOGLE_SHEETS_CREDENTIALS_JSON")
    )
    google_sheet_id: str = field(default_factory=lambda: _get_env("GOOGLE_SHEET_ID"))

    # --- Security for the Vercel cron endpoint ---
    cron_secret: str = field(default_factory=lambda: _get_env("CRON_SECRET", required=False))

    @property
    def llm_model_string(self) -> str:
        """Returns a litellm-style model string CrewAI's LLM() understands.

        Free-tier defaults:
          - groq   -> openai/gpt-oss-120b (free on Groq's tier)
          - gemini -> gemini-3.1-flash-lite (free on Google AI Studio's tier)
        Override any of these with MODEL_NAME in your env without touching code.
        """
        if self.model_name:
            return self.model_name
        if self.llm_provider == "groq":
            return "groq/openai/gpt-oss-120b"
        if self.llm_provider == "gemini":
            return "gemini/gemini-3.6-flash"
        return "gpt-4o-mini"

    @property
    def llm_api_key(self) -> str:
        if self.llm_provider == "groq":
            return self.groq_api_key
        if self.llm_provider == "gemini":
            return self.gemini_api_key
        return self.openai_api_key


# ---------------------------------------------------------------------------
# Editorial scope — this is the "narrow the scope" knob your mentor mentioned.
# Change TOPICS / CATEGORY to steer what the crew researches each run.
# ---------------------------------------------------------------------------

# Search queries the News Fetcher agent will run through SerpAPI (Google News).
TOPICS: List[str] = [
    "artificial intelligence business",
    "startup funding Pakistan",
    "big tech earnings",
]

# Free-text category label the Summarizer uses to filter/tag relevance.
# Keep this tight — it's what turns "all news" into "business/tech news only".
NEWS_CATEGORY_SCOPE = "Business & Technology"

# How many articles per topic to pull from SerpAPI.
ARTICLES_PER_TOPIC = 3

# How many top stories to actually push to Slack + Sheets after ranking.
MAX_STORIES_TO_PUBLISH = 4


def get_settings() -> Settings:
    """Lazily build Settings so importing this module never fails at import time."""
    return Settings()
