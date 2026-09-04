# Branch ladder — HR Policy Assistant

This project is taught in three branches, each building on the last. A
student walks up the ladder; `git diff` between branches is the lesson.

| Branch | What it is | Adds over the previous |
|---|---|---|
| **`basic-rag`** *(this branch)* | A plain, working RAG agent | ingestion (both Qdrant collections, multi-format parsing), hybrid search, Jina re-rank, an agent with memory, CLI + Streamlit + LangGraph Studio, LangSmith tracing. Model: Vertex AI Gemini, called directly. |
| `security` | Reliability & safety | Model Armor input/output guardrail (+ `gemini_lite` fallback), the scope guardrail (category filter + relevance floor), identity-lock prompt, semantic cache, LangSmith evaluation, the 7-attack red-team suite, a LiteLLM Router with a Groq fallback model. |
| `deployment` | Ship it | Dockerfile + docker-compose, Cloud Run deploy, Google OAuth gate + employee allow-list, Secret Manager. Ends up matching `main`. |

`main` holds the complete system (= `deployment`).

## Conventions (all branches)

- Every module in `hr_assistant/` and every root entry script starts its
  docstring with `NN · name — purpose`, numbered in reading order.
- Small, single-purpose files. Split + renumber if one grows two jobs.
- Config values in `config.py` (01); system-prompt text in `prompts.py` (02).

## Working on `basic-rag`

- The pipeline is deliberately minimal — see the `hr-assistant-dev` skill
  for the contract (`build_hr_assistant()` → `agent`; `ask(agent, q, thread_id)`).
- Don't pull `security` / `deployment` concepts back in.
- Ingestion builds **both** collections; the app uses the clean one.
