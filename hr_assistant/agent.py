"""16 · agent — the LLM + search tool + system prompt + memory, tied
together by LangChain's create_agent.

Two variants, differing only in which prompt they run:
  create_hr_agent           — config-plain SYSTEM_PROMPT (red-team baseline)
  create_reliability_agent  — RELIABILITY_SYSTEM_PROMPT (every real path)
"""

from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from hr_assistant import prompts


def _build_agent(llm, tools, system_prompt: str):
    """Shared by both variants. The checkpointer (InMemorySaver) gives the
    chat UIs real conversation memory — without it a follow-up like "I meant
    in detail" has zero context of the prior question and the agent
    re-retrieves from scratch. Same thread_id across calls = remembers; a
    new thread_id = clean slate (see pipeline.ask()). That per-thread
    history is also what the input guardrail screens alongside the current
    question (thread_memory.input_text_for_screening)."""
    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
        checkpointer=InMemorySaver(),
    )


def create_hr_agent(llm, tools):
    """Plain agent — used only by the red-team plain baseline
    (pipeline.build_plain_assistant)."""
    return _build_agent(llm, tools, prompts.SYSTEM_PROMPT)


def create_reliability_agent(llm, tools):
    """The default agent for every real code path — reinforced scope prompt
    with identity lock and NOT_FOUND handling."""
    return _build_agent(llm, tools, prompts.RELIABILITY_SYSTEM_PROMPT)
