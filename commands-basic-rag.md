# Commands — `basic-rag` branch, direct copy-paste

Scoped to this branch only: no Model Armor, no OAuth, no Cloud Run, no
LiteLLM gateway, no eval/red-team. Just what runs the plain RAG pipeline.
Real values below, confirmed via `gcloud` just now — not placeholders.
Shell: Git Bash (matches `hrrenv/Scripts/activate`).

## Already true, confirmed today — nothing to do here

- Project **`rag-hr-assistant-demo`** (number `564821241199`) exists.
- Billing is linked and enabled (`billingAccounts/01F83E-4931F0-126013`).
- `aiplatform.googleapis.com` and `storage.googleapis.com` are already enabled.
- `hrrenv` (the `uv` venv) already has `basic-rag`'s dependencies installed
  (`langchain-google-genai`, `langchain-qdrant`, `streamlit`, `qdrant-client`,
  `langgraph-cli`, `python-docx`/`pptx`, `pypdf`, `langsmith`, ...).

`GCS_BUCKET_NAME` below (`rag-hr-assistant-demo-hr-policies`) matches your
`.env` exactly. Nothing here touches `.env`'s contents otherwise —
`python-dotenv` reads it automatically; none of these commands need the
Jina/Qdrant/LangSmith keys typed anywhere.

## 1. Confirm you're pointed at the right project

```bash
gcloud config set project rag-hr-assistant-demo
gcloud auth application-default login
gcloud auth application-default set-quota-project rag-hr-assistant-demo
```

## 2. Create the bucket — **when you're ready, not run yet**

No bucket exists under the project yet. `ingest.py` needs this one to
exist before it can upload `data/` to GCS. Run it yourself whenever you
want to ingest:

```bash
gcloud storage buckets create gs://rag-hr-assistant-demo-hr-policies \
  --project=rag-hr-assistant-demo \
  --location=us-central1
```

## 3. Install dependencies (uv, into the existing `hrrenv`)

```bash
source hrrenv/Scripts/activate
uv pip install -r requirements.txt
```

## 4. `.env`

Already present in the repo root — nothing to create. `config.py` reads it
automatically via `python-dotenv`. It needs (already filled, per
`.env.example`): `PROJECT_ID=rag-hr-assistant-demo`, `LOCATION=us-central1`,
`GCS_BUCKET_NAME=rag-hr-assistant-demo-hr-policies`, `JINA_API_KEY`,
`QDRANT_URL`, `QDRANT_API_KEY`.

## 5. Ingest the corpus (both collections — `hr_policies` + `hr_policies_noisy_demo`)

```bash
python ingest.py
```

Rebuild from scratch, or limit scope:

```bash
python ingest.py --force
python ingest.py --hr-only       # skip the noisy/mixed collection
python ingest.py --noisy-only    # skip the clean collection
```

## 6. Run it

```bash
python main.py               # CLI demo — a few questions through the agent
streamlit run app.py         # chat UI, http://localhost:8501
langgraph dev                # LangGraph Studio on the agent graph
python -m hr_assistant.tracing   # confirm LangSmith tracing (if enabled)
```

## Cost note

Same as `commands.md`: Vertex AI Gemini Flash + Jina are pay-per-call at
near-zero volume for local dev; Qdrant Cloud + Jina free tiers cover this
easily. Nothing here runs standing infrastructure — there's no Cloud Run
service on this branch to leave running.
