# Commands — Project Creation to Teardown

Every command used to build this project, in order, with the real values.
**Reference only — not re-run to produce this file.** A one-line comment
sits above each command.

This is the single command reference for the whole project — local setup,
cloud provisioning, deployment, and teardown.

## Values used throughout

```bash
PROJECT_ID=rag-hr-assistant-demo
PROJECT_NUMBER=564821241199
REGION=us-central1
LOCATION=us-central1
GCS_BUCKET_NAME=rag-hr-assistant-demo-hr-policies
BILLING_ACCOUNT_ID=<your-billing-account-id>
MODEL_ARMOR_LOCATION=us
MODEL_ARMOR_TEMPLATE_ID=hr-assistant-guardrail
QDRANT_COLLECTION_NAME=hr_policies
QDRANT_NOISY_COLLECTION_NAME=hr_policies_noisy_demo
COMPUTE_SA=564821241199-compute@developer.gserviceaccount.com
CLOUD_RUN_SERVICE_APP=hr-rag-assistant
SECRET_NAME=streamlit-auth
```

`QDRANT_URL`, `QDRANT_API_KEY`, `JINA_API_KEY`, `LANGSMITH_API_KEY`, and
`GROQ_API_KEY` are real secrets — not reproduced here. Get your own from
Qdrant Cloud, Jina AI, smith.langchain.com, and console.groq.com.
LangSmith + Groq are only needed to run `evaluate.py`.

---

## Phase 0 — Prerequisites

```bash
# Log in and see the active account
gcloud auth login

# Find your billing account ID
gcloud billing accounts list
```

You also need free accounts for **Jina AI** (jina.ai) and **Qdrant Cloud**
(cloud.qdrant.io) — neither is a GCP service.

## Phase 1 — Create the project and link billing

```bash
# Create the project
gcloud projects create $PROJECT_ID --name="RAG HR Assistant Demo"

# Attach billing — nothing chargeable works without this
gcloud billing projects link $PROJECT_ID --billing-account=$BILLING_ACCOUNT_ID

# Make this the default project for every command below
gcloud config set project $PROJECT_ID
```

## Phase 2 — Point local credentials at the project

```bash
# Let local Python authenticate as you
gcloud auth application-default login

# Attribute API usage/billing to THIS project
gcloud auth application-default set-quota-project $PROJECT_ID
```

## Phase 3 — Enable the core APIs

```bash
# Vertex AI — the Gemini model
gcloud services enable aiplatform.googleapis.com --project=$PROJECT_ID

# Cloud Storage — holds the raw HR policy documents
gcloud services enable storage.googleapis.com --project=$PROJECT_ID

# Model Armor — the input/output safety guardrail
gcloud services enable modelarmor.googleapis.com --project=$PROJECT_ID
```

## Phase 4 — Cloud Storage: create the bucket

```bash
gcloud storage buckets create gs://$GCS_BUCKET_NAME --location=$REGION
```

Uploading the documents is handled by `python ingest.py` (Phase 8) — it
pushes `data/` to `raw/`, parses pdf/docx/pptx into `processed/`, then
chunks + embeds into Qdrant.

## Phase 5 — Model Armor: create the guardrail template

```bash
# One-time: the template that screens every input/output
gcloud model-armor templates create $MODEL_ARMOR_TEMPLATE_ID \
  --location=$MODEL_ARMOR_LOCATION \
  --project=$PROJECT_ID \
  --pi-and-jailbreak-filter-settings-enforcement=enabled \
  --pi-and-jailbreak-filter-settings-confidence-level=high \
  --basic-config-filter-enforcement=enabled \
  --rai-settings-filters=confidenceLevel=high,filterType=HATE_SPEECH \
  --rai-settings-filters=confidenceLevel=high,filterType=HARASSMENT \
  --rai-settings-filters=confidenceLevel=high,filterType=DANGEROUS \
  --rai-settings-filters=confidenceLevel=high,filterType=SEXUALLY_EXPLICIT \
  --malicious-uri-filter-settings-enforcement=enabled

# Confirm
gcloud model-armor templates describe $MODEL_ARMOR_TEMPLATE_ID --location=$MODEL_ARMOR_LOCATION --project=$PROJECT_ID
```

