# Branch ladder — HR Policy Assistant

This project is taught in three branches, each building on the last. A
student walks up the ladder; `git diff` between branches is the lesson.

| Branch | What it is | Adds over the previous |
|---|---|---|
| `basic-rag` | A plain, working RAG agent | ingestion (both Qdrant collections, multi-format parsing), hybrid search, Jina re-rank, an agent with memory, CLI + Streamlit + LangGraph Studio, LangSmith tracing. Model: Vertex AI Gemini, called directly. |
| **`security`** *(this branch)* | Reliability & safety | Model Armor input/output guardrail (+ `gemini_lite` fallback), the scope guardrail (category filter + relevance floor), identity-lock prompt, semantic cache, LangSmith evaluation, the 7-attack red-team suite, a LiteLLM Router with a Groq fallback model. |
| `deployment` | Ship it | Dockerfile + docker-compose, Cloud Run deploy, Google OAuth gate + employee allow-list, Secret Manager. Ends up matching `main`. |

`main` holds the complete system (= `deployment`).

## Conventions (all branches)

- Every module in `hr_assistant/` and every root entry script starts its
  docstring with `NN · name — purpose`, numbered in reading order
  (config 01 → pipeline 17 → entry scripts 21–27).
- Small, single-purpose files. Split + renumber if one grows two jobs.
- Config values in `config.py` (01); system-prompt text in `prompts.py` (02).

## Working on `security`

- Full secure pipeline — see the `hr-assistant-dev` skill for the contract
  (the three `build_*` variants, `ask(agent, cache, q, thread_id)` vs
  `ask_plain`), and the three guardrail layers (safety / scope / identity).
- Guardrail failure modes: input fails CLOSED, output fails OPEN.
- Don't pull `deployment` concepts (Dockerfile, Cloud Run, OAuth) back in.

## Call-site map (keep in sync)

| Caller | Builder | Ask fn |
|---|---|---|
| `app.py` | `build_hr_assistant()` → `(agent, cache)` | `ask(agent, cache, q, thread_id)` |
| `main.py` | `build_hr_assistant()` → `(agent, cache)` | `ask(agent, cache, q)` |
| `demo_reliability.py` | `build_reliability_assistant()` → `(agent, cache)` | `ask(agent, cache, q, thread_id)` |
| `redteam_test.py` (plain) | `build_plain_assistant()` → `agent` | `ask_plain(agent, q, thread_id)` |
| `redteam_test.py` (guarded) | `build_reliability_assistant()` → `(agent, cache)` | `ask(agent, cache, q, thread_id)` |
| `evaluation.py` | builds its own agent (guarded tool) | `ask_plain(agent, q, thread_id)` |
| `studio_graph.py` | `build_reliability_assistant()` → `(agent, _cache)` | n/a (returns the graph) |
