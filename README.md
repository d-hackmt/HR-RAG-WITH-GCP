# HR Policy Assistant — Basic RAG

> **This is the `basic-rag` branch — stage 1 of 3.**
> A plain, working RAG agent: ingestion, hybrid search, re-ranking, an
> agent with memory, a CLI and a Streamlit UI, LangGraph Studio. No
> guardrails, no evaluation, no deployment — those come next.
>
> | Branch | Adds |
> |---|---|
> | **`basic-rag`** *(here)* | the RAG pipeline end to end |
> | `security` | safety guardrails, scope filter, semantic cache, evaluation, red-team, LLM fallback |
> | `deployment` | Docker, Cloud Run, Google OAuth |

A RAG agent that answers HR-policy questions from real policy documents —
retrieval, metadata plumbing, hybrid (dense + BM25) search, and Jina
re-ranking for grounded, cited answers. The model is Vertex AI Gemini.

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
`QDRANT_URL`, `QDRANT_API_KEY`. `LANGSMITH_API_KEY` + `LANGSMITH_TRACING=true`
are optional (request tracing).

## The code, in reading order

Every file is numbered in its docstring. `hr_assistant/`: **01** config ·
**02** prompts · **03** logging · **04** document_loader · **05** processor ·
**06** splitter · **07** embeddings · **08** vector_store · **09** ingestion ·
**10** reranker · **11** tools · **12** llm · **13** agent · **14** pipeline ·
**15** tracing. Entry scripts: **16** `ingest.py` · **17** `main.py` ·
**18** `app.py` · **19** `studio_graph.py`.

## The scripts

| Command | What it does |
|---|---|
| `python ingest.py` | Ingest the corpus: local `data/` → GCS raw → GCS processed (pdf/docx/pptx parsed once) → Qdrant. Builds **both** collections. `--force` to rebuild, `--hr-only` / `--noisy-only` to limit scope. |
| `python main.py` | CLI demo — a few questions through the agent. Bootstraps ingestion on first run if needed. |
| `streamlit run app.py` | The chat UI. One conversation thread per browser session. |
| `python -m hr_assistant.tracing` | Check that LangSmith tracing is wired up. |
| `langgraph dev` | Open LangGraph Studio on the agent graph. |

## How it works

```
question
  -> agent (LangChain create_agent + InMemorySaver memory)
       -> search_hr_policy tool
            -> Qdrant hybrid retrieve (wide: RERANK_CANDIDATE_K)
            -> Jina reranker (narrow: TOP_K_RESULTS)  ->  cited chunks
  -> Gemini writes the answer from those chunks  ->  answer + citation
```

Ingestion is a **separate** step — `hr_assistant/ingestion.py` is the only
writer to Qdrant. Everything else connects to what it built.

## Documentation

Read `docs/` in order — [01 Overview](docs/01-overview.md)–[08 The Agent](docs/08-the-agent.md)
for this stage. [commands/commands.md](commands/commands.md) has every provisioning command.