## Phase 6 — Local Python environment

```bash
# Isolated virtual environment
uv venv genenv
source genenv/Scripts/activate        # Git Bash / macOS / Linux
uv pip install -r requirements.txt
```

## Phase 7 — Configure `.env`

```bash
copy .env.example .env
```
Then fill in `PROJECT_ID`, `LOCATION`, `REGION`, `GCS_BUCKET_NAME`, your
Jina key, your Qdrant URL + key. To run `evaluate.py` you also need
`LANGSMITH_API_KEY` (+ `LANGSMITH_TRACING=true` for tracing) and
`GROQ_API_KEY`.

`app.py` / `main.py` now run the full safety pipeline, so the input/output
guardrail fires on every request. If you haven't provisioned the Model
Armor template (Phase 5), set `GUARDRAIL_PROVIDER=gemini_lite` (one Gemini
call, no extra GCP setup) or `GUARDRAIL_PROVIDER=none` in `.env` for local
work. The guardrail's own knobs (`GUARDRAIL_FAIL_OPEN_INPUT` /
`GUARDRAIL_FAIL_OPEN_OUTPUT`, `GUARDRAIL_HISTORY_TURNS`,
`SEMANTIC_CACHE_MAX_ENTRIES` / `SEMANTIC_CACHE_TTL_SECONDS`) all have
sensible defaults — leave them unset unless you're tuning.

## Phase 8 — Ingest the corpus into Qdrant

```bash
# local data/ -> GCS raw/ -> GCS processed/ -> Qdrant (both collections).
# Idempotent — safe to re-run; skips a collection that already has data.
python ingest.py

# Rebuild from scratch, or limit scope:
#   python ingest.py --force
#   python ingest.py --hr-only        # skip the noisy collection
```

## Phase 9 — Run it locally

```bash
# Secure assistant (guardrails + scope filter + cache), command line
# (bootstraps ingestion if you skipped Phase 8)
python main.py

# Same secure assistant, chat UI
streamlit run app.py

# Reliability walkthrough — same pipeline against the noisy corpus
python demo_reliability.py

# Answer-quality eval — correctness + groundedness, uploaded to LangSmith
# (needs LANGSMITH_API_KEY + GROQ_API_KEY in .env)
python evaluate.py

# Check LangSmith tracing is wired up
python -m hr_assistant.tracing

# Adversarial red-team pass
python redteam_test.py
```

Or with Docker (local only — needs `gcloud auth application-default login`
first; on Windows set `GCLOUD_CONFIG=%APPDATA%\gcloud`):

```bash
docker compose run --rm ingest  # ingest the corpus (or let `up` bootstrap it)
docker compose up               # the app at http://localhost:8501
docker compose run --rm eval    # one evaluation run
```

---

## Phase 10 — Deploy `hr-rag-assistant` to Cloud Run

