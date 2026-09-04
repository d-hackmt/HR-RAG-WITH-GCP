"""Re-rank retrieved candidates with Jina's cross-encoder reranker.

Plain REST call — no extra SDK needed beyond `requests`.
See https://jina.ai/reranker/
"""

import requests

from hr_assistant import config

JINA_RERANK_URL = "https://api.jina.ai/v1/rerank"


def rerank_with_scores(query: str, candidates: list, top_n: int = config.TOP_K_RESULTS) -> list[tuple]:
    """Re-rank candidates with Jina, returning (Document, relevance_score)
    pairs — the guarded search tool (hr_assistant/tools.py) uses the scores
    to gate on relevance, not just reorder. candidates is typically a wider
    shortlist (see RERANK_CANDIDATE_K)."""
    if not candidates:
        return []

    response = requests.post(
        JINA_RERANK_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.JINA_API_KEY}",
        },
        json={
            "model": config.RERANKER_MODEL_NAME,
            "query": query,
            "top_n": top_n,
            "documents": [c.page_content for c in candidates],
            "return_documents": False,
        },
        timeout=30,
    )
    response.raise_for_status()

    # results are ranked, each with an "index" back into the original list
    ranked = response.json()["results"]
    return [(candidates[r["index"]], r["relevance_score"]) for r in ranked]


def rerank(query: str, candidates: list, top_n: int = config.TOP_K_RESULTS) -> list:
    """Just the re-ordered Documents, no scores. Thin wrapper around
    rerank_with_scores()."""
    return [doc for doc, _score in rerank_with_scores(query, candidates, top_n)]
