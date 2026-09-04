"""20 · evaluation — answer-quality scoring, uploaded to LangSmith.

Runs the real HR agent against evaluation_dataset.TEST_CASES (19) and scores
each answer on two dimensions with an LLM judge:

  1. CORRECTNESS  — matches the human-verified reference from the policy text?
  2. GROUNDEDNESS — every claim supported by the retrieved chunks?

Both land in LangSmith as a Dataset + Experiment so quality can be compared
across runs. The judge is Groq's `openai/gpt-oss-120b` — a different family
from the app's Gemini, reached via langchain-openai's ChatOpenAI.
"""

import logging
import uuid

from langchain_openai import ChatOpenAI
from langsmith import Client
from openevals.llm import create_llm_as_judge
from openevals.prompts import CORRECTNESS_PROMPT, RAG_GROUNDEDNESS_PROMPT

from hr_assistant import config
from hr_assistant.agent import create_reliability_agent
from hr_assistant.evaluation_dataset import DATASET_NAME, TEST_CASES
from hr_assistant.llm import get_llm
from hr_assistant.pipeline import ask_plain
from hr_assistant.reranker import rerank
from hr_assistant.tools import create_guarded_search_tool
from hr_assistant.tracing import enable_tracing
from hr_assistant.vector_store import get_retriever, load_vector_store

logger = logging.getLogger(__name__)


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
    # same guarded search tool the app runs; the groundedness context is
    # rebuilt the SAME way that tool builds it — category filter, wide
    # retrieve (RERANK_CANDIDATE_K), then Jina re-rank down to TOP_K_RESULTS
    # — so groundedness is judged against the chunks the agent actually
    # reasons over, not a looser separate query.
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
        keeps them independent.

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
        prompt=CORRECTNESS_PROMPT, feedback_key="correctness", judge=judge,
    )
    groundedness_judge = create_llm_as_judge(
        prompt=RAG_GROUNDEDNESS_PROMPT, feedback_key="groundedness", judge=judge,
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
