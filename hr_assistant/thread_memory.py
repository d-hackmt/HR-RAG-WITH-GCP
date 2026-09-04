"""15 · thread_memory — everything that touches the agent's checkpointer.

The agent (16) carries an InMemorySaver keyed by thread_id. This module is
the small set of operations pipeline.ask() (17) performs on that memory
around a normal turn:

  invoke_agent            — run one turn, return the final message object
  record_turn             — write a (Q, A) pair WITHOUT running the agent
                            (used on a semantic-cache hit)
  overwrite_answer        — replace an answer already in memory, by id
                            (used when the output guardrail blocks it)
  input_text_for_screening — the current question + recent USER turns, for
                            the input guardrail

Kept out of pipeline.py so that file reads as just the flow.
"""

import logging

from langchain_core.messages import AIMessage, HumanMessage

from hr_assistant import config

logger = logging.getLogger(__name__)


def thread_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def invoke_agent(agent, question: str, thread_id: str):
    """Run one turn and return the final message object.

    Callers read `.text` off it (not `.content`) — Gemini 2.5+ returns
    content as a list of blocks carrying a "thought signature" alongside the
    text; `.text` extracts the plain string regardless of shape. The message
    object (not just its text) is returned so a caller can overwrite it in
    memory by id."""
    response = agent.invoke(
        {"messages": [{"role": "user", "content": question}]},
        config=thread_config(thread_id),
    )
    return response["messages"][-1]


def record_turn(agent, thread_id: str, question: str, answer: str) -> None:
    """Append a (user question, assistant answer) pair to the thread's
    memory without running the agent — used on a semantic-cache hit, so a
    later follow-up ("tell me more about that") still has this turn in
    context. Best-effort; a memory-write failure must not fail the request."""
    try:
        agent.update_state(
            thread_config(thread_id),
            {"messages": [HumanMessage(content=question), AIMessage(content=answer)]},
        )
    except Exception:
        logger.debug("Could not write cache-hit turn to thread memory", exc_info=True)


def overwrite_answer(agent, thread_id: str, ai_message, replacement: str) -> None:
    """Swap the answer the agent just produced for `replacement` in the
    thread's memory. add_messages replaces a message whose id matches, so a
    blocked (unsafe) answer doesn't linger in context for the next turn and
    memory matches what the user was shown."""
    if not getattr(ai_message, "id", None):
        return
    try:
        agent.update_state(
            thread_config(thread_id),
            {"messages": [AIMessage(id=ai_message.id, content=replacement)]},
        )
    except Exception:
        logger.debug("Could not overwrite blocked answer in thread memory", exc_info=True)


def input_text_for_screening(agent, question: str, thread_id: str) -> str:
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
        state = agent.get_state(thread_config(thread_id))
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
