---
name: hr-assistant-dev
description: >-
  Architecture, conventions, and the guardrail model for the HR Policy
  Assistant codebase. Load BEFORE editing anything under hr_assistant/, the
  pipeline, guardrails, retrieval, the agent, the semantic cache, the LLM
  connector, or the entry scripts (app.py, main.py, ingest.py, evaluate.py,
  redteam_test.py, demo_reliability.py).
---

# Working in the HR Policy Assistant codebase

## What it is

A RAG agent answering company HR-policy questions from real policy
documents, with citations. Deployed on Google Cloud Run behind Google OAuth;
every model call is routed in-process by a LiteLLM Router (Gemini primary,
Groq fallback — `hr_assistant/llm.py`, doc 14). Full explanation:
`docs/01`-`docs/17` (17 = troubleshooting). Fast orientation: `README.md`.
This skill is the "before you touch the code" brief.

## Non-negotiable rules

- **Git repo, pushed to GitHub** (`origin/main`). Still: read a file before
  you edit or overwrite it, and don't delete without a reason.
- **`.env` holds LIVE secrets** (Jina, Qdrant, LangSmith, Groq). Never edit
  it, never print it, never paste its contents. A PreToolUse hook blocks
  writes to it. Config defaults go in `hr_assistant/config.py`; new
  variables get documented in `.env.example`.
- **Config only from `.env`** via `config.py`. No hardcoded keys, URLs,
  model names, or thresholds anywhere else -- import from
  `hr_assistant.config`.
- **Never run** `ingest.py`, `evaluate.py`, `redteam_test.py`,
  `demo_reliability.py`, or `streamlit run app.py` without the user asking
  -- they hit real GCP / Qdrant / Jina and cost money. Compile-checking
  (`py_compile`, `python -m compileall`) is fine; it does not execute
  anything.
- **`requirements.txt` is unpinned.** Don't add a dependency to solve
  something the stdlib or an already-present package covers.
- **Windows host.** PowerShell is the primary shell (Bash tool also
  available). Don't assume POSIX-only tooling.

## Reading order

Every file in `hr_assistant/` (and the root entry scripts) carries a
`NN ·` number in its module docstring — read them in that order. Ingestion
is 01–09, the query pipeline 10–17, then tracing / eval (18–20), then the
entry scripts (21–27). Keep numbers dense and in dependency order when you
add or move a file.

Small, single-purpose files: `prompts.py` (02) holds the system-prompt
text (not `config.py`); `thread_memory.py` (15) holds every checkpointer
operation `pipeline.ask()` performs; `evaluation_dataset.py` (19) is the
eval's Q/A pairs. `document_loader.py` (04) only *loads* text; the binary
parsers live in `processor.py` (05).

## Architecture in one screen

Ingestion is a SEPARATE pipeline. `ingest.py` -> `hr_assistant/ingestion.py`
is the ONLY thing that writes to Qdrant: `data/` -> GCS `raw/` -> GCS
`processed/` (pdf/docx/pptx parsed once) -> chunk (500/60) -> Jina embed ->
Qdrant. Idempotent. Everything else CONNECTS to what it built via
`vector_store.load_vector_store()`.

Request flow, secure / default path (`ask()`):

```
question
 -> check_input()    Model Armor; screens current turn + recent history; FAIL CLOSED on error
 -> cache.lookup()   semantic cache (cosine >= 0.93); a hit short-circuits here
 -> agent.invoke()   guarded search tool (category allow-list + post-rerank relevance floor)
                     + RELIABILITY_SYSTEM_PROMPT (identity lock + NOT_FOUND handling)
                     + per-thread memory (InMemorySaver)
 -> check_output()   Model Armor on the answer; FAIL OPEN on error
 -> cache.store()
 -> answer
```

## The pipeline contract (`hr_assistant/pipeline.py`)

| Function | Returns | Path | Used by |
|---|---|---|---|
| `build_hr_assistant()` | `(agent, cache)` | guarded, clean `hr_policies` collection | `app.py`, `main.py` |
| `build_reliability_assistant()` | `(agent, cache)` | guarded, mixed `hr_policies_noisy_demo` | `demo_reliability.py`, `redteam_test.py`, `studio_graph.py` |
| `build_plain_assistant()` | `agent` | NO guardrails, plain search tool, `SYSTEM_PROMPT` | `redteam_test.py` baseline only |
| `ask(agent, cache, q, thread_id=...)` | `str` | full secure flow above | app, main, demo, redteam-guarded |
| `ask_plain(agent, q, thread_id=...)` | `str` | raw `agent.invoke`, no checks / no cache | `evaluate.py`, redteam-plain |

If you change an `ask*` signature you MUST update every call site in the
table. Run the sweep from the `verify-pipeline-change` skill before you
finish.

## The three "guardrail" layers -- do not conflate them (see docs/15)

- **A. Safety guardrail** -- `hr_assistant/guardrails.py`, `check_input` /
  `check_output`. Provider is `model_armor` (default), `gemini_lite`, or
  `none`. Prompt injection / jailbreak / unsafe content, both directions.
  On a provider error: input fails CLOSED, output fails OPEN.
- **B. Scope guardrail** -- `hr_assistant/tools.py`
  `create_guarded_search_tool`: Qdrant category filter
  (`config.HR_POLICY_CATEGORIES`) + post-rerank `config.RELEVANCE_THRESHOLD`
  floor -> returns the `NOT_FOUND` sentinel, which
  `RELIABILITY_SYSTEM_PROMPT` turns into a clean refusal.
- **C. Identity lock** -- `prompts._IDENTITY_LOCK`, folded into both system
  prompts. Enforced by the model at generation time, not a classifier.

The deployed app uses the CLEAN `hr_policies` collection with the guarded
tool: the category filter is close to a no-op there (all docs are HR), but
the relevance floor still turns a weak match into "I don't have that"
instead of a stretchy answer.

## House style

- Module docstring's FIRST line is `NN · name — one-line purpose`; the rest
  explains WHY the module exists.
- Small, single-purpose files (roughly <150 lines of code). If a file grows
  two responsibilities, split it and renumber.
- Small functions, one job each. Match the surrounding verbosity -- this
  codebase writes long, explanatory docstrings on purpose.
- Comments explain rationale and gotchas, not mechanics.
- **Logging vs print:** operational lines (guardrail pass/block, cache
  hit/miss, ingestion progress) go through `logging` at INFO; errors
  through `logger.warning` / `logger.exception`. Entry points call
  `hr_assistant.logging_config.configure_logging()`. Bare `print()` is
  only for a script's own output -- the demo Q&A display, red-team
  markers, section headers.
- Model IDs come from `config.LLM_MODEL_NAME` / `EMBEDDING_MODEL_NAME` /
  `RERANKER_MODEL_NAME` (env-overridable). Never hardcode a model string
  elsewhere. `gemini-2.5-flash` retires ~2026-10-20.
- After any change, load the `verify-pipeline-change` skill and follow it.
