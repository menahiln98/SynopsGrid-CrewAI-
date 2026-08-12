"""
Agent definitions. Three agents, each with exactly the custom tool(s) it
needs — no built-in crewai_tools anywhere in this file.
"""

from crewai import Agent, LLM

from src.config import Settings
from src.tools.news_fetcher_tool import NewsFetcherTool
from src.tools.summarizer_tool import SummarizerTool
from src.tools.slack_tool import SlackNotifierTool
from src.tools.sheets_tool import SheetsLoggerTool


def build_llm(settings: Settings) -> LLM:
    return LLM(model=settings.llm_model_string, api_key=settings.llm_api_key, temperature=0.3)


def build_agents(settings: Settings) -> dict:
    llm = build_llm(settings)

    researcher = Agent(
        role="Senior News Researcher",
        goal=(
            "Find the freshest, most relevant {category_scope} news stories for the "
            "given topics using the News Fetcher Tool, and hand off a clean, "
            "structured list of raw articles."
        ),
        backstory=(
            "You are a wire-service researcher with an eye for signal over noise. "
            "You always use the News Fetcher Tool to pull real, current results — "
            "you never fabricate an article or its link."
        ),
        tools=[NewsFetcherTool(result_as_answer=True)],
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    summarizer = Agent(
        role="Intelligent News Summarizer",
        goal=(
            "Turn raw articles into de-duplicated, structured stories with sharp "
            "summaries, a 'why it matters' angle, a category, and a relevance score, "
            "strictly using the Intelligent Summarizer Tool."
        ),
        backstory=(
            "You are a business-desk editor known for concise, accurate summaries "
            "and for never repeating the same story twice under different headlines. "
            "You always call the Intelligent Summarizer Tool to do the actual "
            "summarizing — you never write your own summary and pass it off as the "
            "tool's output."
        ),
        tools=[SummarizerTool(result_as_answer=True)],
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    publisher = Agent(
        role="Distribution & Publishing Agent",
        goal=(
            "Publish the top-ranked stories to the team's Slack channel and log every "
            "story to the shared Google Sheet, using the Slack Notifier Tool and the "
            "Google Sheets Logger Tool."
        ),
        backstory=(
            "You are the automation that keeps the team's internal news feed alive — "
            "reliable, on schedule, and it never posts a broken link."
        ),
        tools=[SlackNotifierTool(), SheetsLoggerTool()],
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    return {"researcher": researcher, "summarizer": summarizer, "publisher": publisher}
