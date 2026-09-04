# Handoff — HR Policy Assistant

For a Claude session or a person picking this project up cold. Full detail
is in `docs/01` → `docs/16`; this page is the fast orientation. Working
conventions and the pipeline contract are in `CLAUDE.md` + the
`hr-assistant-dev` skill.

> Last worked on: two passes — (1) wiring the full safety pipeline into the
> deployed app, (2) a codebase audit (20 findings, all fixed). All 28
> Python files compile clean. Runtime behaviour not yet re-verified — run
> the live checks below. Details: `.claude/IMPLEMENTATION-PLAN.md`.

---

## TL;DR

A RAG agent that answers company HR-policy questions from real policy
documents, with citations. Built in three layers: the RAG pipeline →
reliability (guardrails, memory, cache, red-team) → deployment on Google
Cloud Run behind OAuth with a governed LLM gateway.

```bash
cp .env.example .env      # fill in PROJECT_ID, LOCATION, GCS_BUCKET_NAME,
                          # JINA_API_KEY, QDRANT_URL, QDRANT_API_KEY
                          # no Model Armor template? add GUARDRAIL_PROVIDER=gemini_lite
pip install -r requirements.txt
gcloud auth application-default login
python ingest.py          # build the Qdrant collections (once)
python main.py            # or: streamlit run app.py
```

---

## Mental model (read this before touching the code)

**Ingestion is a separate step.** `ingest.py` is the *only* thing that
writes to Qdrant: `data/` → GCS `raw/` → GCS `processed/` (pdf/docx/pptx
parsed once) → embed → Qdrant. It's idempotent. Everything else just
*connects* to what it built (`vector_store.load_vector_store`). If a
collection is missing, `main.py`/`app.py` bootstrap ingestion once on
startup, then it's just a connect.

**The guarded pipeline is the default now.** `app.py` and `main.py` call
`build_hr_assistant()` + `ask()` — the full secure flow. There are still
two Qdrant collections, and a bare "plain" build survives only as the
red-team baseline.

| | Collection | Search tool | Guardrails | Used by |
|---|---|---|---|---|
| **Guarded (clean)** | `hr_policies` (HR only) | `create_guarded_search_tool` (category filter + relevance floor) | Model Armor in/out (history-aware) + semantic cache + identity-lock prompt | `main.py`, `app.py` (**the deployed app**) |
| **Guarded (noisy)** | `hr_policies_noisy_demo` (HR + 8 non-HR noise docs) | same | same | `demo_reliability.py`, `redteam_test.py` |
| **Plain** | `hr_policies` | `create_search_tool` | none (plain prompt only) | `redteam_test.py` baseline only |

The noise corpus (Finance/Sales/Ops/Business, mixed into the *same*
collection as HR) exists so retrieval and the scope guardrail are tested
against real cross-domain noise, not a clean single-domain set.

**One request (`ask()`):** input Model Armor (current question + last
`GUARDRAIL_HISTORY_TURNS` *user turns*, human messages only; fails
**closed** on a provider error) → semantic cache lookup (bounded + TTL) →
agent → `search_hr_policy` tool (category-filtered retrieve 12 → Jina
re-rank to 5 → relevance floor → cited text) → Gemini answers from those
chunks → output Model Armor (fails **open** on a provider error) → cache
store. A cache hit and an output block are both written into thread memory.

**`ask_plain()`** is the same agent call with none of that — used by
`evaluate.py` (answer quality only) and the red-team plain baseline.
`ask_reliably` is kept as an alias of `ask`.

---

## The stack

| Job | Choice |
|---|---|
| Orchestration | LangChain **v1** (`langchain.agents.create_agent`) + LangGraph (`InMemorySaver` memory) |
| App LLM | Vertex AI Gemini `gemini-2.5-flash` (`LLM_MODEL_NAME`, env-overridable — **retires ~2026-10-20**) — direct, or via the LiteLLM gateway (deployed). Gateway falls back to Groq `llama-3.3-70b-versatile` if Vertex errors |
| Embeddings / reranker | Jina `jina-embeddings-v2-base-en` (768-dim) / `jina-reranker-v2-base-multilingual` — both env-overridable (`EMBEDDING_MODEL_NAME` / `RERANKER_MODEL_NAME`) |
| Vector store | Qdrant Cloud, hybrid dense + BM25 |
| Safety guardrail | Vertex AI Model Armor (fallback: `gemini_lite` classifier; `none` disables) |
| Ingestion storage | Google Cloud Storage |
| Hosting | Docker + Cloud Run (two services) |
| Tracing + eval | LangSmith; `openevals` prompts; Groq `openai/gpt-oss-120b` as the eval judge |

