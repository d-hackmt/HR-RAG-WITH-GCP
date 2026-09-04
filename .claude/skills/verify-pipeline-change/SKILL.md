---
name: verify-pipeline-change
description: >-
  How to verify a change to the HR assistant pipeline, retrieval, agent,
  LLM connector, or entry scripts WITHOUT running the app. Use after editing
  hr_assistant/ or an entry script and before telling the user the change is
  done. (basic-rag branch.)
---

# Verifying a pipeline change (no execution)

The user's rule: **never run anything.** Verification here is static and
compile-only. The user runs the live checks themselves.

## 1. Compile check

```
python -m compileall -q hr_assistant *.py
```

Byte-compiles source; does NOT import or run modules. Must be clean. (The
`Stop` hook runs this automatically too.)

## 2. Static consistency sweep

- `grep -rn "\bask(" *.py hr_assistant/` — every call is
  `ask(agent, question[, thread_id=...])`.
- `grep -rn "build_hr_assistant" *.py hr_assistant/` — returns a bare
  `agent` (no cache tuple on this branch).
- One search tool (`create_search_tool`); one prompt (`prompts.SYSTEM_PROMPT`).
- No hardcoded secrets / URLs / model names / thresholds outside `config.py`.
- No `import` of a package absent from `requirements.txt`.
- No leftover reference to `guardrails`, `semantic_cache`, `thread_memory`,
  `evaluation`, `ChatLiteLLM`, `litellm`, Model Armor, OAuth, or the
  scripts `evaluate.py` / `redteam_test.py` / `demo_reliability.py` — those
  belong to later branches.
- Every module docstring still starts with its `NN ·` number, in order.

## 3. Reason through the flow

- `build_hr_assistant()` → `check_api_keys()` → bootstrap if the collection
  is missing → `load_vector_store` → agent with the search tool.
- `ask()` → `agent.invoke` → return `.text` off the last message.
- Same `thread_id` reuses memory; a new one starts fresh (InMemorySaver).

## 4. Hand the user the live checks — do NOT run them

- `python main.py` → cited answers; a follow-up resolves using memory.
- `streamlit run app.py` → normal Q, context-dependent follow-up,
  "New conversation" resets.
- `python -m hr_assistant.tracing` → LangSmith connectivity check.
- `langgraph dev` → Studio loads the agent graph.

## 5. Docs

If behaviour or the pipeline contract changed, update `docs/03`–`docs/08`,
`README.md`, and check `commands.md` in the same pass.
