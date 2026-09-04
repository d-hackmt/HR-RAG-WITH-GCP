"""Build the agent that ties the LLM and the search tool together
(LangChain's create_agent)."""

from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from hr_assistant import config


def _build_agent(llm, tools, system_prompt: str):
    """Shared by both agent variants below. Both need a checkpointer so
    the chat UIs (main.py/app.py, demo_reliability.py) have real
    conversation memory — without it, a follow-up like "I meant in detail"
    has zero context of the prior question and the agent re-retrieves from
    scratch, sometimes against a completely different document. Same
    thread_id across calls = remembers; a new thread_id = clean slate
    (see pipeline.ask()). The per-thread history is also what the input
    guardrail screens alongside the current question (pipeline
    _input_text_for_screening)."""
    return create_agent(model=llm,
                         tools=tools,
                         system_prompt=system_prompt,
                         checkpointer=InMemorySaver())


def create_hr_agent(llm, tools):
    """Plain agent on config.SYSTEM_PROMPT. Used only by the red-team plain
    baseline (pipeline.build_plain_assistant) now — every real path uses
    create_reliability_agent below."""
    return _build_agent(llm, tools, config.SYSTEM_PROMPT)


def create_reliability_agent(llm, tools):
    """The default agent for every real code path — reinforced scope prompt
    with identity lock and NOT_FOUND handling (config.RELIABILITY_SYSTEM_PROMPT)."""
    return _build_agent(llm, tools, config.RELIABILITY_SYSTEM_PROMPT)
