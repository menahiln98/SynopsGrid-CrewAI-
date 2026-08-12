"""
Vercel serverless endpoint powering the SynopsGrid dashboard (public/index.html).

GET /api/dashboard
Reads the latest run's stats from the "Runs" tab and its stories from the
"Stories" tab (both written by SheetsLoggerTool) and returns JSON shaped
for the frontend to render directly -- no auth required, read-only.
"""

import json
import os
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import NEWS_CATEGORY_SCOPE  # noqa: E402

STORIES_SHEET_TITLE = "Stories"
RUNS_SHEET_TITLE = "Runs"


def _get_sheets_client():
    import gspread
    from google.oauth2.service_account import Credentials

    creds_raw = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if not creds_raw or not sheet_id:
        return None, None

    if os.path.exists(creds_raw):
        with open(creds_raw, "r") as f:
            creds_info = json.load(f)
    else:
        creds_info = json.loads(creds_raw)

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = Credentials.from_service_account_info(creds_info, scopes=scopes)
    client = gspread.authorize(credentials)
    return client, sheet_id


def _row_to_bool(value) -> bool:
    return str(value).strip().upper() in ("TRUE", "1", "YES")


def build_dashboard_payload() -> dict:
    client, sheet_id = _get_sheets_client()

    if client is None:
        return _empty_payload(note="Google Sheets not configured yet.")

    try:
        spreadsheet = client.open_by_key(sheet_id)
        runs_records = spreadsheet.worksheet(RUNS_SHEET_TITLE).get_all_records()
        stories_records = spreadsheet.worksheet(STORIES_SHEET_TITLE).get_all_records()
    except Exception as exc:
        return _empty_payload(note=f"No run data yet ({exc.__class__.__name__}). Run the pipeline first.")

    if not runs_records or not stories_records:
        return _empty_payload(note="No run data yet. Click 'Run Pipeline' or wait for the next cron run.")

    latest_run = runs_records[-1]
    latest_timestamp = latest_run["run_timestamp_utc"]

    latest_stories = [r for r in stories_records if r["run_timestamp_utc"] == latest_timestamp]

    stories_published_count = sum(1 for r in latest_stories if _row_to_bool(r.get("published_to_slack")))
    sheets_logged_count = len(latest_stories)

    # Preserve first-seen order of topics for stable filter-chip ordering.
    topics = list(OrderedDict.fromkeys(r["topic"] for r in latest_stories if r.get("topic")))

    stories_payload = [
        {
            "title": r["title"],
            "summary": r["summary"],
            "why_it_matters": r["why_it_matters"],
            "link": r["link"],
            "source": r["source"],
            "published_date": r["published_date"],
            "category": r["category"],
            "topic": r.get("topic", ""),
            "relevance_score": float(r["relevance_score"]),
            "published_to_slack": _row_to_bool(r.get("published_to_slack")),
        }
        for r in sorted(latest_stories, key=lambda x: float(x["relevance_score"]), reverse=True)
    ]

    try:
        dt = datetime.fromisoformat(latest_timestamp.replace("Z", "+00:00"))
    except ValueError:
        dt = datetime.now(timezone.utc)

    return {
        "ok": True,
        "note": None,
        "last_run_utc": latest_timestamp,
        "date_label": dt.strftime("%B %-d, %Y") if os.name != "nt" else dt.strftime("%B %d, %Y"),
        "category_scope": NEWS_CATEGORY_SCOPE,
        "pipeline": {
            "researcher": {"count": int(latest_run["articles_fetched"])},
            "summarizer": {"count": int(latest_run["stories_after_dedup"])},
            "publisher": {"count": stories_published_count},
        },
        "stats": {
            "fetched": int(latest_run["articles_fetched"]),
            "after_dedup": int(latest_run["stories_after_dedup"]),
            "duplicates_removed": int(latest_run["duplicates_removed"]),
            "scored": int(latest_run["stories_after_dedup"]),
            "avg_score": float(latest_run["avg_relevance_score"]),
            "published_to_slack": stories_published_count,
            "logged_to_sheets": sheets_logged_count,
        },
        "topics": topics,
        "stories": stories_payload,
    }


def _empty_payload(note: str) -> dict:
    return {
        "ok": False,
        "note": note,
        "last_run_utc": None,
        "date_label": datetime.now(timezone.utc).strftime("%B %d, %Y"),
        "category_scope": NEWS_CATEGORY_SCOPE,
        "pipeline": {"researcher": {"count": 0}, "summarizer": {"count": 0}, "publisher": {"count": 0}},
        "stats": {
            "fetched": 0,
            "after_dedup": 0,
            "duplicates_removed": 0,
            "scored": 0,
            "avg_score": 0,
            "published_to_slack": 0,
            "logged_to_sheets": 0,
        },
        "topics": [],
        "stories": [],
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            payload = build_dashboard_payload()
            self._send_json(200, payload)
        except Exception as exc:
            self._send_json(500, {"ok": False, "note": str(exc)})

    def _send_json(self, status_code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
