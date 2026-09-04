"""Run the data ingestion pipeline.

    local data/ files  ->  GCS raw/  ->  GCS processed/  ->  Qdrant

Idempotent: a Qdrant collection that already has data is left alone.

  python ingest.py                 # ingest whatever is missing
  python ingest.py --force         # rebuild both collections from scratch
  python ingest.py --hr-only       # only the clean HR collection
  python ingest.py --noisy-only    # only the mixed HR + noise collection
  python ingest.py --no-upload     # skip pushing local data/ to GCS

Run this once after filling in .env. main.py / app.py / evaluate.py assume
it has already been run.
"""

import argparse

from hr_assistant.ingestion import run_ingestion
from hr_assistant.logging_config import configure_logging


def main():
    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="rebuild collections even if they already exist")
    parser.add_argument("--hr-only", action="store_true", help="only ingest the clean HR collection")
    parser.add_argument("--noisy-only", action="store_true", help="only ingest the mixed HR + noise collection")
    parser.add_argument("--no-upload", action="store_true", help="skip uploading local data/ to GCS")
    args = parser.parse_args()

    hr = not args.noisy_only
    noisy = not args.hr_only

    run_ingestion(force=args.force, hr=hr, noisy=noisy, upload=not args.no_upload)
    print("\nIngestion complete.")


if __name__ == "__main__":
    main()