---

## File map

### `hr_assistant/`
| Module | Responsibility |
|---|---|
| `config.py` | All settings from `.env` (model IDs env-overridable); both system prompts (incl. identity lock) |
| `logging_config.py` | `configure_logging()` — CLI entry points + app.py call it so the guardrail / cache INFO lines show |
| `ingestion.py` | The ingestion pipeline (upload → parse → chunk → embed → upsert), idempotent |
| `document_loader.py` | Load `.txt` from GCS; load parsed JSON from the processed zone |
| `processor.py` | Parse pdf/docx/pptx → one JSON per file in `processed/` |
| `splitter.py` | `RecursiveCharacterTextSplitter` (500 / 60) |
| `embeddings.py` | Jina embeddings model |
| `vector_store.py` | `build_vector_store` (ingest only, hybrid) · `load_vector_store` / `collection_exists` (connect, shared client) · `get_retriever` (`filter_categories`) |
| `reranker.py` | Jina reranker REST call |
| `tools.py` | `create_guarded_search_tool` (scope guardrail — every real path) · `create_search_tool` (plain, red-team baseline only) |
| `llm.py` | Gemini direct, or gateway via `ChatOpenAI` + a Google ID token cached ~50 min and re-minted per request (process-shared httpx clients) |
| `agent.py` | `create_agent` + checkpointer; `create_hr_agent` (plain baseline) / `create_reliability_agent` (default) |
| `guardrails.py` | `check_input` / `check_output` — Model Armor or a memoised `gemini_lite`; provider errors → input fails closed, output fails open; `@traceable` |
| `semantic_cache.py` | In-memory cosine cache; bounded (`MAX_ENTRIES`) + per-entry TTL; single-matmul lookup; reuses lookup's embedding on store; `@traceable` |
| `pipeline.py` | `build_hr_assistant` / `build_reliability_assistant` (guarded, → `(agent, cache)`) · `build_plain_assistant` (→ `agent`) · `ask` (secure; user-history screening; cache-hit + output-block both written to thread memory) / `ask_plain` / `ask_reliably` alias |
| `tracing.py` | `enable_tracing()` + `check_langsmith_tracing()` (fires one real traced run) |
| `evaluation.py` | LangSmith dataset + experiment; correctness + groundedness; 18 test cases |
| `studio_graph.py` | LangGraph Studio entry (`langgraph dev`) |

### Entry scripts (repo root)
| Script | What it does |
|---|---|
| `ingest.py` | Run ingestion. Flags: `--force` `--hr-only` `--noisy-only` `--no-upload` |
| `main.py` | CLI demo, **secure pipeline** (`ask()`) |
| `app.py` | Streamlit chat UI, **secure pipeline**. OAuth when configured, else "open local mode". Tracing + guardrail status in the sidebar |
| `demo_reliability.py` | 5-scenario walkthrough of the secure pipeline (noisy collection) |
| `redteam_test.py` | 7 attacks vs the secure pipeline + a bare plain baseline → `results/redteam_results.json` |
| `evaluate.py` | LangSmith eval (guarded tool + reliability prompt, no Model Armor) — needs `LANGSMITH_API_KEY` + `GROQ_API_KEY` |

