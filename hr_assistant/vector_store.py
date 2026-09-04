"""08 · vector_store — store chunk embeddings in Qdrant Cloud and search them.

Covers hybrid (dense + sparse/BM25) retrieval.

Two entry points:
  - build_vector_store(chunks, ...)  — embed + upsert. Only ingestion (09) calls this.
  - load_vector_store(name)          — connect to an EXISTING collection, no
                                       embedding. pipeline (14) uses this.
"""

import uuid
from functools import lru_cache

from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient

from hr_assistant import config
from hr_assistant.embeddings import get_embeddings_model

_ID_NAMESPACE = uuid.UUID("5b9c1a1e-8b1a-4f7d-9d5e-2b6a7c9d1e3f")  # fixed, arbitrary
_SPARSE_MODEL = "Qdrant/bm25"


@lru_cache(maxsize=1)
def _qdrant_client() -> QdrantClient:
    """One client for the process — collection_exists() is called a few
    times per startup and QdrantClient holds a connection pool."""
    return QdrantClient(url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY)


def collection_exists(collection_name: str) -> bool:
    """True only if the collection exists AND has at least one point in it."""
    client = _qdrant_client()
    if not client.collection_exists(collection_name):
        return False
    return client.count(collection_name).count > 0


def load_vector_store(
    collection_name: str = config.QDRANT_COLLECTION_NAME,
    hybrid: bool = True,
) -> QdrantVectorStore:
    """Connect to an existing Qdrant collection — no embedding, no upsert.

    Raises if the collection isn't there yet; the fix is always to run the
    ingestion pipeline once (`python ingest.py`)."""
    if not collection_exists(collection_name):
        raise RuntimeError(
            f"Qdrant collection '{collection_name}' is missing or empty. "
            f"Run `python ingest.py` once to ingest the corpus."
        )

    kwargs = dict(
        collection_name=collection_name,
        embedding=get_embeddings_model(),
        url=config.QDRANT_URL,
        api_key=config.QDRANT_API_KEY,
    )
    if hybrid:
        kwargs["sparse_embedding"] = FastEmbedSparse(model_name=_SPARSE_MODEL)
        kwargs["retrieval_mode"] = RetrievalMode.HYBRID
    else:
        kwargs["retrieval_mode"] = RetrievalMode.DENSE

    return QdrantVectorStore.from_existing_collection(**kwargs)


def _stable_chunk_id(chunk) -> str:
    """Deterministic point ID from (source, chunk text) — the same chunk
    always maps to the same Qdrant point ID. Without this,
    QdrantVectorStore.from_documents generates a fresh random ID every call,
    so re-running `ingest.py` would INSERT duplicate copies instead of
    overwriting. With stable IDs, re-ingestion is a true upsert."""
    key = f"{chunk.metadata.get('source', '')}::{chunk.page_content}"
    return str(uuid.uuid5(_ID_NAMESPACE, key))


def build_vector_store(chunks, hybrid: bool = True, collection_name: str = config.QDRANT_COLLECTION_NAME) -> QdrantVectorStore:
    """Embed every chunk and upsert into a Qdrant Cloud collection.

    hybrid=True (the default, matching load_vector_store) also computes
    sparse (keyword/BM25) vectors — a DENSE-only collection built here can't
    later be opened in hybrid mode. collection_name defaults to the clean HR
    collection; ingestion also builds the mixed
    config.QDRANT_NOISY_COLLECTION_NAME.
    """
    kwargs = dict(
        documents=chunks,
        embedding=get_embeddings_model(),
        ids=[_stable_chunk_id(c) for c in chunks],
        url=config.QDRANT_URL,
        api_key=config.QDRANT_API_KEY,
        collection_name=collection_name,
    )
    if hybrid:
        kwargs["sparse_embedding"] = FastEmbedSparse(model_name=_SPARSE_MODEL)
        kwargs["retrieval_mode"] = RetrievalMode.HYBRID
    else:
        kwargs["retrieval_mode"] = RetrievalMode.DENSE

    return QdrantVectorStore.from_documents(**kwargs)


def get_retriever(vector_store: QdrantVectorStore, k: int = config.TOP_K_RESULTS):
    """Turn a vector store into a retriever that returns the top `k` chunks."""
    return vector_store.as_retriever(search_kwargs={"k": k})
