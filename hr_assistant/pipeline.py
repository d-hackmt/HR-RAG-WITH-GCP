"""14 · pipeline — wire the components into one agent, and the ask() flow
that drives it.

    question -> agent (search tool 11 + short-term memory) -> answer

Ingestion (09) is separate — build_hr_assistant() connects to the Qdrant
collection it already built, and bootstraps it once only on a completely
fresh setup.
"""

import logging

from langgraph.checkpoint.memory import InMemorySaver

from hr_assistant import config
from hr_assistant.agent import create_hr_agent
from hr_assistant.llm import get_llm
from hr_assistant.tools import create_search_tool
from hr_assistant.vector_store import collection_exists, load_vector_store

logger = logging.getLogger(__name__)


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


def build_hr_assistant(checkpointer=None):
    """Connect to the clean `hr_policies` collection and build the agent
    (search tool + system prompt + memory). Returns a bare agent; drive it
    with ask().

    checkpointer defaults to an InMemorySaver (real chat memory for the CLI
    and Streamlit UI). Pass checkpointer=False from studio_graph.py to build
    the graph with none — `langgraph dev` supplies persistence itself and
    rejects a graph with one baked in."""
    from hr_assistant.ingestion import ingest_hr_policies

    config.check_api_keys()
    _bootstrap_collection(config.QDRANT_COLLECTION_NAME, ingest_hr_policies)

    if checkpointer is None:
        checkpointer = InMemorySaver()
    elif checkpointer is False:
        checkpointer = None

    vector_store = load_vector_store(config.QDRANT_COLLECTION_NAME)
    return create_hr_agent(get_llm(), [create_search_tool(vector_store)], checkpointer=checkpointer)


def ask(agent, question: str, thread_id: str = "default-session") -> str:
    """Run one turn through the agent and return the answer text.

    Same thread_id across calls means the agent remembers prior turns via
    the checkpointer — pass a different thread_id to start a fresh
    conversation (e.g. one per Streamlit session).

    `.text` (not `.content`) is read off the final message: Gemini 2.5+
    returns content as a list of blocks carrying a "thought signature"
    alongside the text; `.text` extracts just the plain string regardless."""
    response = agent.invoke(
        {"messages": [{"role": "user",
                "content": question}]},
        config={"configurable": {"thread_id": thread_id}},
    )
    return response["messages"][-1].text
