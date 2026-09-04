"""Wire the components into ready-to-use agents.

The deployed app (app.py) and the CLI (main.py) both call
build_hr_assistant() + ask() — the full secure flow:

    input safety guardrail (current turn + recent history)
      -> semantic cache
      -> agent (guarded search tool + short-term memory)
      -> output safety guardrail
      -> cache store

build_plain_assistant() + ask_plain() is the same kind of agent WITHOUT any
of that — no safety guardrail, no scope filter, no cache. It's kept only as
the red-team before/after baseline (redteam_test.py); nothing user-facing
should use it.

Ingestion is a *separate* pipeline (hr_assistant/ingestion.py, run via
`python ingest.py`). These builders don't re-embed on every run — they
connect to the Qdrant collection ingestion already built. As a
convenience, if the collection is missing entirely (a fresh setup), they
bootstrap it once; after that, startup is just a connect.
"""

import logging

from langchain_core.messages import AIMessage, HumanMessage

from hr_assistant import config
from hr_assistant.agent import create_hr_agent, create_reliability_agent
from hr_assistant.guardrails import check_input, check_output
from hr_assistant.llm import get_llm
from hr_assistant.semantic_cache import SemanticCache
from hr_assistant.tools import create_guarded_search_tool, create_search_tool
from hr_assistant.vector_store import collection_exists, load_vector_store

logger = logging.getLogger(__name__)

INPUT_BLOCKED_MESSAGE = "I can't process that request — it was flagged by the input safety guardrail."
OUTPUT_BLOCKED_MESSAGE = "I can't share that answer as generated — it was flagged by the output safety guardrail."


# --------------------------------------------------------------------------
# Builders
# --------------------------------------------------------------------------

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
    """The secure stack: guarded search tool (category filter + post-rerank
    relevance floor) + RELIABILITY_SYSTEM_PROMPT (identity lock + NOT_FOUND
    handling) + short-term memory + a semantic cache. Returns (agent,
    cache). ask() adds the input/output safety guardrails around this."""
    config.check_api_keys()
    _bootstrap_collection(collection_name, ingest_fn)

    vector_store = load_vector_store(collection_name)
    search_tool = create_guarded_search_tool(vector_store)
    agent = create_reliability_agent(get_llm(), [search_tool])
    return agent, SemanticCache()


def build_hr_assistant():
    """The deployed assistant — the guarded stack against the clean
    `hr_policies` collection. Returns (agent, cache); drive it with ask()."""
    from hr_assistant.ingestion import ingest_hr_policies

    return _build_guarded_assistant(config.QDRANT_COLLECTION_NAME, ingest_hr_policies)


def build_reliability_assistant():
    """The same guarded stack against the mixed HR + noise
    `hr_policies_noisy_demo` collection — used by demo_reliability.py and
    redteam_test.py to exercise the scope guardrail against real
    cross-domain noise. Returns (agent, cache)."""
    from hr_assistant.ingestion import ingest_noisy_corpus

    return _build_guarded_assistant(config.QDRANT_NOISY_COLLECTION_NAME, ingest_noisy_corpus)


def build_plain_assistant():
    """No guardrails at all: the plain search tool (no category filter, no
    relevance floor) + the plain SYSTEM_PROMPT + memory. Kept ONLY as the
    red-team before/after baseline (redteam_test.py) — nothing user-facing
    should use this. Returns a bare agent; drive it with ask_plain()."""
    from hr_assistant.ingestion import ingest_hr_policies

    config.check_api_keys()
    _bootstrap_collection(config.QDRANT_COLLECTION_NAME, ingest_hr_policies)

    vector_store = load_vector_store(config.QDRANT_COLLECTION_NAME)
    return create_hr_agent(get_llm(), [create_search_tool(vector_store)])


# --------------------------------------------------------------------------
# Asking
# --------------------------------------------------------------------------

def _thread_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _invoke_agent(agent, question: str, thread_id: str):
    """Run one turn through the agent and return the final message object.

    Callers read `.text` off it (not `.content`) — Gemini 2.5+ returns
    content as a list of blocks carrying a "thought signature" alongside
    the text; `.text` extracts just the plain string regardless of shape.
    The message object (not just its text) is returned so ask() can
    overwrite it in memory by id if the output guardrail blocks it."""
    response = agent.invoke(
        {"messages": [{"role": "user", "content": question}]},
        config=_thread_config(thread_id),
    )
    return response["messages"][-1]


