# HR Policy Assistant — project guide for Claude

**Branch: `basic-rag` (stage 1 of 3).** A plain RAG agent — ingestion,
hybrid search, re-ranking, an agent with memory, CLI + Streamlit + LangGraph
Studio. Model is Vertex AI Gemini, called directly. NO guardrails, NO
evaluation, NO deployment on this branch — `security` and `deployment` add
those. Full docs: `docs/01`–`docs/16` (09–16 describe later stages).

## Before you touch the code

Load the **`hr-assistant-dev`** skill (architecture, the pipeline contract,
house style). After a change, load **`verify-pipeline-change`**. Short rules:
`.claude/DOS-AND-DONTS.md`.

## Hard rules

- **Git repo, pushed to GitHub** (`origin/basic-rag`). Still read before you
  edit; don't delete without reason.
- **`.env` = live secrets.** Never edit / print / share it. Defaults go in
  `config.py`; new variables get documented in `.env.example`.
- **Config only from `.env`** through `hr_assistant/config.py` (values) /
  `prompts.py` (instruction text).
- **Never run** `ingest.py` or `streamlit run app.py` unprompted — real
  cloud, real cost. Compile checks (`python -m compileall`) are fine.
- **`requirements.txt` is unpinned** — don't add dependencies casually.
- Windows host; PowerShell shell.

## Shape of the system

- **Files are numbered.** Every module's docstring starts `NN · name — …`;
  read `hr_assistant/` in that order (config 01 → pipeline 14 → entry
  scripts 16–19). Keep files small and single-purpose; split + renumber if
  one grows two jobs.
- **Ingestion is separate.** `ingest.py` → `hr_assistant/ingestion.py` (09)
  is the only writer to Qdrant. It builds **two** collections — `hr_policies`
  (clean) and `hr_policies_noisy_demo` (HR + non-HR noise). Everything else
  connects to what it built.
- **One pipeline.** `app.py` / `main.py` call `build_hr_assistant()` →
  `agent`, then `ask(agent, question, thread_id=...)`:
  agent → `search_hr_policy` tool (retrieve 08 → re-rank 10 → cited chunks)
  → Gemini answers → text.
- The app connects to the **clean** `hr_policies` collection. The noisy one
  is built now but exercised in the `security` branch.

## Pipeline contract (`hr_assistant/pipeline.py`, 14)

| Function | Returns | Used by |
|---|---|---|
| `build_hr_assistant()` | `agent` | `app.py`, `main.py`, `studio_graph.py` |
| `ask(agent, question, thread_id="default-session")` | `str` | `app.py`, `main.py` |

Change the `ask` signature and you must update every call site.

## Entry points

| Script | What it does |
|---|---|
| `main.py` (17) | CLI demo |
| `app.py` (18) | Streamlit UI (no auth on this branch) |
| `ingest.py` (16) | build both Qdrant collections (idempotent) |
| `hr_assistant/studio_graph.py` (19) | LangGraph Studio entry (`langgraph dev`) |

## Hooks in this repo (`.claude/settings.json`)

- **PreToolUse** — blocks writes to `.env`.
- **PostToolUse** — byte-compiles a just-edited `.py` file.
- **Stop** — whole-repo `compileall` + stale-reference sweep.

All are compile-only; none execute the app.