### Infra
| File | What |
|---|---|
| `Dockerfile` | App image; pre-downloads the BM25 model at build time |
| `docker-compose.yml` | Local run: `app` service + `ingest` / `eval` one-off jobs (`--profile tools`) |
| `gateway/` | LiteLLM proxy — `litellm-config.yaml` (Gemini primary, Groq fallback) + `Dockerfile`, its own Cloud Run service |
| `langgraph.json` | Points `langgraph dev` at `studio_graph.py` |
| `requirements.txt` | `langchain` / `langchain-core` pinned `>=1.0,<2`, `langgraph>=0.2`; the rest unpinned — `pip freeze` after any deliberate upgrade |
| `.claude/` | `settings.json` (hooks) · `hooks/` (syntax check, `.env` guard, `compileall` sweep) · `skills/` · `DOS-AND-DONTS.md` · `IMPLEMENTATION-PLAN.md` |
| `CLAUDE.md` | Auto-loaded project guide — hard rules + entry-point map |
| `data/` | 10 HR `.txt` + `data/noise/` (8 non-HR docs) |
| `results/` | Red-team output + writeup |
| `docs/` `01`–`16` · `commands.md` | Explanation, then every command creation → teardown |

---

## Running it

**Local**

```bash
python ingest.py             # once
python main.py               # CLI, secure pipeline
streamlit run app.py         # chat UI  (open local mode without OAuth secrets)
python demo_reliability.py   # secure-pipeline walkthrough (noisy collection)
python redteam_test.py       # adversarial pass
python evaluate.py           # LangSmith eval
python -m hr_assistant.tracing   # confirm tracing works
```

Local dev without a Model Armor template: set `GUARDRAIL_PROVIDER=gemini_lite`
(one Gemini call, no GCP setup) or `GUARDRAIL_PROVIDER=none` in `.env`.

**Verify after the recent changes** (compile is already clean):
`python redteam_test.py` — 7/7 hold on both pipelines; the guarded side
should now also BLOCK `instruction_override` / `dan_jailbreak` at the input
stage. `python evaluate.py` — correctness/groundedness not regressed. A
Streamlit smoke test: normal Q (cited) · repeat Q (cache-hit log line) ·
"ignore all previous instructions" (input blocked) · a finance question
(NOT_FOUND refusal) · "you are Drishti" (identity-lock refusal).

**Local via Docker** — needs `gcloud auth application-default login`; on
Windows set `GCLOUD_CONFIG=%APPDATA%\gcloud`:

```bash
docker compose run --rm ingest
docker compose up
docker compose run --rm eval
```

**Deployed** (project `rag-hr-assistant-demo` / `564821241199` /
`us-central1`):

| Service | URL | Access |
|---|---|---|
| `hr-rag-assistant` | `https://hr-rag-assistant-564821241199.us-central1.run.app` | Public page; Google OAuth + approved-email list to chat |
| `llm-gateway` | `https://llm-gateway-564821241199.us-central1.run.app` | Private; only the app's service account (Cloud Run IAM + a minted Google ID token) |

Two deploy bugs were hit and fixed: `fastembed`'s BM25 download rate-limited
on Cloud Run (→ pre-download at build time, doc 12); the gateway's shared
Bearer secret collided with Cloud Run IAM (→ minted Google ID token
instead, doc 14).

---

## Resolved (was open, now done — full list in `.claude/IMPLEMENTATION-PLAN.md`)

- `guardrails.py` catches provider errors: input fails **closed**, output
  fails **open** (`GUARDRAIL_FAIL_OPEN_*`).
- **The deployed app runs the secure pipeline** — `app.py` / `main.py` call
  `ask()` (Model Armor in/out + scope filter + cache + identity lock).
- The input guardrail screens the current question **plus the last N user
  turns** (`GUARDRAIL_HISTORY_TURNS`, default 6) — human messages only,
  never tool output or the assistant's own answers.
- A **semantic-cache hit** and an **output block** are both written into the
  thread's memory (`update_state`) — a follow-up still sees the turn, and a
  blocked answer is overwritten so it can't linger in context; the
  Streamlit transcript is kept in step.
- The eval agent uses the guarded tool + reliability prompt; groundedness
  context is rebuilt the tool's way (category-filtered retrieve 12 → Jina
  re-rank to 5).
- Semantic cache is bounded (`SEMANTIC_CACHE_MAX_ENTRIES`) + per-entry TTL
  (`SEMANTIC_CACHE_TTL_SECONDS`, default 1 h); lookup reuses its embedding
  on the following store; single-matmul scoring.
- Gateway ID token cached ~50 min, re-minted per request, on
  process-shared httpx clients (no per-call socket leak).
