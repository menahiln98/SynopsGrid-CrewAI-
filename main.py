"""
Local entrypoint. Run with:

    python main.py

Deployed on Vercel, api/cron.py calls src.crew.run_crew() instead — this
file is only for running/testing the crew on your own machine.
"""

import json

from src.crew import run_crew


def main():
    print("Starting News Automation Crew run...\n")
    output = run_crew()

    print("\n=== FINAL STRUCTURED RESULT ===")
    print(json.dumps(output["pydantic"], indent=2))


if __name__ == "__main__":
    main()
