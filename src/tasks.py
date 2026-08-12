"""
Task definitions — sequential pipeline: fetch -> summarize -> publish.
Each task is pinned to a Pydantic `output_pydantic` schema so the crew
produces validated, structured data at every stage instead of loose text.
"""

from crewai import Task

from src.schemas import NewsFetchResult, SummaryResult, PublishResult


def build_tasks(agents: dict, topics: list, category_scope: str, articles_per_topic: int, max_stories: int):
    researcher = agents["researcher"]
    summarizer = agents["summarizer"]
    publisher = agents["publisher"]

    fetch_task = Task(
        description=(
            f"Call the News Fetcher Tool with topics={topics} and "
            f"articles_per_topic={articles_per_topic} to pull the latest news. "
            f"Editorial scope to keep in mind: '{category_scope}'. "
            "You MUST actually invoke the tool — do not write out what you think "
            "the tool's output would look like. Never fabricate article titles, "
            "links, or dates. Return the real tool output as-is, unmodified."
        ),
        expected_output=(
            "The exact, unmodified JSON returned by the News Fetcher Tool call, "
            "matching the NewsFetchResult schema."
        ),
        agent=researcher,
        output_pydantic=NewsFetchResult,
    )

    summarize_task = Task(
        description=(
            "Take the raw articles JSON from the previous task and pass it to the "
            "Intelligent Summarizer Tool along with "
            f"category_scope='{category_scope}'. You MUST actually invoke the tool "
            "with the real JSON from the previous task — do not write out what you "
            "think the tool's output would look like, and do not summarize the "
            "articles yourself without calling the tool. Return the real tool "
            "output as-is, unmodified."
        ),
        expected_output=(
            "The exact, unmodified JSON returned by the Intelligent Summarizer "
            "Tool call, matching the SummaryResult schema."
        ),
        agent=summarizer,
        context=[fetch_task],
        output_pydantic=SummaryResult,
    )

    publish_task = Task(
        description=(
            "Take the summarized stories JSON from the previous task. First call the "
            "Slack Notifier Tool with "
            f"max_stories={max_stories} to post the top stories to Slack. Then call "
            "the Google Sheets Logger Tool with the same summary JSON to log every "
            "story. You MUST actually invoke both tools with the real JSON from the "
            "previous task — do not skip a call or assume it succeeded. Report back "
            "whether each step succeeded, how many stories were posted to Slack, "
            "and how many rows were appended to the sheet, as a PublishResult JSON "
            "object (include the current UTC timestamp as run_timestamp_utc)."
        ),
        expected_output="A JSON object matching the PublishResult schema.",
        agent=publisher,
        context=[summarize_task],
        output_pydantic=PublishResult,
    )

    return [fetch_task, summarize_task, publish_task]