"""13 · agent — the LLM + search tool + system prompt + short-term memory,
tied together by LangChain's create_agent.
"""

from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from hr_assistant import prompts


def create_hr_agent(llm, tools):
    """The agent. The checkpointer (InMemorySaver) is what gives the chat
    UIs real conversation memory — without it, a follow-up like "I meant in
    detail" has zero context of the prior question and the agent
    re-retrieves from scratch. Same thread_id across calls = remembers; a
    new thread_id = clean slate (see pipeline.ask())."""
    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=prompts.SYSTEM_PROMPT,
        checkpointer=InMemorySaver(),
    )
