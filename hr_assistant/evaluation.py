"""Evaluate answer quality, with results uploaded to LangSmith.

Runs the real HR agent against a fixed set of question / reference-answer
pairs and scores each answer with an LLM judge, along two dimensions:

  1. CORRECTNESS  — does the answer match the human-verified reference
                    pulled from the actual policy text?
  2. GROUNDEDNESS — is every claim in the answer supported by the chunks
                    that were actually retrieved (not invented, not from
                    the model's own prior knowledge)?

Both scores are uploaded to LangSmith as a Dataset + Experiment, so
quality can be compared across runs (a prompt change, a new model, a new
guardrail, ...).

The judge is Groq's `openai/gpt-oss-120b` — a different model family from
the app's Gemini, so the eval is not the model grading its own answers.
It's reached through langchain-openai's ChatOpenAI (gpt-oss is
OpenAI-API-compatible), so no extra client library is needed.
"""

import logging
import uuid

from langchain_openai import ChatOpenAI
from langsmith import Client
from openevals.llm import create_llm_as_judge
from openevals.prompts import CORRECTNESS_PROMPT, RAG_GROUNDEDNESS_PROMPT

from hr_assistant import config

logger = logging.getLogger(__name__)
from hr_assistant.agent import create_reliability_agent
from hr_assistant.llm import get_llm
from hr_assistant.pipeline import ask_plain
from hr_assistant.reranker import rerank
from hr_assistant.tools import create_guarded_search_tool
from hr_assistant.tracing import enable_tracing
from hr_assistant.vector_store import get_retriever, load_vector_store

DATASET_NAME = "hr-policy-qa"

# Reference answers are taken straight from data/*.txt — keep them in sync
# if the corpus changes.
TEST_CASES = [
    {"question": "How many days of paid annual leave do I get per year?",
     "answer": "18 days of paid annual leave per calendar year, accrued at 1.5 days per completed month of service."},
    {"question": "How many days of unused annual leave can be carried forward?",
     "answer": "Up to 10 days; any balance beyond that is forfeited on December 31st."},
    {"question": "How many paid sick days do I get per year?",
     "answer": "10 days of paid sick leave per calendar year; it does not carry forward."},
    {"question": "How many days per week can I work from home?",
     "answer": "Up to 2 days per week as a standing arrangement, agreed with your manager."},
    {"question": "How long is the probation period?",
     "answer": "3 months (90 calendar days) from the date of joining, unless the offer letter says otherwise."},
    {"question": "What is the notice period during probation?",
     "answer": "15 days' written notice, or payment in lieu of notice."},
    {"question": "What is the standard notice period for a confirmed employee?",
     "answer": "60 days (2 calendar months); 90 days for Director level and above."},
    {"question": "Within how many days must reimbursement claims be submitted?",
     "answer": "Within 30 days of the expense being incurred."},
    {"question": "How many public holidays does the company observe each year?",
     "answer": "12 fixed public holidays per calendar year, plus 2 floating holidays."},
    {"question": "How much is the one-time home office setup allowance?",
     "answer": "Up to 15,000 (local currency), claimable within the first 3 months of WFH eligibility."},
    {"question": "How many weeks of paid maternity leave am I entitled to?",
     "answer": "26 weeks of paid maternity leave, which may begin up to 8 weeks before the expected delivery date."},
    {"question": "Within how many days is the final settlement processed after the last working day?",
     "answer": "Within 45 days of the last working day."},
    {"question": "How many days of casual leave do I get per year?",
     "answer": "Up to 6 days of casual leave per calendar year."},
    {"question": "What flight class can I book for an international flight over 6 hours if I'm below Director level?",
     "answer": "Premium economy. Director level and above may book business class for international flights over 6 hours."},
    {"question": "How long do I have to submit travel expenses after a trip?",
     "answer": "Within 15 days of returning from travel — shorter than the standard 30-day reimbursement window."},
    {"question": "When do I get my relieving letter after my last working day?",
     "answer": "Within 10 working days of the last working day, provided handover and asset return are complete."},
    {"question": "How much can I claim per year for professional certifications or courses?",
     "answer": "Up to 25,000 (local currency) per calendar year, with prior manager approval before enrollment."},
    {"question": "Who do I report a Code of Conduct violation to?",
     "answer": "HR — confidentially, via the HR portal's ethics reporting form or the dedicated ethics mailbox. Retaliation against a good-faith reporter is itself a violation."},
]


