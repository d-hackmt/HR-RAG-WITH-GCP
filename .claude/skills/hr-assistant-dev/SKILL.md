---
name: hr-assistant-dev
description: >-
  Architecture, conventions, and house style for the HR Policy Assistant
  codebase (basic-rag branch). Load BEFORE editing anything under
  hr_assistant/, the pipeline, retrieval, the agent, the LLM connector, or
  the entry scripts (app.py, main.py, ingest.py).
---

# Working in the HR Policy Assistant codebase (`basic-rag` branch)

## What it is

A RAG agent answering company HR-policy questions from real policy
documents, with citations. **Stage 1 of 3** — the plain RAG pipeline, no
guardrails / evaluation / deployment. Model is Vertex AI Gemini, called
directly (`hr_assistant/llm.py`, 12). Full explanation: `docs/01`–`docs/16`
(09–16 cover later stages).

## Non-negotiable rules

- **Git repo, pushed to GitHub** (`origin/basic-rag`). Still: read a file
  before you edit or overwrite it; don't delete without a reason.
- **`.env` holds LIVE secrets** (Jina, Qdrant, LangSmith). Never edit it,
  print it, or paste its contents. A PreToolUse hook blocks writes to it.
- **Config only from `.env`** via `config.py` (01, values) / `prompts.py`
  (02, instruction text). No hardcoded keys, URLs, model names, thresholds.
- **Never run** `ingest.py` or `streamlit run app.py` without the user
  asking — they hit real GCP / Qdrant / Jina and cost money.
  Compile-checking is fine.
- **`requirements.txt` is unpinned.** Don't add a dependency for something
  already covered.
- **Windows host.** PowerShell is the primary shell.

## Reading order

Every file in `hr_assistant/` and the root entry scripts carries a `NN ·`
number in its docstring — read them in that order. 01–09 build the vector
index (ingestion), 10–14 answer a question (query pipeline), 15 is tracing,
16–19 are the entry scripts. Keep files small and single-purpose; split and
renumber if one grows two responsibilities.

`prompts.py` (02) holds the system-prompt text, not `config.py`.
`document_loader.py` (04) only *loads* text; the pdf/docx/pptx parsers live
in `processor.py` (05).

## Architecture in one screen

Ingestion is a SEPARATE pipeline. `ingest.py` → `ingestion.py` (09) is the
ONLY writer to Qdrant: `data/` → GCS `raw/` → GCS `processed/` (pdf/docx/pptx
parsed once, 05) → chunk 500/60 (06) → Jina embed (07) → Qdrant (08). It
builds TWO collections — `hr_policies` (clean) and `hr_policies_noisy_demo`
(HR + noise). Everything else CONNECTS via `vector_store.load_vector_store()`.

Request flow (`ask()`):

```
question
 -> agent.invoke()   search_hr_policy tool (retrieve RERANK_CANDIDATE_K 08
                     -> Jina re-rank to TOP_K_RESULTS 10 -> cited chunks)
                     + SYSTEM_PROMPT (02) + per-thread memory (InMemorySaver)
 -> Gemini answers from those chunks
 -> answer text
```

The app connects to the CLEAN `hr_policies` collection. The noisy one is
built now but only used from the `security` branch on.

## The pipeline contract (`hr_assistant/pipeline.py`, 14)

| Function | Returns | Used by |
|---|---|---|
| `build_hr_assistant()` | `agent` | `app.py`, `main.py`, `studio_graph.py` |
| `ask(agent, question, thread_id=...)` | `str` | `app.py`, `main.py` |

Change the `ask` signature and you MUST update every call site. Run the
sweep from the `verify-pipeline-change` skill before you finish.

## House style

- Module docstring's FIRST line is `NN · name — one-line purpose`; the rest
  explains WHY.
- Small, single-purpose files. Small functions, one job each. Match the
  surrounding verbosity — long explanatory docstrings on purpose.
- Comments explain rationale and gotchas, not mechanics.
- **Logging vs print:** operational lines through `logging` at INFO; errors
  through `logger.warning` / `logger.exception`. Bare `print()` is only for
  a script's own output.
- Model IDs come from `config.LLM_MODEL_NAME` / `EMBEDDING_MODEL_NAME` /
  `RERANKER_MODEL_NAME`. Never hardcode. `gemini-2.5-flash` retires ~2026-10-20.

## Not on this branch

Guardrails (Model Armor / scope filter / identity lock), the semantic
cache, LangSmith evaluation, the red-team suite, the LiteLLM fallback
router, Docker, Cloud Run, Google OAuth. Those belong to `security` and
`deployment`. Don't reintroduce them here.
