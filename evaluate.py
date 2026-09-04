"""Run the LangSmith evaluation (correctness + groundedness) for the HR agent.

Needs LANGSMITH_API_KEY and GROQ_API_KEY in .env. Results land in your
LangSmith project as an Experiment on the 'hr-policy-qa' dataset.

Run with:  python evaluate.py
"""

from hr_assistant.evaluation import DATASET_NAME, run_evaluation
from hr_assistant.logging_config import configure_logging


def main():
    configure_logging()
    print("Running HR Policy Assistant evaluation (uploads to LangSmith)...")
    results = run_evaluation()
    print(f"\nDone. Open the '{DATASET_NAME}' dataset in LangSmith to see the experiment.")
    try:
        print(results)
    except Exception:
        pass


if __name__ == "__main__":
    main()
