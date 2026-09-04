"""01 · config — every setting, read from .env. Everything imports this.

config.py holds values only (keys, URLs, model ids, sizes). The
system-prompt text lives next door in prompts.py (02).
"""

import os
from dotenv import load_dotenv

load_dotenv()

## GCP

PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION")  # Vertex AI region — used by hr_assistant/llm.py

## ENV VAR / SECRETS

JINA_API_KEY = os.getenv("JINA_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

## CLOUD STORAGE

GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")

# Raw zone — original files, untouched. Ingestion uploads the local data/
# tree here: HR policies under GCS_PREFIX, the non-HR noise docs under
# NOISE_GCS_PREFIX.
GCS_PREFIX = "raw/hr-policies/"
NOISE_GCS_PREFIX = "raw/other-data/"

# Processed zone — one JSON record per raw file (parsed text + metadata),
# written by processor.py (05). Ingestion reads ONLY from here, so
# PDFs/DOCX/PPTX are parsed once, not on every rebuild.
PROCESSED_HR_PREFIX = "processed/hr-policies/"
PROCESSED_NOISE_PREFIX = "processed/other-data/"

## QDRANT

QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "hr_policies")

# A second collection holding HR docs + non-HR noise together. `ingest.py`
# builds it alongside the clean one; the app connects to the clean
# collection. The noisy collection is where a later stage tests retrieval
# against real cross-domain noise.
QDRANT_NOISY_COLLECTION_NAME = os.getenv("QDRANT_NOISY_COLLECTION_NAME", "hr_policies_noisy_demo")

## MODELS
# All three are env-overridable so a model swap needs no code change.

# gemini-2.5-flash retires ~2026-10-20 (verified Sept 2026) — set
# LLM_MODEL_NAME to a Gemini 3.x Flash model before then. Current IDs:
# https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gemini-2.5-flash")

# jina-embeddings-v2-base-en: 768-dim, English. Changing it changes the
# vector dimension, so it also needs `python ingest.py --force`.
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "jina-embeddings-v2-base-en")

RERANKER_MODEL_NAME = os.getenv("RERANKER_MODEL_NAME", "jina-reranker-v2-base-multilingual")

## CHUNK / TEXT SPLITTING

CHUNK_SIZE = 500
CHUNK_OVERLAP = 60

## RETRIEVAL RESULTS

# Broad questions ("list all maternity leave provisions") need enough
# chunks in context to answer in full; at CHUNK_SIZE=500 a single
# multi-section policy doc is often 4-5 chunks, so a small top_k can't
# return the whole thing no matter how the prompt is worded.
TOP_K_RESULTS = 5
RERANK_CANDIDATE_K = 12  # wider shortlist retrieved before re-ranking

## LANGSMITH — request tracing (env-var based; langchain auto-traces)

LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "false")
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "hr-policy-assistant")


def check_api_keys() -> None:
    """Stop early with a clear message if a required key/config is missing."""
    missing = [
        name for name, value in [
            ("PROJECT_ID", PROJECT_ID),
            ("JINA_API_KEY", JINA_API_KEY),
            ("QDRANT_URL", QDRANT_URL),
            ("QDRANT_API_KEY", QDRANT_API_KEY),
            ("GCS_BUCKET_NAME", GCS_BUCKET_NAME),
        ]
        if not value
    ]
    if missing:
        raise ValueError(f"Missing required .env values: {', '.join(missing)}")
