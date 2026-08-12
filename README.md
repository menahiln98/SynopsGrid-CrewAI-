# SynopsGrid — CrewAI Multi-Agent News Automation

A CrewAI multi-agent pipeline that researches, summarizes, ranks, and
distributes business/tech news — fully automated, with structured
(Pydantic-validated) data at every stage, deployed on Vercel with a
scheduled cron trigger and a live dashboard.

```
Researcher Agent  ---->  Intelligent Summarizer Agent  ---->  Publisher Agent
(News Fetcher Tool         (Summarizer Tool: LLM-based           (Slack Notifier Tool
 -> SerpAPI Google News)    structured summary + dedup            -> Slack webhook)
                            + relevance scoring)                 (Sheets Logger Tool
                                                                    -> Google Sheets)
```

Every custom tool (`NewsFetcherTool`, `SummarizerTool`, `SlackNotifierTool`,
`SheetsLoggerTool`) is written from scratch as a `crewai.tools.BaseTool`
subclass with its own Pydantic `args_schema` — no built-in `crewai_tools`
package tools are used anywhere.

## Highlights

- **Structured data everywhere.** Every task has an `output_pydantic`
  schema (`src/schemas.py`), so each stage produces validated
  `NewsFetchResult`, `SummaryResult`, and `PublishResult` objects instead
  of free text.
- **Relevance scoring + ranking.** The Summarizer scores each story 1–10
  for business impact; the Publisher only posts the top N to Slack
  (configurable), so the channel doesn't get flooded.
- **"Why it matters" line.** Each Slack story includes a one-line
  business/industry takeaway, not just a headline and link.
- **De-duplication is explicit and counted.** `duplicates_removed` is
  part of the structured output, so the pipeline's editorial work is
  visible, not implicit.
- **Scope is a single config knob.** `NEWS_CATEGORY_SCOPE` and `TOPICS`
  in `src/config.py` narrow the pipeline from "all news" to "business/tech
  only" — change them and the whole pipeline follows.

## Project layout

```
api/cron.py              Vercel serverless entrypoint (cron target, triggers a full run)
api/dashboard.py         Read-only endpoint that serves live stats/stories to the dashboard
public/index.html        The SynopsGrid dashboard — static, no build step
src/config.py            Env vars + editorial scope (TOPICS, category, limits)
src/schemas.py           Pydantic models — the structured data contracts
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

```powershell
cd "C:\Users\NeXT GeN\Desktop\INTERNSHIP\CrewAI\crewai-news-bot"
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Fill in `.env`:

