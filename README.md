# News Intelligence Crew — CrewAI Multi-Agent News Automation

A CrewAI multi-agent pipeline that researches, summarizes, ranks, and
distributes business/tech news — fully automated, with structured
(Pydantic-validated) data at every stage, deployed on Vercel with a
scheduled cron trigger.

```
Researcher Agent  ---->  Intelligent Summarizer Agent  ---->  Publisher Agent
(News Fetcher Tool         (Summarizer Tool: LLM-based           (Slack Notifier Tool
 -> SerpAPI Google News)    structured summary + dedup            -> Slack webhook)
                            + relevance scoring)                 (Sheets Logger Tool
                                                                    -> Google Sheets)
```

Every custom tool here (`NewsFetcherTool`, `SummarizerTool`,
`SlackNotifierTool`, `SheetsLoggerTool`) is written from scratch as a
`crewai.tools.BaseTool` subclass with its own Pydantic `args_schema` — no
built-in `crewai_tools` package tools are used anywhere.

## What makes this different from a bare-bones version

- **Structured data everywhere.** Every task has an `output_pydantic`
  schema (`src/schemas.py`), so you never get free-text you have to
  regex apart — you get validated `NewsFetchResult`, `SummaryResult`,
  `PublishResult` objects.
- **Relevance scoring + ranking.** The Summarizer doesn't just summarize —
  it scores each story 1-10 for business impact, and the Publisher only
  posts the top N to Slack (configurable), so the channel doesn't get
  flooded.
- **"Why it matters" line.** Each Slack story includes a one-line
  business/industry takeaway, not just a headline + link.
- **De-duplication is explicit and counted.** `duplicates_removed` is
  part of the structured output, so you can see the pipeline actually
  did editorial work.
- **Scope is a single config knob.** `NEWS_CATEGORY_SCOPE` and `TOPICS`
  in `src/config.py` are what narrow this from "all news" to
  "business/tech only" — change them and the whole pipeline follows.

## Project layout

```
api/cron.py              Vercel serverless entrypoint (cron target, triggers a full run)
api/dashboard.py         Read-only endpoint that serves live stats/stories to the dashboard
public/index.html        The SynopsGrid dashboard — static, no build step
src/config.py            Env vars + editorial scope (TOPICS, category, limits)
src/schemas.py           Pydantic models — the "structured data" contracts
src/tools/
  news_fetcher_tool.py    Custom SerpAPI Google News tool
  summarizer_tool.py      Custom LLM-based summarizer + dedup tool
  slack_tool.py           Custom Slack Incoming Webhook tool
  sheets_tool.py          Custom Google Sheets logger tool (Stories + Runs tabs)
src/agents.py             Researcher / Summarizer / Publisher agent definitions
src/tasks.py              The 3 sequential tasks, wired to output_pydantic schemas
src/crew.py               Crew assembly (Process.sequential)
main.py                   Local run entrypoint
vercel.json               Cron schedule + function runtime config
```

## 1. Local setup (Windows)

Open PowerShell in your project folder:

```powershell
cd "C:\Users\NeXT GeN\Desktop\INTERNSHIP\CrewAI"
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Fill in `.env`:

| Variable | Where to get it |
|---|---|
| `SERPAPI_API_KEY` | [serpapi.com](https://serpapi.com) → Dashboard → API Key |
| `LLM_PROVIDER` + key | See "Choosing a free LLM" below — no paid key required |
| `SLACK_WEBHOOK_URL` | Slack → [api.slack.com/apps](https://api.slack.com/apps) → Create App → Incoming Webhooks → Add to your private channel |
| `GOOGLE_SHEETS_CREDENTIALS_JSON`, `GOOGLE_SHEET_ID` | Google Cloud Console → Service Account → create JSON key. Share the target Sheet with the service account's `client_email` as Editor. Copy the Sheet ID from its URL. |
| `CRON_SECRET` | Any random string — only needed for the deployed cron endpoint |

Run it:

```powershell
python main.py
```

## 2. Choosing a free LLM (no OpenAI key needed)

`LLM_PROVIDER` in `.env` picks which model powers the agents and the
Summarizer Tool's structured-output call — both are free-tier:

| `LLM_PROVIDER` | Default model | Get a key |
|---|---|---|
| `groq` (recommended — fast) | `openai/gpt-oss-120b` (OpenAI's open-weight model, free on Groq) | [console.groq.com](https://console.groq.com) → API Keys |
| `gemini` | `gemini-3.1-flash-lite` (Google's free-tier Flash model) | [aistudio.google.com](https://aistudio.google.com) → Get API Key |

Set the matching key (`GROQ_API_KEY` or `GEMINI_API_KEY`) and leave
`MODEL_NAME` blank to use the defaults above. If you want a specific
model instead — e.g. `gemini/gemini-3-flash` or `groq/llama-3.3-70b-versatile`
— set `MODEL_NAME` directly and it overrides everything.

Note Gemini's free tier only covers Flash / Flash-Lite models — Pro
models (`gemini-3.1-pro`, etc.) require billing, so stick to Flash-Lite
or Flash for this project.

## 3. Tune the scope

Edit `src/config.py`:

```python
TOPICS = [
    "artificial intelligence business",
    "startup funding Pakistan",
    "big tech earnings",
]
NEWS_CATEGORY_SCOPE = "Business & Technology"
ARTICLES_PER_TOPIC = 5
MAX_STORIES_TO_PUBLISH = 6
```

This is the whole "narrow the scope" lever — the Researcher searches
exactly these topics, the Summarizer tags/filters against this scope,
and the Publisher only ships the top `MAX_STORIES_TO_PUBLISH`.

## 4. Deploy to Vercel

```powershell
npm install -g vercel
vercel login
vercel link
vercel env add SERPAPI_API_KEY
vercel env add LLM_PROVIDER
vercel env add GROQ_API_KEY
:: or: vercel env add GEMINI_API_KEY   (if LLM_PROVIDER=gemini)
vercel env add SLACK_WEBHOOK_URL
vercel env add GOOGLE_SHEETS_CREDENTIALS_JSON
vercel env add GOOGLE_SHEET_ID
vercel env add CRON_SECRET
vercel --prod
```

For `GOOGLE_SHEETS_CREDENTIALS_JSON` on Vercel, paste the **entire
contents** of the service-account JSON file as the value (not a file
path — Vercel functions don't have your local filesystem). The tool
already handles both a JSON string and a local file path automatically.

Your cron endpoint is now live at:

```
https://<your-project>.vercel.app/api/cron
```

## 5. About the "every 4 hours" requirement — read this before you demo it

Vercel's **Hobby (free) plan cron jobs only fire once per day**, no
matter what cron expression you put in `vercel.json` — anything more
frequent gets rejected at deploy time. `0 */4 * * *` (every 4 hours,
already set in `vercel.json`) **requires the Pro plan** to actually run
on that schedule.

If you're on Hobby, you have two working options:

- **Ask your mentor for a Vercel Pro seat** (often free for
  students/interns via GitHub Student Pack), or
- **Keep the endpoint on Vercel, trigger it externally every 4 hours**
  with a free scheduler that just sends an authenticated HTTP request:
  - [cron-job.org](https://cron-job.org) (free, simplest) — set URL to
    your `/api/cron` endpoint, method GET, header
    `Authorization: Bearer <CRON_SECRET>`, schedule `0 */4 * * *`.
  - A GitHub Actions workflow with a `schedule:` trigger that does the
    same `curl` call.

Either way, remove or keep the `crons` block in `vercel.json` — it's
harmless on Hobby (it just won't fire more than daily); the external
scheduler covers the real 4-hour cadence.

Also note: serverless function duration limits scale with plan too
(Hobby caps `maxDuration` well below the 300s set here). If you're
staying on Hobby, shrink `TOPICS` / `ARTICLES_PER_TOPIC` so a full crew
run comfortably finishes within your plan's limit.

## 6. Structured data — where to see it

- `NewsFetchResult`, `SummaryResult`, `PublishResult` in `src/schemas.py`
  are what `output_pydantic` enforces on each Task. Access them locally
  via `result.pydantic` after `crew.kickoff()` (see `main.py`).
- The `/api/cron` endpoint returns the final `PublishResult` as JSON in
  the HTTP response body — check it in your scheduler's execution logs.

## 7. The dashboard

`public/index.html` is a live dashboard — no build step, Vercel serves it
as a static file automatically. It reads real numbers from your Google
Sheet via `/api/dashboard` (a read-only endpoint that pulls the latest
run's rows from the `Runs` and `Stories` tabs the pipeline writes to).

Once deployed, visit `https://<your-project>.vercel.app/` to see it.
Locally, you can preview the layout with the API mocked (see below), but
the real thing only lights up once you've run the crew at least once and
it has written to your Sheet.

- The **"Run Pipeline"** button calls `/api/cron` directly from the
  browser — it'll prompt you for `CRON_SECRET` before triggering a run.
  Runs can take 20-60 seconds; the button shows a loading state while it
  waits.
- The **filter chips** are generated from whatever topics appear in the
  latest run (driven by `TOPICS` in `src/config.py`) — no manual wiring
  needed when you change your topic list.
- The **"Why it matters"** toggle on each story expands the
  `why_it_matters` field the Summarizer wrote — this is real structured
  data, not decoration.
- Article images are intentionally *not* real photos (avoids scraping/
  copyright issues) — each story gets an original gradient art tile
  generated client-side based on its category.

If you ever want to sanity-check the dashboard's layout without running
the whole pipeline, you can temporarily point `fetch("/api/dashboard")`
in `public/index.html` at a local mock JSON file with fake data — useful
for iterating on the design without burning API calls.

## 8. Testing tools in isolation

```python
from src.tools.news_fetcher_tool import NewsFetcherTool

tool = NewsFetcherTool()
print(tool.run(topics=["AI regulation"], articles_per_topic=3))
```

Do the same for `SummarizerTool`, `SlackNotifierTool`, `SheetsLoggerTool`
before wiring them into the full crew — much faster than debugging
through an LLM agent loop.
