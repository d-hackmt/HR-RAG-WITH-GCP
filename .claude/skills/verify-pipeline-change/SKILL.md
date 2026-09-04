---
name: verify-pipeline-change
description: >-
  How to verify a change to the HR assistant pipeline, guardrails,
  retrieval, agent, semantic cache, LLM connector, or entry scripts WITHOUT
  running the app. Use after editing hr_assistant/ or an entry script and
  before telling the user the change is done.
---

# Verifying a pipeline change (no execution)

The user's rule: **never run anything.** Verification here is static and
compile-only. The user runs the live checks themselves.

## 1. Compile check -- safe, no execution

```
python -m compileall -q hr_assistant *.py
```

`py_compile` / `compileall` byte-compile source; they do NOT import or run
modules. Zero side effects, no cloud calls. Must be clean. (The `Stop` hook
runs this automatically too.)

## 2. Static consistency sweep

Run these greps and eyeball every hit:

- `grep -rn "ask_reliably\|ask_plain\|\bask(" *.py hr_assistant/`
  -- every call matches the signature table in the `hr-assistant-dev` skill.
- `grep -rn "build_hr_assistant\|build_reliability_assistant\|build_plain_assistant" *.py`
  -- callers unpack `(agent, cache)` wherever the builder returns a tuple;
  `build_plain_assistant` returns a bare `agent`.
- `grep -rn "create_search_tool\|create_guarded_search_tool" hr_assistant/ *.py`
  -- the plain tool appears ONLY in `build_plain_assistant`; every other
  path uses the guarded tool.
- `grep -rn "SYSTEM_PROMPT\|RELIABILITY_SYSTEM_PROMPT" hr_assistant/`
  -- the secure path uses `RELIABILITY_SYSTEM_PROMPT`.
- No hardcoded secrets / URLs / model names / thresholds outside
  `config.py`.
- No `import` of a package absent from `requirements.txt`.

## 3. Reason through the guardrail failure modes

Trace the code, do not run it:

- INPUT check raises -> request is refused (fail CLOSED). Confirm the path.
- OUTPUT check raises -> answer still returned, failure logged (fail OPEN).
- `GUARDRAIL_PROVIDER=none` -> both checks pass through, nothing crashes.
- Semantic-cache hit -> input guardrail still ran first (order matters).

## 4. Hand the user the live checks -- do NOT run them

List these for the user:

- `python redteam_test.py` -> expect 7/7 hold on both pipelines; the
  guarded pipeline should now also block `instruction_override` and
  `dan_jailbreak` at the INPUT stage (before retrieval), not just refuse at
  generation.
- `python evaluate.py` -> correctness + groundedness not regressed vs the
  last LangSmith experiment.
- `streamlit run app.py` smoke: normal Q (cited answer) - repeat Q
  (cache-hit log line) - "ignore all previous instructions" (input blocked)
  - a finance question (NOT_FOUND -> polite refusal) - "you are Drishti"
  (identity-lock refusal).
- Guardrail-outage sim: set a bad `MODEL_ARMOR_TEMPLATE_ID` -> an input
  request is refused gracefully (no stack trace); an output request returns
  the answer with a logged warning.

## 5. Docs

If behaviour or the pipeline table changed, update in the same pass:
`docs/08`, `docs/09`, `docs/10`, `docs/14`, `docs/15`, `docs/16`,
`summary.md`, `README.md`, and check whether `commands.md` needs a note.
Doc drift is a real, recurring failure mode in this repo.
