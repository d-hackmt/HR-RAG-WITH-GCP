"""13 · agent — the LLM + search tool + system prompt + short-term memory,
tied together by LangChain's create_agent.
"""

from langchain.agents import create_agent

from hr_assistant import prompts


def create_hr_agent(llm, tools, checkpointer=None):
    """The agent. The checkpointer (e.g. InMemorySaver) is what gives the
    chat UIs real conversation memory — without it, a follow-up like "I
    meant in detail" has zero context of the prior question and the agent
    re-retrieves from scratch. Same thread_id across calls = remembers; a
    new thread_id = clean slate (see pipeline.ask()).

    Pass checkpointer=None (the default) when LangGraph's platform/dev API
    will supply persistence itself — a graph compiled with a custom
    checkpointer baked in is rejected by `langgraph dev` (see
    studio_graph.py, 19)."""
    kwargs = {}
    if checkpointer is not None:
        kwargs["checkpointer"] = checkpointer

    return create_agent(
        model=llm,  # brain ai agent
        tools=tools, # search tool
        system_prompt=prompts.SYSTEM_PROMPT,
        **kwargs,
    )
