"""LangGraph Studio entry point.

Exposes the reliability agent's compiled graph so `langgraph dev` can
visualize and step through it (nodes, edges, state at each step, tool
calls) in the browser-based Studio UI.

Connects to the mixed HR + noise Qdrant collection at import time (run
`python ingest.py` first) and builds the guarded agent.
"""

from hr_assistant.logging_config import configure_logging
from hr_assistant.pipeline import build_reliability_assistant

configure_logging()

# Studio drives the raw agent graph — the semantic cache and the
# input/output safety guardrails live in pipeline.ask(), not the agent, so
# they are not exercised here. That's intentional: Studio is for inspecting
# the agent's own nodes/edges/state.
agent, _cache = build_reliability_assistant()

# langgraph.json points at this module-level name
graph = agent
