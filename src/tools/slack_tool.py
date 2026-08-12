"""
Custom Slack Notifier Tool — posts formatted messages to a private Slack
channel via an Incoming Webhook URL (no bot token / OAuth scopes needed,
matches the "webhook + connect agent" setup you described).
"""

import os
from typing import List, Type

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ValidationError

from src.schemas import SummaryResult


class SlackNotifierInput(BaseModel):
    """Input schema for the Slack Notifier Tool."""

    summary_json: str = Field(
        ..., description="JSON string produced by the Intelligent Summarizer Tool (a SummaryResult)."
    )
    max_stories: int = Field(default=6, description="Max number of top stories to post.")


class SlackNotifierTool(BaseTool):
    name: str = "Slack Notifier Tool"
    description: str = (
        "Posts a ranked digest of summarized news stories to a private Slack channel "
        "using an Incoming Webhook. Each story includes title, summary, link and date. "
        "Input must be the JSON output of the Intelligent Summarizer Tool."
    )
    args_schema: Type[BaseModel] = SlackNotifierInput

    def _run(self, summary_json: str, max_stories: int = 6) -> str:
        webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        if not webhook_url:
            return "SLACK_WEBHOOK_URL not set — skipped Slack post."

        try:
            summary = SummaryResult.model_validate_json(summary_json)
        except (ValidationError, ValueError) as exc:
            return f"Could not parse summary JSON: {exc}"

        if not summary.stories:
            return "No stories to post."

        stories = sorted(summary.stories, key=lambda s: s.relevance_score, reverse=True)[:max_stories]

        blocks = self._build_blocks(stories)
        payload = {
            "text": f"📰 News digest — {len(stories)} stories",  # fallback text for notifications
            "blocks": blocks,
        }

        response = requests.post(webhook_url, json=payload, timeout=15)
        if response.status_code != 200:
            return f"Slack post failed ({response.status_code}): {response.text}"

        return f"Posted {len(stories)} stories to Slack."

    @staticmethod
    def _build_blocks(stories) -> List[dict]:
        blocks: List[dict] = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "📰 Business & Tech News Digest"},
            },
            {"type": "divider"},
        ]

        for story in stories:
            score_bar = "🔥" if story.relevance_score >= 8 else "📌" if story.relevance_score >= 5 else "🔹"
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"{score_bar} *<{story.link}|{story.title}>*\n"
                            f"{story.summary}\n"
                            f"_Why it matters:_ {story.why_it_matters}"
                        ),
                    },
                }
            )
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": (
                                f"*{story.category}* · {story.source} · {story.published_date or 'n/a'} "
                                f"· relevance {story.relevance_score}/10"
                            ),
                        }
                    ],
                }
            )
            blocks.append({"type": "divider"})

        return blocks
