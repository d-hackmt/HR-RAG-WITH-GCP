"""Command-line demo of the HR Policy Assistant.

Run `python ingest.py` once first, then:  python main.py
"""

from hr_assistant.logging_config import configure_logging
from hr_assistant.pipeline import ask, build_hr_assistant


def main():
    configure_logging()  # show the INPUT/OUTPUT GUARDRAIL + CACHE lines
    print("Connecting to the HR policy assistant...")
    # (agent, cache) — the guarded, cached stack. ask() runs the full
    # input/output safety pipeline around it. Bootstraps ingestion on the
    # first run if the collection is missing.
    agent, cache = build_hr_assistant()
    print("Assistant ready!\n")

    demo_questions = [
        "How many paid annual leave days do I get?",
        "What is the notice period during probation?",
        "Can I work from home every day?",
        "What happens to my leave during my notice period?",
        "How many weeks of maternity leave am I entitled to?",
    ]

    for question in demo_questions:
        print("=" * 60)
        print("QUESTION:", question)
        print("-" * 60)
        answer = ask(agent, cache, question)
        print("ANSWER:", answer)
        print("=" * 60)
        print()


if __name__ == "__main__":
    main()
