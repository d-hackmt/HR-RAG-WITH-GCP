"""11 · tools — wrap retrieve (08) + re-rank (10) as one tool the agent calls.

Retriever-as-tool: wide retrieval -> re-rank -> narrow, cited result.

create_guarded_search_tool(): the default — plus the scope guardrail
(category allow-list + post-rerank relevance floor, see config's
HR_POLICY_CATEGORIES / RELEVANCE_THRESHOLD). Every real path uses this.

create_search_tool(): the plain tool — no category filter, no relevance
gate. Kept only for the red-team plain baseline (build_plain_assistant).
"""

from langchain.tools import tool

from hr_assistant import config
from hr_assistant.reranker import rerank, rerank_with_scores
from hr_assistant.vector_store import get_retriever

NOT_FOUND_SENTINEL = "NOT_FOUND: no relevant HR policy content matched this question."


def create_search_tool(vector_store):
    """Return a @tool function that searches + re-ranks the HR policy corpus."""

    @tool
    def search_hr_policy(question: str) -> str:
        """Search the HR policy documents for information about leave,
        work from home,
        probation, notice period,
        reimbursement, code of conduct,
        holidays, maternity/
        paternity leave, travel expenses, or the exit process."""
        retriever = get_retriever(vector_store,
                        k=config.RERANK_CANDIDATE_K)
        candidates = retriever.invoke(question)
        top_chunks = rerank(question, candidates,
                    top_n=config.TOP_K_RESULTS)

        return "\n\n".join(
            f"[Source: {c.metadata['source']}]\n{c.page_content}" for c in top_chunks
        )

    return search_hr_policy


def create_guarded_search_tool(vector_store):
    """Guarded version of the search tool. Two-layer scope guardrail:

    1. Retrieval is hard-filtered to config.HR_POLICY_CATEGORIES — non-HR
       chunks (Finance/Sales/Operations/Business) can never be returned by
       this tool at all, regardless of embedding similarity.
    2. The reranked top result must clear config.RELEVANCE_THRESHOLD, or
       the tool reports NOT_FOUND instead of a weak, technically-in-scope
       match — this is what RELIABILITY_SYSTEM_PROMPT tells the agent to
       treat as "politely refuse," not "guess anyway."
    """

    @tool
    def search_hr_policy(question: str) -> str:
        """Search the HR policy documents for information about leave, work from home,
        probation, notice period, reimbursement, code of conduct, holidays, maternity/
        paternity leave, travel expenses, or the exit process. Do not use this for
        Finance, Sales, Operations, or Business questions — it will not find anything."""
        retriever = get_retriever(
            vector_store, k=config.RERANK_CANDIDATE_K, filter_categories=config.HR_POLICY_CATEGORIES
        )
        candidates = retriever.invoke(question)
        if not candidates:
            return NOT_FOUND_SENTINEL

        ranked = rerank_with_scores(question, candidates, top_n=config.TOP_K_RESULTS)
        if not ranked or ranked[0][1] < config.RELEVANCE_THRESHOLD:
            return NOT_FOUND_SENTINEL

        return "\n\n".join(
            f"[Source: {c.metadata['source']}] (relevance: {score:.2f})\n{c.page_content}"
            for c, score in ranked
        )

    return search_hr_policy