def ask_plain(agent, question: str, thread_id: str = "default-session") -> str:
    """Raw agent call — no safety guardrail, no cache. Used by evaluate.py
    (answer-quality measurement only) and the red-team plain baseline."""
    return _invoke_agent(agent, question, thread_id).text


def _record_turn(agent, thread_id: str, question: str, answer: str) -> None:
    """Append a (user question, assistant answer) pair to the thread's
    memory without running the agent — used on a semantic-cache hit, so a
    later follow-up ("tell me more about that") still has this turn in
    context. Best-effort; a memory-write failure must not fail the request."""
    try:
        agent.update_state(
            _thread_config(thread_id),
            {"messages": [HumanMessage(content=question), AIMessage(content=answer)]},
        )
    except Exception:
        logger.debug("Could not write cache-hit turn to thread memory", exc_info=True)


def _overwrite_answer_in_memory(agent, thread_id: str, ai_message, replacement: str) -> None:
    """Swap the answer the agent just produced for `replacement` in the
    thread's memory. add_messages replaces a message whose id matches, so
    a blocked (unsafe) answer doesn't linger in context for the next turn
    and memory matches what the user was shown."""
    if not getattr(ai_message, "id", None):
        return
    try:
        agent.update_state(
            _thread_config(thread_id),
            {"messages": [AIMessage(id=ai_message.id, content=replacement)]},
        )
    except Exception:
        logger.debug("Could not overwrite blocked answer in thread memory", exc_info=True)


def _input_text_for_screening(agent, question: str, thread_id: str) -> str:
    """The current question, prefixed with the last
    config.GUARDRAIL_HISTORY_TURNS *user* turns for this thread, so a
    multi-turn attack that looks benign one message at a time is still
    screened in aggregate.

    Only prior human messages are included — never tool output (the
    retrieved policy text) or the assistant's own answers, which would
    inflate every follow-up's screening payload and risk false positives.
    Falls back to just the question if history can't be read."""
    turns = config.GUARDRAIL_HISTORY_TURNS
    if turns <= 0:
        return question

    try:
        state = agent.get_state(_thread_config(thread_id))
        messages = (getattr(state, "values", None) or {}).get("messages", [])
    except Exception:
        logger.debug("Could not read conversation history for screening", exc_info=True)
        return question

    prior = []
    for m in [msg for msg in messages if getattr(msg, "type", "") == "human"][-turns:]:
        content = getattr(m, "content", "")
        if isinstance(content, list):
            content = " ".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        content = str(content).strip()
        if content:
            prior.append(content)

    if not prior:
        return question
    # Plain concatenation of the user's own messages — no added framing that
    # a prompt-injection classifier might itself react to.
    return "\n".join([*prior, question])


def ask(agent, cache, question: str, thread_id: str = "default-session") -> str:
    """Full secure flow: input safety guardrail (current turn + recent user
    history) -> semantic cache -> agent (guarded search tool + memory) ->
    output safety guardrail -> cache store. Each layer logs a pass/block
    line.

    Same thread_id across calls means the agent remembers prior turns via
    the checkpointer — pass a different thread_id to start a fresh
    conversation (e.g. one per Streamlit session). A cache hit and an
    output block are both written into that memory so a follow-up still
    sees the turn, and a blocked answer never lingers in context."""
    screen_text = _input_text_for_screening(agent, question, thread_id)
    input_ok, input_reason = check_input(screen_text)
    logger.info("INPUT GUARDRAIL: %s (%s)", "pass" if input_ok else "block", input_reason)
    if not input_ok:
        # Deliberately not written to memory — the point is to keep the
        # blocked prompt out of the model's context entirely.
        return INPUT_BLOCKED_MESSAGE

    cached_answer = cache.lookup(question)
    if cached_answer is not None:
        _record_turn(agent, thread_id, question, cached_answer)
        return cached_answer

    message = _invoke_agent(agent, question, thread_id)
    answer = message.text

    output_ok, output_reason = check_output(answer)
    logger.info("OUTPUT GUARDRAIL: %s (%s)", "pass" if output_ok else "block", output_reason)
    if not output_ok:
        _overwrite_answer_in_memory(agent, thread_id, message, OUTPUT_BLOCKED_MESSAGE)
        return OUTPUT_BLOCKED_MESSAGE

    cache.store(question, answer)
    return answer


# Backwards-compatible alias — this flow was called ask_reliably() when it
# was reliability-only. It's the default path now; the name stays so
# existing callers and traces don't break.
ask_reliably = ask