```bash
# APIs needed to build and host a container
gcloud services enable run.googleapis.com aiplatform.googleapis.com \
  storage.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  --project=$PROJECT_ID

# Let the app's identity call Gemini
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$COMPUTE_SA" --role="roles/aiplatform.user"

# Let it READ (not write) the documents in Cloud Storage
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$COMPUTE_SA" --role="roles/storage.objectViewer"

# Let it call Model Armor
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$COMPUTE_SA" --role="roles/modelarmor.user"

# Build from the Dockerfile and deploy as a public web service
# (public at the network level only — the real gate comes in Phase 11).
# GROQ_API_KEY is the fallback model's credential — llm.py's LiteLLM router
# uses Groq only if the Vertex Gemini call errors (see doc 14).
gcloud run deploy $CLOUD_RUN_SERVICE_APP \
  --source . \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars PROJECT_ID=$PROJECT_ID,LOCATION=$LOCATION,REGION=$REGION,GCS_BUCKET_NAME=$GCS_BUCKET_NAME,QDRANT_URL=<your-qdrant-url>,QDRANT_API_KEY=<your-qdrant-key>,QDRANT_COLLECTION_NAME=$QDRANT_COLLECTION_NAME,JINA_API_KEY=<your-jina-key>,GROQ_API_KEY=<your-groq-key>,GUARDRAIL_PROVIDER=model_armor,MODEL_ARMOR_LOCATION=$MODEL_ARMOR_LOCATION,MODEL_ARMOR_TEMPLATE_ID=$MODEL_ARMOR_TEMPLATE_ID
```

**Bug hit here:** the first deploy crashed — `fastembed`'s BM25 model
download was rate-limited on Cloud Run's shared IP. Fixed by adding one
line to the `Dockerfile` that pre-downloads the model at *build* time.
See doc 12. No new command — just a Dockerfile change and re-run the deploy.

---

## Phase 11 — Google OAuth gate

```bash
# Secret Manager holds the OAuth login secrets
gcloud services enable secretmanager.googleapis.com --project=$PROJECT_ID
```

**Manual step (no CLI):** in the Cloud Console, configure the OAuth consent
screen (User Type: External, Publishing status: Testing — add each approved
employee email under **Test users**), then create an **OAuth Client ID**
(Web application) with redirect URI
`https://<your-cloud-run-url>/oauth2callback`. Copy the Client ID and
Client Secret.

```bash
# Random signing key for the login cookie — never hand-type a secret
COOKIE_SECRET=$(openssl rand -hex 32)

# Write the OAuth config locally (temporary)
cat > secrets.toml <<EOF
[auth]
redirect_uri = "https://<your-cloud-run-url>/oauth2callback"
cookie_secret = "$COOKIE_SECRET"

[auth.google]
client_id = "<your-oauth-client-id>"
client_secret = "<your-oauth-client-secret>"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
EOF

# Upload to Secret Manager — the only place these secrets live
gcloud secrets create $SECRET_NAME --data-file=secrets.toml

# Delete the local copy immediately
rm secrets.toml

# Let the app read (only) this one secret
gcloud secrets add-iam-policy-binding $SECRET_NAME \
  --member="serviceAccount:$COMPUTE_SA" --role="roles/secretmanager.secretAccessor"

# Redeploy: mount the secret, set the employee allow-list
gcloud run deploy $CLOUD_RUN_SERVICE_APP \
  --source . \
  --region $REGION \
  --set-secrets=/app/.streamlit/secrets.toml=$SECRET_NAME:latest \
  --update-env-vars ALLOWED_EMPLOYEE_EMAILS="employee1@example.com,employee2@example.com"
```

To change the allow-list later — repeat the manual "Test user" step AND:

```bash
# The ^;^ prefix makes gcloud split on ; instead of , (emails contain , and @)
gcloud run deploy $CLOUD_RUN_SERVICE_APP \
  --source . --region $REGION \
  --update-env-vars '^;^ALLOWED_EMPLOYEE_EMAILS=a@example.com,b@example.com,c@example.com'
```

---

## Phase 12 — LLM routing & fallback

Nothing to deploy. Model routing (Vertex Gemini primary, Groq fallback) runs
**in-process** via the LiteLLM SDK in `hr_assistant/llm.py` — the fallback
just needs `GROQ_API_KEY`, already set in the Phase 10 deploy. To change the
fallback model, set `FALLBACK_MODEL_NAME` (default `openai/gpt-oss-20b`):

```bash
gcloud run deploy $CLOUD_RUN_SERVICE_APP \
  --source . --region $REGION \
  --update-env-vars FALLBACK_MODEL_NAME=<groq-model-id>
```