| Variable | Where to get it |
|---|---|
| `SERPAPI_API_KEY` | [serpapi.com](https://serpapi.com) → Dashboard → API Key |
| `LLM_PROVIDER` + matching key | See "Choosing an LLM" below |
| `SLACK_WEBHOOK_URL` | Slack → [api.slack.com/apps](https://api.slack.com/apps) → your app → Incoming Webhooks → add to your private channel |
| `GOOGLE_SHEETS_CREDENTIALS_JSON`, `GOOGLE_SHEET_ID` | Google Cloud Console → Service Account → create JSON key. Share the target Sheet with the service account's `client_email` as Editor. Copy the Sheet ID from its URL. |
| `CRON_SECRET` | Any random string — only needed for the deployed cron endpoint |

> `.env` and `service-account.json` are both git-ignored. Never commit
> real credentials — treat any key that's ever been pasted or committed
> as compromised and rotate it.

Run it:

```powershell
python main.py
```

## 2. Choosing an LLM

`LLM_PROVIDER` in `.env` picks which model powers the agents and the
Summarizer Tool's structured-output call.

| `LLM_PROVIDER` | Default model | Get a key |
|---|---|---|
| `gemini` (used in this project) | `gemini-3.6-flash` (Google's free-tier Flash model) | [aistudio.google.com](https://aistudio.google.com) → Get API Key |
| `groq` | `openai/gpt-oss-120b` (OpenAI's open-weight model, free on Groq) | [console.groq.com](https://console.groq.com) → API Keys |

Set the matching key (`GEMINI_API_KEY` or `GROQ_API_KEY`) and leave
`MODEL_NAME` blank to use the defaults above. To use a specific model
instead — e.g. `gemini/gemini-3-flash` or `groq/llama-3.3-70b-versatile`
— set `MODEL_NAME` directly and it overrides everything.

Gemini's free tier only covers Flash / Flash-Lite models — Pro models
(`gemini-3.1-pro`, etc.) require billing.

## 3. Tune the scope

Edit `src/config.py`:

```python
TOPICS = [
    "artificial intelligence business",
    "startup funding Pakistan",
    "big tech earnings",
]
NEWS_CATEGORY_SCOPE = "Business & Technology"
ARTICLES_PER_TOPIC = 3
MAX_STORIES_TO_PUBLISH = 4
```

This is the whole "narrow the scope" lever — the Researcher searches
exactly these topics, the Summarizer tags/filters against this scope, and
the Publisher only ships the top `MAX_STORIES_TO_PUBLISH`.

## 4. Deploy to Vercel

This project is deployed by importing the GitHub repo directly in the
Vercel dashboard — no CLI required.

1. Push this repo to GitHub (see below if you haven't yet).
2. In the [Vercel dashboard](https://vercel.com/new), click **Add
   New → Project**, then **Import** this GitHub repository.
3. Under **Environment Variables**, add each of the following (values
   from your local `.env`):

   - `SERPAPI_API_KEY`
   - `LLM_PROVIDER`
   - `GEMINI_API_KEY` (or `GROQ_API_KEY`, matching your provider)
   - `SLACK_WEBHOOK_URL`
   - `GOOGLE_SHEETS_CREDENTIALS_JSON`
   - `GOOGLE_SHEET_ID`
   - `CRON_SECRET`

   For `GOOGLE_SHEETS_CREDENTIALS_JSON`, paste the **entire contents**
   of the service-account JSON key as the value — not a file path.
   Vercel functions don't have access to your local filesystem. The
   tool already handles both a JSON string and a local file path
   automatically, so this works without any code changes.

4. Click **Deploy**.

Your cron endpoint will be live at:

```
https://<your-project>.vercel.app/api/cron
```

## 5. About the "every 4 hours" schedule — read before demoing

Vercel's **Hobby (free) plan cron jobs only fire once per day**, no
matter what cron expression is in `vercel.json` — anything more frequent
is rejected at deploy time. The `0 */4 * * *` expression already set
in `vercel.json` **requires the Pro plan** to run on that schedule.

If you're on Hobby, two working options:

- **Get a Vercel Pro seat** (often free for students/interns via the
  GitHub Student Developer Pack), or
- **Keep the endpoint on Vercel, trigger it externally** every 4 hours
  with a free scheduler that sends an authenticated HTTP request:
  - [cron-job.org](https://cron-job.org) — set the URL to your
    `/api/cron` endpoint, method GET, header
    `Authorization: Bearer <CRON_SECRET>`, schedule `0 */4 * * *`.
  - A GitHub Actions workflow with a `schedule:` trigger doing the same
    `curl` call.

The `crons` block in `vercel.json` is harmless either way on Hobby — it
just won't fire more than once a day; an external scheduler covers the
real 4-hour cadence.

Serverless function duration limits also scale with plan (Hobby caps
`maxDuration` well below the 300s set here). If staying on Hobby, shrink
`TOPICS` / `ARTICLES_PER_TOPIC` so a full run comfortably finishes within
your plan's limit.

## 6. Structured data — where to see it

- `NewsFetchResult`, `SummaryResult`, `PublishResult` in `src/schemas.py`
  are what `output_pydantic` enforces on each Task. Access them locally
  via `result.pydantic` after `crew.kickoff()` (see `main.py`).
- The `/api/cron` endpoint returns the final `PublishResult` as JSON in
  the HTTP response body — check it in your scheduler's execution logs.

## 7. The dashboard

`public/index.html` is a live dashboard — no build step, Vercel serves it
as a static file automatically. It reads real numbers from your Google
Sheet via `/api/dashboard`, a read-only endpoint that pulls the latest
run's rows from the `Runs` and `Stories` tabs the pipeline writes to.

Once deployed, visit `https://<your-project>.vercel.app/` to see it. The
dashboard only shows real data once you've run the pipeline at least
once and it has written to your Sheet.

- The **"Run Pipeline"** button calls `/api/cron` directly from the
  browser and prompts for `CRON_SECRET` before triggering a run. Runs
  take roughly 20–60 seconds; the button shows a loading state while it
  waits.
- The **filter chips** are generated from whatever topics appear in the
  latest run, driven by `TOPICS` in `src/config.py` — no manual wiring
  needed when the topic list changes.
- The **"Why it matters"** toggle on each story expands the
  `why_it_matters` field the Summarizer wrote — real structured data,
  not decoration.
- Article images are intentionally not real photos (avoids scraping and
  copyright issues) — each story gets an original gradient tile
  generated client-side based on its category.

To sanity-check the dashboard layout without running the full pipeline,
point `fetch("/api/dashboard")` in `public/index.html` at a local mock
JSON file with fake data.

## 8. Testing tools in isolation

```python
from src.tools.news_fetcher_tool import NewsFetcherTool

tool = NewsFetcherTool()
print(tool.run(topics=["AI regulation"], articles_per_topic=3))
```

Do the same for `SummarizerTool`, `SlackNotifierTool`, and
`SheetsLoggerTool` before wiring them into the full crew — much faster
than debugging through an LLM agent loop.