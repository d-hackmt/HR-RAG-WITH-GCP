# HR Policy Assistant — project guide for Claude

**Branch: `security` (stage 2 of 3).** The `basic-rag` pipeline plus the
reliability & safety layer: input/output safety guardrail (Model Armor, with
a `gemini_lite` fallback), the structural scope guardrail, an identity-lock
prompt, a semantic cache, LangSmith evaluation, a red-team suite, and a
LiteLLM Router (Vertex Gemini primary, Groq fallback). NO deployment on this
branch — Docker / Cloud Run / Google OAuth come in `deployment`. Full docs:
`docs/01`–`docs/16`.

## Before you touch the code

Load the **`hr-assistant-dev`** skill (architecture, the pipeline contract,
the guardrail model, house style). After a change, load
**`verify-pipeline-change`**. Short rules: `.claude/DOS-AND-DONTS.md`.

## Hard rules

- **Git repo, pushed to GitHub** (`origin/security`). Still read before you
  edit; never delete without reason.
- **`.env` = live secrets.** Never edit / print / share it. Defaults go in
  `config.py` (values) / `prompts.py` (instruction text); new variables get
  documented in `.env.example`.
- **Config only from `.env`** through `hr_assistant/config.py`.
- **Never run** `ingest.py`, `evaluate.py`, `redteam_test.py`,
  `demo_reliability.py`, `streamlit run app.py` unprompted — real cloud,
  real cost. Compile checks (`python -m compileall`) are fine.
- **`requirements.txt` is unpinned** — don't add dependencies casually.
- Windows host; PowerShell shell.

## Shape of the system

- **Files are numbered.** Every module's docstring starts `NN · name — …`;
  read `hr_assistant/` in that order (config 01 → pipeline 17 → entry
  scripts 21–27). Keep files small and single-purpose.
- **Ingestion is separate.** `ingest.py` → `hr_assistant/ingestion.py` (09)
  is the only writer to Qdrant. Two collections: `hr_policies` (clean — the
  app) and `hr_policies_noisy_demo` (HR + non-HR noise — reliability /
  red-team).
- **Guarded by default.** `app.py` / `main.py` run the full secure flow:
  `ask()` = input guardrail → semantic cache → guarded-tool agent → output
  guardrail. The plain pipeline stays only as the red-team baseline
  (`build_plain_assistant` / `ask_plain`).
- **Model routing** (Gemini primary, Groq fallback) is the in-process
  LiteLLM Router in `hr_assistant/llm.py` (12).
- Pipeline function signatures and their callers: in the `hr-assistant-dev`
  skill. Keep every call site in sync.

## Entry points

| Script | Pipeline | What it does |
|---|---|---|
| `main.py` (22) | secure | CLI demo |
| `app.py` (23) | secure | Streamlit UI (no auth on this branch) |
| `ingest.py` (21) | — | build both Qdrant collections (idempotent) |
| `evaluate.py` (26) | guarded tool, no Model Armor | LangSmith correctness + groundedness |
| `demo_reliability.py` (24) | secure | guarded-pipeline walkthrough |
| `redteam_test.py` (25) | plain + secure | 7 attacks against both pipelines |

## Hooks in this repo (`.claude/settings.json`)

- **PreToolUse** — blocks writes to `.env`.
- **PostToolUse** — byte-compiles a just-edited `.py` file (syntax check).
- **Stop** — whole-repo `compileall` + stale-reference sweep.

All are compile-only; none execute the app.
