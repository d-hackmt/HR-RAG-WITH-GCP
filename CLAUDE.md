# HR Policy Assistant — project guide for Claude

RAG agent answering company HR-policy questions from real policy documents,
with citations. Deployed on Google Cloud Run behind Google OAuth; every
model call is routed in-process by a LiteLLM Router (Gemini primary, Groq
fallback). Full docs: `docs/01`–`docs/17` (17 = troubleshooting). Fast
orientation: `README.md`.

## Before you touch the code

Load the **`hr-assistant-dev`** skill (architecture, the pipeline contract,
the guardrail model, house style). After a change, load
**`verify-pipeline-change`**. The short rules are in
`.claude/DOS-AND-DONTS.md`.

## Hard rules

- **Git repo, pushed to GitHub** (`origin/main`) — but still read before you
  edit, and don't delete without reason.
- **`.env` = live secrets.** Never edit / print / share it. Defaults go in
  `config.py`; new variables get documented in `.env.example`.
- **Config only from `.env`** through `hr_assistant/config.py`.
- **Never run** `ingest.py`, `evaluate.py`, `redteam_test.py`,
  `demo_reliability.py`, `streamlit run app.py` unprompted — real cloud,
  real cost. Compile checks (`python -m compileall`) are fine.
- **`requirements.txt` is unpinned** — don't add dependencies casually.
- Windows host; PowerShell shell.

## Shape of the system

- **Files are numbered.** Every module's docstring starts `NN · name — …`;
  read `hr_assistant/` in that order (config 01 → pipeline 17 → entry
  scripts 21–27). Keep files small and single-purpose; split + renumber if
  one grows two jobs.
- **Ingestion is separate.** `ingest.py` → `hr_assistant/ingestion.py` is
  the only writer to Qdrant. Everything else connects to what it built.
- **Two collections:** `hr_policies` (clean — the deployed app) and
  `hr_policies_noisy_demo` (HR + non-HR noise — reliability / red-team).
- **Guarded by default.** `app.py` / `main.py` run the full secure flow:
  `ask()` = input guardrail → semantic cache → guarded-tool agent → output
  guardrail. The plain pipeline stays only as the red-team baseline
  (`build_plain_assistant` / `ask_plain`).
- Pipeline function signatures and their callers: in the `hr-assistant-dev`
  skill. Keep every call site in sync.

## Entry points

| Script | Pipeline | What it does |
|---|---|---|
| `main.py` | secure | CLI demo |
| `app.py` | secure | Streamlit UI (Google OAuth when configured) |
| `ingest.py` | — | build both Qdrant collections (idempotent) |
| `evaluate.py` | guarded tool, no Model Armor | LangSmith correctness + groundedness |
| `demo_reliability.py` | secure | guarded-pipeline walkthrough |
| `redteam_test.py` | plain + secure | 7 attacks against both pipelines |

## Hooks in this repo (`.claude/settings.json`)

- **PreToolUse** — blocks writes to `.env`.
- **PostToolUse** — byte-compiles a just-edited `.py` file (syntax check).
- **Stop** — whole-repo `compileall` + stale-reference sweep.

All are compile-only; none execute the app.
