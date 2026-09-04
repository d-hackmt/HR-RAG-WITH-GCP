# HR Policy Assistant

A working RAG agent that answers HR-policy questions from real policy
documents — retrieval, metadata filtering, hybrid search, and re-ranking
for grounded answers. Hardened with guardrails, memory, and a semantic
cache; deployed to Google Cloud Run behind Google OAuth with a governed
LLM gateway.

## Quick start

```bash
cp .env.example .env          # then fill in the values (see below)
pip install -r requirements.txt
gcloud auth application-default login

python ingest.py              # local data/ -> GCS -> Qdrant (run once)
python main.py                # CLI demo
streamlit run app.py          # chat UI
```

`.env` needs: `PROJECT_ID`, `LOCATION`, `GCS_BUCKET_NAME`, `JINA_API_KEY`,
`QDRANT_URL`, `QDRANT_API_KEY`. For `evaluate.py` also add
`LANGSMITH_API_KEY` and `GROQ_API_KEY`. Local dev without a Model Armor
template: set `GUARDRAIL_PROVIDER=gemini_lite` (or `none`). Full
provisioning: **[commands.md](commands.md)**.

## The scripts

| Command | What it does |
|---|---|
| `python ingest.py` | Ingest the corpus: local `data/` → GCS raw → GCS processed → Qdrant. Idempotent — skips a collection that already exists (`--force` to rebuild). |
| `python main.py` | CLI demo — the full secure pipeline (guardrails + scope filter + cache). Bootstraps ingestion on first run if needed. |
| `streamlit run app.py` | The chat UI. Same secure pipeline and bootstrap behavior. |
| `python demo_reliability.py` | The reliability walkthrough — same pipeline against the noisy corpus: guardrails, scope filter, memory, cache. |
| `python evaluate.py` | Answer-quality eval (correctness + groundedness), uploaded to LangSmith. Separate from everything else. |
| `python redteam_test.py` | 7-attack adversarial pass; output to `results/`. |
| `python -m hr_assistant.tracing` | Check that LangSmith tracing is wired up. |

Local Docker: `docker compose up` (app), `docker compose run --rm eval`.

## Documentation

Read `docs/` in order:

**The project** — [01 Overview](docs/01-overview.md) · [02 Tech Stack](docs/02-tech-stack.md)

**The RAG pipeline** — [03 Document Processing](docs/03-document-processing.md) · [04 Chunking & Embeddings](docs/04-chunking-and-embeddings.md) · [05 Retrieval & Vector Storage](docs/05-retrieval-and-vector-storage.md) · [06 Filtering & Hybrid Search](docs/06-filtering-and-hybrid-search.md) · [07 Re-ranking](docs/07-re-ranking.md) · [08 The Agent](docs/08-the-agent.md)

**Reliability** — [09 Noisy Corpus, Memory & Cache](docs/09-reliability.md) · [10 Evaluation & Red-Teaming](docs/10-evaluation-and-redteam.md)

**Deployment & governance** — [11 GCP, APIs & IAM](docs/11-gcp-apis-and-iam.md) · [12 Containerization & Cloud Run](docs/12-containerization-and-cloud-run.md) · [13 Access Control](docs/13-access-control.md) · [14 LLM Gateway](docs/14-llm-gateway.md) · [15 Content Guardrails](docs/15-content-guardrails.md) · [16 Hosting Architecture](docs/16-hosting-architecture.md)

**Reference** — [commands.md](commands.md) (every command, creation to teardown) · [summary.md](summary.md) (project snapshot + known limitations, for handoff)
