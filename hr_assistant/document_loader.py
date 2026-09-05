"""04 · document_loader — read documents out of Cloud Storage.

Two readers, nothing else:
  load_documents_from_gcs()            — the raw .txt HR policies (raw zone)
  load_processed_documents_from_gcs()  — the parsed JSON records (processed
                        zone), written by processor.py (05)

Binary formats (.pdf/.docx/.pptx) are parsed in processor.py, not here —
this file only loads text that is already text.
"""

import json

from google.cloud import storage
from langchain_core.documents import Document

# langchain document cotains 2 things 

# 1) pagecontent: the text content of the document
# 2) metadata: a dictionary of metadata about the document, such as the source,

from hr_assistant import config

## extract policy 
def extract_policy_category(text: str) -> str:
    """Every policy file starts with a 'Policy Category: X' line (HR docs)
    or a 'Category: X' line (noise docs) — pull whichever is present out.
    Shared with processor.py (05)."""
    for line in text.splitlines()[:5]:
        stripped = line.strip().lower()
        if stripped.startswith("policy category:"):
            return line.split(":", 1)[1].strip()
        if stripped.startswith("category:"):
            return line.split(":", 1)[1].strip()
    return "Unknown"


# load raw data from gcs 

def load_documents_from_gcs(
    bucket_name: str = config.GCS_BUCKET_NAME,
    prefix: str = config.GCS_PREFIX,
) -> list[Document]:
    """List and download every .txt file under the given GCS prefix,
    returning one LangChain Document per file with source + category
    metadata."""
    client = storage.Client(project=config.PROJECT_ID)
    bucket = client.bucket(bucket_name)

    documents = []
    for blob in bucket.list_blobs(prefix=prefix):
        if not blob.name.endswith(".txt"):
            continue
        text = blob.download_as_text()
        filename = blob.name.rsplit("/", 1)[-1]
        documents.append(Document(
            page_content=text,
            metadata={
                "source": filename,
                "policy_category": extract_policy_category(text),
                "gcs_path": f"gs://{bucket_name}/{blob.name}",
            },
        ))
    return documents


# load processed data from gcs


def load_processed_documents_from_gcs(
    bucket_name: str = config.GCS_BUCKET_NAME,
    prefixes: tuple[str, ...] = (config.PROCESSED_HR_PREFIX, config.PROCESSED_NOISE_PREFIX),
) -> list[Document]:
    """Read the processed zone (JSON records written by processor.py) and
    return LangChain Documents. No parsing here — just reading already-parsed
    text out of JSON. This is what the ingestion pipeline (09) calls."""
    client = storage.Client(project=config.PROJECT_ID)
    bucket = client.bucket(bucket_name)

    documents = []
    for prefix in prefixes:
        for blob in bucket.list_blobs(prefix=prefix):
            if not blob.name.endswith(".json"):
                continue
            record = json.loads(blob.download_as_text())
            documents.append(Document(
                page_content=record["text"],
                metadata={
                    "source": record["source"],
                    "policy_category": record["policy_category"],
                    "gcs_path": record["raw_gcs_path"],
                },
            ))
    return documents



