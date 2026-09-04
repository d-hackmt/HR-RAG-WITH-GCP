# Implementation plan — guardrails into the main app + reliability fixes

Living document. Claude ticks boxes as it goes; survives context loss.

## Goal

Make the DEPLOYED app secure by default: Model Armor input/output screening,
the structural scope guardrail, and the semantic cache all run in
`app.py` / `main.py` — not just in the demo / red-team scripts. Plus four
reliability fixes discussed alongside it.

## Locked decisions

- Guardrail failure mode: **input fails CLOSED, output fails OPEN**.
- `evaluate.py` moves onto the **guarded search tool** (no Model Armor
  added to the eval itself).
- The plain pipeline stays in the codebase as the red-team baseline only.
- The deployed app keeps using the CLEAN `hr_policies` collection.

## Phases

- [x] **0. Claude scaffolding** — hooks, settings.json, 2 skills, CLAUDE.md,
  DOS-AND-DONTS.md, this file.
- [x] **1. `guardrails.py`** — try/except around the provider call; input
  fails closed, output fails open; `logging`.
- [x] **2. `config.py`** — `GUARDRAIL_FAIL_OPEN_INPUT/OUTPUT`,
  `GUARDRAIL_HISTORY_TURNS`, `SEMANTIC_CACHE_MAX_ENTRIES/TTL_SECONDS`;
  system-prompt docstrings updated.
- [x] **3. `semantic_cache.py`** — `deque(maxlen=)` eviction + per-entry
  TTL + single-matmul lookup.
- [x] **4. `pipeline.py`** — `_build_guarded_assistant()`;
  `build_hr_assistant()` guarded + clean, returns `(agent, cache)`;
  `build_reliability_assistant()` guarded + noisy; `build_plain_assistant()`;
  `ask(agent, cache, q, thread_id)` secure flow + history-aware screening;
  `ask_plain(agent, q, thread_id)`; `ask_reliably = ask` alias.
- [x] **5. `app.py`** — `(agent, cache)`; secure `ask()`; blocked answer →
  `st.warning`, kept out of the visible transcript; guardrail sidebar caption.
- [x] **6. `main.py`** — `(agent, cache)` + `ask(agent, cache, q)`.
- [x] **7. `evaluation.py`** — guarded tool + `create_reliability_agent` +
  `ask_plain`; groundedness context = category-filtered retrieve 12 →
  `rerank()` → top 5.
- [x] **8. `redteam_test.py`** — plain baseline via `build_plain_assistant`
  + `ask_plain`; guarded via `build_reliability_assistant` + `ask`; docstring.
- [x] **9. `demo_reliability.py`** — `ask_reliably` → `ask`. `studio_graph.py`
  needs no change (already unpacks the tuple).
- [x] **10. `llm.py`** — token cached ~50 min, re-minted per request via
  httpx sync + async auth hooks. `httpx` added to requirements.txt.
- [x] **11. Docs** — `docs/07`, `08`, `09`, `10`, `14`, `15`, `16`,
  `summary.md`, `README.md`.
- [x] **12. `commands.md` + `.env.example`** — guardrail-in-app note,
  local-dev `GUARDRAIL_PROVIDER` guidance, new tuning vars, verification step.
- [ ] **13. Final compile check** — `python -m compileall -q hr_assistant *.py`
  (user runs, or the Stop hook once `.claude/settings.json` is approved).

## Status: code complete — pending the Phase 13 compile check.

`agent.py` docstrings also updated (create_hr_agent is now baseline-only,
create_reliability_agent is the default).

---

## Round 2 — codebase audit fixes (20 findings)

All applied. Verified against current docs (LangChain v1 `create_agent`,
`add_messages` replace-by-id, `ChatOpenAI` http_client pair, gemini-2.5-flash
retirement ~2026-10-20).

- [x] 1. `pipeline._input_text_for_screening` — human messages only (no
  tool output / policy text into Model Armor); last N *user turns*.
- [x] 2. `tools.py` module docstring — guarded is the default, plain is
  red-team-only.
- [x] 3. cache hit now written to thread memory (`_record_turn` /
  `update_state`) so a follow-up resolves.
- [x] 4. output block overwrites the unsafe answer in memory by id
  (`_overwrite_answer_in_memory`); `app.py` mirrors it in the transcript,
  input block stays out of both.
- [x] 5. `guardrails._gemini_lite_client()` memoised; `llm.py` httpx
  clients are process-shared singletons.
- [x] 6. `config.REGION` removed (Python-side dead; kept in .env for gcloud).
- [x] 7. `get_retriever` singular `filter_category` removed (+ `MatchValue`
  import, docs/06 example).
- [x] 8. `processor.py` drops unused `format` / `char_count` record fields.
- [x] 9. `iter_parsed_raw_files(bucket, prefix)` — single prefix.
- [x] 10. `SemanticCache._embed` reuses lookup's embedding on the next store.
- [x] 11. `_qdrant_client` is `@lru_cache`d (one client / connection pool).
- [x] 12. `build_vector_store` default `hybrid=True` (matches load).
- [x] 13/14. `ingest_noisy_corpus` — no wasted processed-zone load on `--force`.
- [x] 15. `enable_tracing()` normalises the truthy "false" string.
- [x] 16. `logging` for operational lines (`hr_assistant/logging_config.py`);
  entry points call `configure_logging()`; `print()` kept only for script output.
- [x] 17. `evaluation.run_evaluation` builds one judge client, shares it.
- [x] 18. `requirements.txt` pins `langchain`/`langchain-core` `>=1.0,<2`.
- [x] 19. `JinaEmbeddings` from langchain_community — verified current, no change.
- [x] 20. Model IDs env-overridable (`LLM_MODEL_NAME` etc.) + dated
  retirement note; models themselves unchanged (migration cost).

Also touched: `.env.example`, `gateway/litellm-config.yaml`, `commands.md`
(model-migration section), `docs/06`, `summary.md`, `hr-assistant-dev`
skill, `DOS-AND-DONTS.md`.

## Round 2 status: code complete — pending the compile check.

`python -m compileall -q hr_assistant *.py`

## Call-site map (keep in sync)

| Caller | Builder | Ask fn |
|---|---|---|
| `app.py` | `build_hr_assistant()` -> `(agent, cache)` | `ask(agent, cache, q, thread_id)` |
| `main.py` | `build_hr_assistant()` -> `(agent, cache)` | `ask(agent, cache, q)` |
| `demo_reliability.py` | `build_reliability_assistant()` -> `(agent, cache)` | `ask(agent, cache, q, thread_id)` |
| `redteam_test.py` (plain) | `build_plain_assistant()` -> `agent` | `ask_plain(agent, q, thread_id)` |
| `redteam_test.py` (guarded) | `build_reliability_assistant()` -> `(agent, cache)` | `ask(agent, cache, q, thread_id)` |
| `evaluation.py` | builds its own agent (guarded tool) | `ask_plain(agent, q, thread_id)` |
| `studio_graph.py` | `build_reliability_assistant()` -> `(agent, _cache)` | n/a (returns the graph) |