**Why no gateway service:** an earlier version ran LiteLLM as a *separate*
private Cloud Run service. It hit a real wall — a shared `LITELLM_MASTER_KEY`
sent as a Bearer token was intercepted by Cloud Run's own IAM layer (which
expects a Google ID token in that header) and rejected with a platform-level
401 before LiteLLM ever saw it. The fix was a per-request minted Google ID
token. With a single app, the whole service — plus its IAM binding and token
minting — buys nothing the in-process SDK doesn't already give (see doc 14),
so it was removed.

---

## Phase 13 — Post-deploy verification

```bash
# Re-run the answer-quality eval (uploads a fresh LangSmith experiment)
python evaluate.py

# Re-run the red-team pass against the same .env the services use.
# The "guarded" pipeline here is now exactly what app.py / main.py run —
# expect the input guardrail to BLOCK instruction_override and
# dan_jailbreak before retrieval, and 7/7 to hold on both pipelines.
python redteam_test.py

# Smoke-test the deployed guardrails in the running app: a normal question
# (cited answer), a repeat (cache hit in the logs), "ignore all previous
# instructions" (input blocked), a finance question (polite refusal).

# Tail the app's logs — look for INPUT GUARDRAIL / OUTPUT GUARDRAIL /
# CACHE HIT lines
gcloud run services logs read $CLOUD_RUN_SERVICE_APP --region $REGION --limit=50
```

---

## Phase 14 — Full teardown

**In order. None of this is reversible.**

```bash
# 1. Delete the app service
gcloud run services delete $CLOUD_RUN_SERVICE_APP --region $REGION

# 2. Delete the OAuth secret
gcloud secrets delete $SECRET_NAME

# 3. Delete the Qdrant collections (external to GCP)
python -c "
from qdrant_client import QdrantClient
from hr_assistant import config
client = QdrantClient(url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY)
client.delete_collection(config.QDRANT_COLLECTION_NAME)
client.delete_collection(config.QDRANT_NOISY_COLLECTION_NAME)
"

# 4. Delete the Model Armor template
gcloud model-armor templates delete $MODEL_ARMOR_TEMPLATE_ID --location=$MODEL_ARMOR_LOCATION --project=$PROJECT_ID

# 5. Delete the bucket and every document in it
gcloud storage rm --recursive gs://$GCS_BUCKET_NAME

# 6. (Optional) disable the APIs
gcloud services disable run.googleapis.com aiplatform.googleapis.com \
  modelarmor.googleapis.com storage.googleapis.com secretmanager.googleapis.com \
  cloudbuild.googleapis.com artifactregistry.googleapis.com \
  --project=$PROJECT_ID

# 7. Delete the whole project — the real teardown, stops all billing
gcloud projects delete $PROJECT_ID

# 8. Local cleanup
rm -rf genenv
rm .env
```

Projects are held ~30 days before permanent deletion
(`gcloud projects undelete $PROJECT_ID` restores one in that window).

## Cost note

Nothing here has a meaningful *standing* cost. The Cloud Run service
scales to zero when idle. Everything else (Qdrant free tier, Jina free
credits, Cloud Storage at this scale, Model Armor and Gemini Flash
pay-per-call, Groq free credits, Secret Manager) is free or near-free.

## Model migration (gemini-2.5-flash retires ~2026-10-20)

The model IDs are env-overridable — no code change needed:

```bash
# point the app at the new model — llm.py's LiteLLM router picks it up,
# still prefixed "vertex_ai/". No other change.
gcloud run deploy $CLOUD_RUN_SERVICE_APP --source . --region $REGION \
  --update-env-vars LLM_MODEL_NAME=<new-gemini-3.x-flash-id>
```

Current model IDs:
https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions
Changing `EMBEDDING_MODEL_NAME` additionally needs `python ingest.py --force`
(the vector dimension changes, invalidating both Qdrant collections).
