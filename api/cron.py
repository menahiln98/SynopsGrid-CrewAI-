"""
Vercel serverless entrypoint. This is the endpoint Vercel Cron (or an
external scheduler, see README) hits every N hours to trigger a crew run.

Deployed URL: https://<your-project>.vercel.app/api/cron

Protected by CRON_SECRET: any request must send
    Authorization: Bearer <CRON_SECRET>
Vercel's own built-in Cron Jobs feature sets this header automatically
once CRON_SECRET is set as a project env var.
"""

import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler

# Make the project root importable (api/ is a subfolder).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.crew import run_crew  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._handle()

    def do_POST(self):
        self._handle()

    def _handle(self):
        expected_secret = os.getenv("CRON_SECRET")
        auth_header = self.headers.get("Authorization", "")

        if expected_secret and auth_header != f"Bearer {expected_secret}":
            self._send_json(401, {"error": "Unauthorized"})
            return

        try:
            result = run_crew()
            self._send_json(200, {"status": "ok", "result": result["pydantic"]})
        except Exception as exc:  # keep the function alive, report the failure clearly
            traceback.print_exc()
            self._send_json(500, {"status": "error", "message": str(exc)})

    def _send_json(self, status_code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
