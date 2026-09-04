# HR Policy Assistant — Security

> **This is the `security` branch — stage 2 of 3.**
> The `basic-rag` pipeline plus the reliability & safety layer: safety
> guardrails, a scope filter, an identity-lock prompt, a semantic cache,
> LangSmith evaluation, a red-team suite, and a Gemini→Groq fallback.
> Deployment (Docker, Cloud Run, Google OAuth) comes in `deployment`.
>
> | Branch | Adds |
> |---|---|
> | `basic-rag` | the RAG pipeline end to end |
> | **`security`** *(here)* | guardrails, scope filter, semantic cache, evaluation, red-team, LLM fallback |
> | `deployment` | Docker, Cloud Run, Google OAuth |

A RAG agent that answers HR-policy questions from real policy documents —
retrieval, metadata filtering, hybrid search, and re-ranking for grounded
answers. Hardened with guardrails, memory, and a semantic cache. Every model
call is routed through an in-process LiteLLM fallback (Gemini → Groq).

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
`QDRANT_URL`, `QDRANT_API_KEY`. `GROQ_API_KEY` enables the app's fallback
model (Gemini → Groq) and is required by `evaluate.py`; `LANGSMITH_API_KEY`
is also required by `evaluate.py`. Local dev without a Model Armor template:
set `GUARDRAIL_PROVIDER=gemini_lite` (or `none`).

## The code, in reading order

Every file is numbered in its docstring. `hr_assistant/`: 01 config · 02
prompts · 03 logging · 04 document_loader · 05 processor · 06 splitter · 07
embeddings · 08 vector_store · 09 ingestion · 10 reranker · 11 tools · 12
llm · 13 guardrails · 14 semantic_cache · 15 thread_memory · 16 agent · 17
pipeline · 18 tracing · 19 evaluation_dataset · 20 evaluation. Entry
scripts: 21 `ingest.py` · 22 `main.py` · 23 `app.py` · 24
`demo_reliability.py` · 25 `redteam_test.py` · 26 `evaluate.py` · 27
`studio_graph.py`.

## The scripts

| Command | What it does |
|---|---|
| `python ingest.py` | Ingest: local `data/` → GCS raw → GCS processed → Qdrant (both collections). `--force` to rebuild. |
| `python main.py` | CLI demo — the full secure pipeline (guardrails + scope filter + cache). |
| `streamlit run app.py` | The chat UI. Same secure pipeline. No login on this branch. |
| `python demo_reliability.py` | Reliability walkthrough against the noisy corpus. |
| `python evaluate.py` | Answer-quality eval (correctness + groundedness), uploaded to LangSmith. |
| `python redteam_test.py` | 7-attack adversarial pass; output to `results/`. |
| `python -m hr_assistant.tracing` | Check that LangSmith tracing is wired up. |

## Documentation

Read `docs/` in order — [01](docs/01-overview.md)–[08](docs/08-the-agent.md)
for the RAG pipeline, [09](docs/09-reliability.md)–[10](docs/10-evaluation-and-redteam.md)
and [14](docs/14-llm-routing.md)–[15](docs/15-content-guardrails.md) for this
stage. [11](docs/11-gcp-apis-and-iam.md)–[13](docs/13-access-control.md),
[16](docs/16-hosting-architecture.md) describe the `deployment` stage.
