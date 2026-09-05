"""27 · studio_graph — entry point: LangGraph Studio (`langgraph dev`).

Exposes the agent's compiled graph so Studio can visualize and step
through it (nodes, edges, state at each step, tool calls) in the browser.
Connects to the clean HR Qdrant collection at import time — run
`python ingest.py` first.
"""

from hr_assistant.logging_config import configure_logging
from hr_assistant.pipeline import build_hr_assistant

configure_logging()

agent, _cache = build_hr_assistant(checkpointer=False)

# langgraph.json points at this module-level name
graph = agent
