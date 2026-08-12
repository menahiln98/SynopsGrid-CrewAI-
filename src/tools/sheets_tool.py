"""
Custom Google Sheets Logger Tool -- appends every summarized story as a row
to a "Stories" tab, and one funnel-stats row per run to a "Runs" tab, via a
service account. The "Runs" tab is what powers the dashboard's stat cards
(fetched / after dedup / scored / published / logged) with real numbers
instead of guesses.
"""

import json
import os
from datetime import datetime, timezone
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ValidationError

from src.config import MAX_STORIES_TO_PUBLISH
from src.schemas import SummaryResult

STORIES_SHEET_TITLE = "Stories"
RUNS_SHEET_TITLE = "Runs"

STORIES_HEADER = [
    "run_timestamp_utc",
    "title",
    "category",
    "topic",
    "relevance_score",
    "published_to_slack",
    "summary",
    "why_it_matters",
    "source",
    "published_date",
    "link",
]

RUNS_HEADER = [
    "run_timestamp_utc",
    "articles_fetched",
    "stories_after_dedup",
    "duplicates_removed",
    "avg_relevance_score",
    "stories_published_to_slack",
]


class SheetsLoggerInput(BaseModel):
    """Input schema for the Google Sheets Logger Tool."""

    summary_json: str = Field(
        ..., description="JSON string produced by the Intelligent Summarizer Tool (a SummaryResult)."
    )


class SheetsLoggerTool(BaseTool):
    name: str = "Google Sheets Logger Tool"
    description: str = (
        "Appends every summarized story as a row to a 'Stories' tab, and one "
        "funnel-stats row to a 'Runs' tab, in a Google Sheet via a service account. "
        "Input must be the JSON output of the Intelligent Summarizer Tool."
    )
    args_schema: Type[BaseModel] = SheetsLoggerInput

    def _run(self, summary_json: str) -> str:
        try:
            import gspread
            from google.oauth2.service_account import Credentials
        except ImportError as exc:
            raise ImportError(
                "Missing dependencies. Install them with: pip install gspread google-auth"
            ) from exc

        creds_raw = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
        sheet_id = os.getenv("GOOGLE_SHEET_ID")
        if not creds_raw or not sheet_id:
            return "Google Sheets credentials/ID not set -- skipped logging."

        try:
            summary = SummaryResult.model_validate_json(summary_json)
        except (ValidationError, ValueError) as exc:
            return f"Could not parse summary JSON: {exc}"

        if not summary.stories:
            return "No stories to log."

        # GOOGLE_SHEETS_CREDENTIALS_JSON can be either a filesystem path (local dev)
        # or the raw JSON content of the service account key (Vercel env var).
        if os.path.exists(creds_raw):
            with open(creds_raw, "r") as f:
                creds_info = json.load(f)
        else:
            creds_info = json.loads(creds_raw)

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        credentials = Credentials.from_service_account_info(creds_info, scopes=scopes)
        client = gspread.authorize(credentials)
        spreadsheet = client.open_by_key(sheet_id)

        stories_sheet = self._get_or_create_worksheet(spreadsheet, STORIES_SHEET_TITLE, STORIES_HEADER)
        runs_sheet = self._get_or_create_worksheet(spreadsheet, RUNS_SHEET_TITLE, RUNS_HEADER)

        timestamp = datetime.now(timezone.utc).isoformat()

        # Same ranking logic the Slack Notifier uses, so "published_to_slack" here
        # matches what actually landed in the channel.
        ranked = sorted(summary.stories, key=lambda s: s.relevance_score, reverse=True)
        published_links = {s.link for s in ranked[:MAX_STORIES_TO_PUBLISH]}

        story_rows = [
            [
                timestamp,
                story.title,
                story.category,
                story.topic,
                story.relevance_score,
                story.link in published_links,
                story.summary,
                story.why_it_matters,
                story.source,
                story.published_date,
                story.link,
            ]
            for story in summary.stories
        ]
        stories_sheet.append_rows(story_rows, value_input_option="USER_ENTERED")

        avg_score = round(sum(s.relevance_score for s in summary.stories) / len(summary.stories), 1)
        runs_sheet.append_row(
            [
                timestamp,
                summary.articles_fetched,
                len(summary.stories),
                summary.duplicates_removed,
                avg_score,
                len(published_links),
            ],
            value_input_option="USER_ENTERED",
        )

        return f"Appended {len(story_rows)} rows to '{STORIES_SHEET_TITLE}' and 1 row to '{RUNS_SHEET_TITLE}'."

    @staticmethod
    def _get_or_create_worksheet(spreadsheet, title: str, header: list):
        try:
            sheet = spreadsheet.worksheet(title)
        except Exception:
            sheet = spreadsheet.add_worksheet(title=title, rows=1000, cols=len(header) + 2)

        if not sheet.row_values(1):
            sheet.append_row(header)

        return sheet
