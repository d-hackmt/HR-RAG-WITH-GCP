"""Reliability path — the parsing stage between the raw zone and indexing.

raw/<prefix>/filename.ext  --parse-->  processed/<prefix>/filename.json

Called by hr_assistant/ingestion.py so PDFs/DOCX/PPTX are parsed once, not
on every vector-store build:
  1. Raw zone (GCS raw/hr-policies/, raw/other-data/) — original files,
     untouched, whatever format they arrived in.
  2. Processed zone (GCS processed/hr-policies/, processed/other-data/) —
     one JSON record per raw file: parsed plain text + metadata, written
     by process_raw_to_json() below.
  3. Ingestion reads ONLY the processed zone, via document_loader.py's
     load_processed_documents_from_gcs() — the "JSON loader".
"""

import json
import logging

from google.cloud import storage

from hr_assistant import config
from hr_assistant.document_loader import iter_parsed_raw_files

logger = logging.getLogger(__name__)

_RAW_TO_PROCESSED = {
    config.GCS_PREFIX: config.PROCESSED_HR_PREFIX,
    config.NOISE_GCS_PREFIX: config.PROCESSED_NOISE_PREFIX,
}


def process_raw_to_json(bucket_name: str = config.GCS_BUCKET_NAME) -> int:
    """Parse every raw file (any format) and write it out as a processed
    JSON record in GCS. Returns how many records were written.

    The record holds exactly what load_processed_documents_from_gcs() reads
    back: source, policy_category, text, raw_gcs_path.
    """
    client = storage.Client(project=config.PROJECT_ID)
    bucket = client.bucket(bucket_name)

    count = 0
    for raw_prefix, processed_prefix in _RAW_TO_PROCESSED.items():
        for blob, filename, text, category in iter_parsed_raw_files(bucket, raw_prefix):
            record = {
                "source": filename,
                "policy_category": category,
                "text": text,
                "raw_gcs_path": f"gs://{bucket_name}/{blob.name}",
            }

            processed_name = filename.rsplit(".", 1)[0] + ".json"
            processed_blob = bucket.blob(f"{processed_prefix}{processed_name}")
            processed_blob.upload_from_string(
                json.dumps(record, indent=2), content_type="application/json"
            )
            logger.info("  %s  ->  %s", blob.name, processed_blob.name)
            count += 1

    return count
