"""10 · reranker — re-rank retrieved candidates with Jina's cross-encoder.

Retrieval (08) is fast but rough; the reranker reads the question and each
candidate chunk *together* and re-scores the shortlist. Plain REST call — no
extra SDK beyond `requests`. See https://jina.ai/reranker/
"""

import requests

from hr_assistant import config

JINA_RERANK_URL = "https://api.jina.ai/v1/rerank"


def rerank(query: str, candidates: list, top_n: int = config.TOP_K_RESULTS) -> list:
    """Re-rank `candidates` (a wide shortlist — see RERANK_CANDIDATE_K) and
    return the top `top_n` Documents, best first."""
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

    # each result carries an "index" back into the original candidates list
    ranked = response.json()["results"]
    return [candidates[r["index"]] for r in ranked]