def _judge_llm() -> ChatOpenAI:
    """Groq gpt-oss-120b via the OpenAI-compatible endpoint."""
    if not config.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set — needed for the eval judge (see .env).")
    return ChatOpenAI(
        model=config.JUDGE_MODEL_NAME,
        base_url=config.GROQ_BASE_URL,
        api_key=config.GROQ_API_KEY,
        temperature=0,
    )


def _ensure_dataset(client: Client):
    """Create the LangSmith dataset the first time, then reuse it."""
    if client.has_dataset(dataset_name=DATASET_NAME):
        logger.info("Dataset '%s' already exists — reusing it.", DATASET_NAME)
        return client.read_dataset(dataset_name=DATASET_NAME)

    logger.info("Creating dataset '%s' with %d example(s).", DATASET_NAME, len(TEST_CASES))
    dataset = client.create_dataset(dataset_name=DATASET_NAME)
    client.create_examples(
        dataset_id=dataset.id,
        examples=[
            {"inputs": {"question": c["question"]}, "outputs": {"answer": c["answer"]}}
            for c in TEST_CASES
        ],
    )
    return dataset


def run_evaluation():
    """Upload the dataset (if needed) and run correctness + groundedness."""
    enable_tracing()
    client = Client()
    dataset = _ensure_dataset(client)

    # Connect to the collection ingest.py already built. The agent uses the
    # same guarded search tool the deployed app runs; the groundedness
    # context is rebuilt the SAME way that tool builds it — category
    # filter, wide retrieve (RERANK_CANDIDATE_K), then Jina re-rank down to
    # TOP_K_RESULTS — so groundedness is judged against the chunks the
    # agent actually reasons over, not a looser separate query.
    vector_store = load_vector_store(config.QDRANT_COLLECTION_NAME)
    agent = create_reliability_agent(get_llm(), [create_guarded_search_tool(vector_store)])
    retriever = get_retriever(
        vector_store,
        k=config.RERANK_CANDIDATE_K,
        filter_categories=config.HR_POLICY_CATEGORIES,
    )

    def target(inputs: dict) -> dict:
        """Run one question through the real agent, and rebuild the chunks
        its search tool would have handed the model so groundedness is
        checked against that exact evidence. A fresh thread_id per question
        keeps them independent (no memory bleed between test cases).

        ask_plain() — no Model Armor in/out here: this measures answer
        quality, and a flagged answer shouldn't silently drop a data point."""
        question = inputs["question"]
        answer = ask_plain(agent, question, thread_id=f"eval-{uuid.uuid4()}")
        candidates = retriever.invoke(question)
        top_chunks = rerank(question, candidates, top_n=config.TOP_K_RESULTS)
        context = "\n\n".join(chunk.page_content for chunk in top_chunks)
        return {"answer": answer, "context": context}

    judge = _judge_llm()  # one client, shared by both evaluators
    correctness_evaluator = create_llm_as_judge(
        prompt=CORRECTNESS_PROMPT,
        feedback_key="correctness",
        judge=judge,
    )

    groundedness_judge = create_llm_as_judge(
        prompt=RAG_GROUNDEDNESS_PROMPT,
        feedback_key="groundedness",
        judge=judge,
    )

    def groundedness_evaluator(outputs: dict, **kwargs) -> dict:
        """Answer supported by the retrieved context, not invented."""
        return groundedness_judge(outputs={"answer": outputs["answer"]}, context=outputs["context"])

    logger.info("Running evaluation against dataset '%s' — judge: %s", DATASET_NAME, config.JUDGE_MODEL_NAME)
    return client.evaluate(
        target,
        data=dataset.name,
        evaluators=[correctness_evaluator, groundedness_evaluator],
        experiment_prefix="hr-policy-eval",
        description="HR policy assistant — correctness + groundedness (Groq gpt-oss-120b judge)",
    )
