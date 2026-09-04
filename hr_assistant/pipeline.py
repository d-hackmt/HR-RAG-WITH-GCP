"""17 · pipeline — wire the components into ready-to-use agents, and the
ask() flow that drives them.

    ask()       input guardrail (13) -> semantic cache (14) -> agent (16)
                -> output guardrail (13) -> cache store.   The default path
                for app.py / main.py / demo_reliability.py.
    ask_plain() raw agent call, none of the above. evaluate.py + the
                red-team plain baseline only.

Ingestion (09) is separate — the builders connect to the Qdrant collection
it already built, and bootstrap it once only on a completely fresh setup.
"""

import logging

from hr_assistant import config, thread_memory
from hr_assistant.agent import create_hr_agent, create_reliability_agent
from hr_assistant.guardrails import check_input, check_output
from hr_assistant.llm import get_llm
from hr_assistant.semantic_cache import SemanticCache
from hr_assistant.tools import create_guarded_search_tool, create_search_tool
from hr_assistant.vector_store import collection_exists, load_vector_store

logger = logging.getLogger(__name__)

INPUT_BLOCKED_MESSAGE = "I can't process that request — it was flagged by the input safety guardrail."
OUTPUT_BLOCKED_MESSAGE = "I can't share that answer as generated — it was flagged by the output safety guardrail."


# ── Builders ──────────────────────────────────────────────────────────────

def _bootstrap_collection(collection_name: str, ingest_fn) -> None:
    """First-run convenience: if the Qdrant collection isn't there yet,
    upload the corpus and ingest once. After that this is a no-op and
    startup is just a connect."""
    if collection_exists(collection_name):
        return
    logger.info("Collection '%s' not found — running first-time ingestion.", collection_name)
    from hr_assistant.ingestion import upload_corpus_to_gcs

    upload_corpus_to_gcs()
    ingest_fn()


def _build_guarded_assistant(collection_name: str, ingest_fn):
    """The secure stack: guarded search tool + RELIABILITY_SYSTEM_PROMPT +
    short-term memory + a semantic cache. Returns (agent, cache). ask() adds
    the input/output safety guardrails around this."""
    config.check_api_keys()
    _bootstrap_collection(collection_name, ingest_fn)

    vector_store = load_vector_store(collection_name)
    agent = create_reliability_agent(get_llm(), [create_guarded_search_tool(vector_store)])
    return agent, SemanticCache()


def build_hr_assistant():
    """The app's assistant — the guarded stack against the clean
    `hr_policies` collection. Returns (agent, cache); drive it with ask()."""
    from hr_assistant.ingestion import ingest_hr_policies

    return _build_guarded_assistant(config.QDRANT_COLLECTION_NAME, ingest_hr_policies)


def build_reliability_assistant():
    """The same guarded stack against the mixed HR + noise
    `hr_policies_noisy_demo` collection — used by demo_reliability.py and
    redteam_test.py. Returns (agent, cache)."""
    from hr_assistant.ingestion import ingest_noisy_corpus

    return _build_guarded_assistant(config.QDRANT_NOISY_COLLECTION_NAME, ingest_noisy_corpus)


def build_plain_assistant():
    """No guardrails at all: the plain search tool + the plain SYSTEM_PROMPT
    + memory. Kept ONLY as the red-team before/after baseline
    (redteam_test.py). Returns a bare agent; drive it with ask_plain()."""
    from hr_assistant.ingestion import ingest_hr_policies

    config.check_api_keys()
    _bootstrap_collection(config.QDRANT_COLLECTION_NAME, ingest_hr_policies)

    vector_store = load_vector_store(config.QDRANT_COLLECTION_NAME)
    return create_hr_agent(get_llm(), [create_search_tool(vector_store)])


# ── Asking ────────────────────────────────────────────────────────────────

def ask_plain(agent, question: str, thread_id: str = "default-session") -> str:
    """Raw agent call — no safety guardrail, no cache. Used by evaluate.py
    (answer-quality measurement only) and the red-team plain baseline."""
    return thread_memory.invoke_agent(agent, question, thread_id).text


def ask(agent, cache, question: str, thread_id: str = "default-session") -> str:
    """Full secure flow: input safety guardrail (current turn + recent user
    history) -> semantic cache -> agent -> output safety guardrail -> cache
    store. Each layer logs a pass/block line.

    Same thread_id across calls means the agent remembers prior turns via
    the checkpointer — pass a different thread_id to start a fresh
    conversation (one per Streamlit session). A cache hit and an output
    block are both written into that memory so a follow-up still sees the
    turn, and a blocked answer never lingers in context."""
    screen_text = thread_memory.input_text_for_screening(agent, question, thread_id)
    input_ok, input_reason = check_input(screen_text)
    logger.info("INPUT GUARDRAIL: %s (%s)", "pass" if input_ok else "block", input_reason)
    if not input_ok:
        # Deliberately not written to memory — the point is to keep the
        # blocked prompt out of the model's context entirely.
        return INPUT_BLOCKED_MESSAGE

    cached_answer = cache.lookup(question)
    if cached_answer is not None:
        thread_memory.record_turn(agent, thread_id, question, cached_answer)
        return cached_answer

    message = thread_memory.invoke_agent(agent, question, thread_id)
    answer = message.text

    output_ok, output_reason = check_output(answer)
    logger.info("OUTPUT GUARDRAIL: %s (%s)", "pass" if output_ok else "block", output_reason)
    if not output_ok:
        thread_memory.overwrite_answer(agent, thread_id, message, OUTPUT_BLOCKED_MESSAGE)
        return OUTPUT_BLOCKED_MESSAGE

    cache.store(question, answer)
    return answer


# Backwards-compatible alias — this flow was called ask_reliably() when it
# was reliability-only. The name stays so existing callers and traces don't
# break.
ask_reliably = ask