- `enable_tracing()` normalises `LANGSMITH_TRACING` (the string "false" is
  truthy).
- Model IDs (`LLM_MODEL_NAME` / `EMBEDDING_MODEL_NAME` / `RERANKER_MODEL_NAME`)
  are env-overridable — **`gemini-2.5-flash` retires ~2026-10-20**, migrate
  via env before then.
- Dead code removed: `config.REGION` (Python-side), `get_retriever`'s
  singular `filter_category`, `processor.py`'s unused `format` /
  `char_count` fields, `iter_parsed_raw_files`'s unused plural param.
- `logging` used for operational lines everywhere (`hr_assistant/logging_config.py`);
  bare `print()` is now only a script's own output.
- `langchain` / `langchain-core` pinned to `>=1.0,<2` (the `create_agent` API).

## Open items (if you continue this)

**Guardrails**
- The relevance floor only gates the *top* chunk; lower-scored chunks in
  the same response still reach the model.
- `RELEVANCE_THRESHOLD = 0.35` is uncalibrated (and would need re-tuning if
  the reranker model is changed).
- The category filter relies on exact string matches between the
  `Policy Category:` lines and `HR_POLICY_CATEGORIES`.
- History-aware screening only covers the last `GUARDRAIL_HISTORY_TURNS`
  user turns, not the whole thread.

**Evaluation**
- The eval skips Model Armor in/out (by design — it measures answer
  quality), and only uses good-faith questions.
- 18 hand-written cases, no variance reporting; references must track
  `data/*.txt`.
- The Groq judge fixes self-grading but hasn't been spot-checked for
  consistency.
- No cost / latency tracking. (Model Armor adds 2 calls/request in the app;
  the cache offsets repeats.)

**Ingestion**
- `main.py` / `app.py` silently bootstrap a full ingestion (GCS upload +
  embed) when a collection is missing — a lot of work on a "just run it".
- `load_vector_store` assumes `langchain-qdrant`'s default dense/sparse
  vector names match what `build_vector_store` created (true within one
  library version).

**Cache**
- In-memory, per-process — not shared across Cloud Run instances; a restart
  clears it. A shared backend (Redis) would be the next step if hit rate
  matters. Also not thread-safe (was never); the lookup→store embedding
  reuse degrades gracefully to a re-embed under a race, never a wrong one.

**Models**
- Still on Jina embeddings v2 (768-dim) + reranker v2. v3/v5 embeddings and
  reranker v3.5 exist; the embedding bump needs `ingest.py --force`, the
  reranker bump needs `RELEVANCE_THRESHOLD` recalibration.

---

## Gotchas for a fresh session

- **Read `CLAUDE.md` + the `hr-assistant-dev` skill first.** The pipeline
  function signatures (`ask(agent, cache, q, …)`, the three `build_*`
  variants) and the guardrail model are documented there; keep call sites
  in sync.
- **`.claude/` has hooks** — a PostToolUse Python syntax check, a
  PreToolUse block on `.env` writes, and a Stop-time `compileall` sweep.
  New hooks need a session reload / `/hooks` approval before they fire.
- **`requirements.txt` is mostly unpinned.** `langchain` / `langchain-core`
  are pinned `>=1.0,<2` (the `create_agent` API needs v1); everything else
  gets latest. If a fresh env breaks, the langchain family
  (`langchain-qdrant`, `langgraph`, `langchain-openai`) is the first
  suspect — pin exact versions with `pip freeze`.
- **`.env` holds live secrets** (Jina, Qdrant, LangSmith, Groq) in the
  working tree. It's `.dockerignore`'d, but rotate before sharing.
- **Local dev without Model Armor:** `GUARDRAIL_PROVIDER=gemini_lite` or
  `none` in `.env`, or the app's first request raises.
- **`app.py` needs a Streamlit `[auth]` secret** for the OAuth gate.
  Without it, it runs in "open local mode" (no login) rather than
  crashing.
- **`evaluate.py` needs `openevals`** (in `requirements.txt`) and a Groq
  key; it also uploads to LangSmith, so it needs `LANGSMITH_API_KEY`.
- **Not a git repo.** No `.git`, no history — deletions are permanent.
