"""11 · tools — wrap retrieve (08) + re-rank (10) as one tool the agent calls.

Retriever-as-tool: wide retrieval -> re-rank -> narrow, cited result. The
agent decides when to call it (see agent.py, 13).
"""

from langchain.tools import tool

from hr_assistant import config
from hr_assistant.reranker import rerank
from hr_assistant.vector_store import get_retriever


def create_search_tool(vector_store):
    """Return a @tool function that searches + re-ranks the HR policy corpus."""

    @tool
    def search_hr_policy(question: str) -> str:
        """Search the HR policy documents for information about leave, work from home,
        probation, notice period, reimbursement, code of conduct, holidays, maternity/
        paternity leave, travel expenses, or the exit process."""
        retriever = get_retriever(vector_store, k=config.RERANK_CANDIDATE_K)
        candidates = retriever.invoke(question)
        top_chunks = rerank(question, candidates, top_n=config.TOP_K_RESULTS)

        return "\n\n".join(
            f"[Source: {c.metadata['source']}]\n{c.page_content}" for c in top_chunks
        )

    return search_hr_policy
