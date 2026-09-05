"""09 · ingestion — the one place documents get loaded into Qdrant.
Orchestrates steps 04–08.

    local data/ files
        -> GCS  raw/hr-policies/   +  raw/other-data/    (upload)
        -> GCS  processed/...      (pdf/docx/pptx parsed to JSON, once — 05)
        -> chunk (06) -> embed (07) -> Qdrant collections (08)

Idempotent by default: a Qdrant collection that already has points in it is
left alone. Pass force=True to rebuild it from scratch. `ingest.py` (21) is
the runnable entry point; the app never ingests — it connects to what this
built.
"""

import glob
import logging
import os

from google.cloud import storage

from hr_assistant import config
from hr_assistant.document_loader import (
    load_documents_from_gcs,
    load_processed_documents_from_gcs,
)
from hr_assistant.processor import process_raw_to_json
from hr_assistant.splitter import split_into_chunks
from hr_assistant.vector_store import build_vector_store, collection_exists

logger = logging.getLogger(__name__)

_LOCAL_HR_GLOB = os.path.join("data", "*.txt")
_LOCAL_NOISE_GLOB = os.path.join("data", "noise", "*")


def upload_corpus_to_gcs() -> None:
    """Push the local data/ files to the GCS raw zone. Overwrites — cheap
    and keeps GCS in sync with the repo."""
    client = storage.Client(project=config.PROJECT_ID)
    bucket = client.bucket(config.GCS_BUCKET_NAME)

    pairs = [(_LOCAL_HR_GLOB, config.GCS_PREFIX), (_LOCAL_NOISE_GLOB, config.NOISE_GCS_PREFIX)]
    for local_glob, prefix in pairs:
        files = [f for f in glob.glob(local_glob) if os.path.isfile(f)]
        for path in files:
            blob = bucket.blob(f"{prefix}{os.path.basename(path)}")
            blob.upload_from_filename(path)
        logger.info("Uploaded %d file(s) -> gs://%s/%s", len(files), config.GCS_BUCKET_NAME, prefix)


def ingest_hr_policies(force: bool = False) -> None:
    """The clean HR-only collection the app connects to."""
    name = config.QDRANT_COLLECTION_NAME
    if collection_exists(name) and not force:
        logger.info("Collection '%s' already populated — skipping (use --force to rebuild).", name)
        return

    documents = load_documents_from_gcs()
    chunks = split_into_chunks(documents)
    build_vector_store(chunks, hybrid=True, collection_name=name)
    logger.info("Ingested %d HR document(s) -> %d chunk(s) into '%s'.", len(documents), len(chunks), name)


def ingest_noisy_corpus(force: bool = False) -> None:
    """The mixed HR + noise collection — built alongside the clean one so a
    later stage can test retrieval against real cross-domain noise.

    Raw pdf/docx/pptx are parsed into the processed JSON zone first —
    always on force=True, otherwise only when that zone is still empty."""
    name = config.QDRANT_NOISY_COLLECTION_NAME
    if collection_exists(name) and not force:
        logger.info("Collection '%s' already populated — skipping (use --force to rebuild).", name)
        return

    if force:
        logger.info("Parsing raw files into the processed/ zone...")
        process_raw_to_json()

    documents = load_processed_documents_from_gcs()
    if not documents:
        logger.info("Processed zone is empty — parsing raw files...")
        process_raw_to_json()
        documents = load_processed_documents_from_gcs()

    if not documents:
        raise RuntimeError("Still no processed documents after parsing — check the GCS raw zone.")

    chunks = split_into_chunks(documents)
    build_vector_store(chunks, hybrid=True, collection_name=name)
    logger.info(
        "Ingested %d document(s) (HR + noise) -> %d chunk(s) into '%s'.",
        len(documents), len(chunks), name,
    )


def run_ingestion(force: bool = False, 
    hr: bool = True, 
    noisy: bool = True, 
    upload: bool = True) -> None:
    config.check_api_keys()
    if upload:
        upload_corpus_to_gcs()
    if hr:
        ingest_hr_policies(force=force)
    if noisy:
        ingest_noisy_corpus(force=force)
