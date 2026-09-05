"""14 · semantic_cache — a simple in-memory semantic cache.

Embeds each question with the same Jina model used for retrieval, keeps a
*bounded* in-memory list of (embedding, question, answer, timestamp), and
on a new question compares by cosine similarity. 

Above
config.SEMANTIC_CACHE_THRESHOLD -> return the cached answer instantly,
skipping retrieval + rerank + the LLM.

Bounded on purpose (config.SEMANTIC_CACHE_MAX_ENTRIES /
SEMANTIC_CACHE_TTL_SECONDS): a long-lived process shouldn't grow without
limit, and a cached answer shouldn't outlive a policy change + re-ingest.
The oldest entry is evicted once the cache is full; entries older than the
TTL are ignored on lookup (and drop off naturally as new ones arrive).

Wired into hr_assistant/pipeline.py as a wrapper around the agent, not
baked into it — so it's easy to toggle and inspect. In-memory means it's
per-process: every Cloud Run instance keeps its own, and a restart clears
it.
"""

import logging
import time
from collections import deque

import numpy as np
from langsmith import traceable

from hr_assistant import config
from hr_assistant.embeddings import get_embeddings_model

logger = logging.getLogger(__name__)


class SemanticCache:
    def __init__(
        self,
        threshold: float = config.SEMANTIC_CACHE_THRESHOLD,
        max_entries: int = config.SEMANTIC_CACHE_MAX_ENTRIES,
        ttl_seconds: int = config.SEMANTIC_CACHE_TTL_SECONDS,
    ):
        self.threshold = threshold
        self.ttl_seconds = ttl_seconds
        self._embeddings_model = get_embeddings_model()
        # deque(maxlen=...) drops the oldest entry automatically on append.
        self._entries: "deque[dict]" = deque(maxlen=max_entries)
        # The (question, raw embedding) most recently computed by lookup(),
        # so a following store() of the same question doesn't re-embed it.
        self._last_embedded: "tuple[str, np.ndarray] | None" = None

    def _embed(self, question: str) -> np.ndarray:
        if self._last_embedded is not None and self._last_embedded[0] == question:
            return self._last_embedded[1]
        vec = np.asarray(self._embeddings_model.embed_query(question), dtype=float)
        self._last_embedded = (question, vec)
        return vec

    def _fresh_entries(self) -> list[dict]:
        """Entries not past their TTL (ttl_seconds <= 0 disables expiry)."""
        if self.ttl_seconds <= 0:
            return list(self._entries)
        cutoff = time.monotonic() - self.ttl_seconds
        return [e for e in self._entries if e["stored_at"] >= cutoff]

    @traceable(name="semantic_cache_lookup")
    def lookup(self, question: str) -> str | None:
        """Return the cached answer for a near-duplicate question, or None."""
        entries = self._fresh_entries()
        if not entries:
            logger.info("CACHE MISS (cache empty)")
            return None

        raw = self._embed(question)
        query = raw / (np.linalg.norm(raw) or 1.0)

        # One matrix-vector product instead of a Python loop over entries.
        matrix = np.vstack([e["embedding"] for e in entries])
        row_norms = np.linalg.norm(matrix, axis=1)
        row_norms[row_norms == 0] = 1.0
        scores = (matrix / row_norms[:, None]) @ query

        best_idx = int(np.argmax(scores))
        best_score = float(scores[best_idx])

        if best_score >= self.threshold:
            best = entries[best_idx]
            logger.info(
                "CACHE HIT (similarity=%.3f vs %r) — skipping retrieval + LLM",
                best_score,
                best["question"],
            )
            return best["answer"]

        logger.info("CACHE MISS (best similarity=%.3f)", best_score)
        return None

    def store(self, question: str, answer: str) -> None:
        # Reuses lookup()'s embedding when the question matches — see _embed().
        self._entries.append(
            {
                "embedding": self._embed(question),
                "question": question,
                "answer": answer,
                "stored_at": time.monotonic(),
            }
        )
