# Dos and Don'ts — HR Policy Assistant

Quick rules. Full context: the `hr-assistant-dev` skill and `docs/`.

## Do

- Read a file completely before editing it.
- Put every setting in `hr_assistant/config.py`, sourced from `.env` —
  including model IDs (`LLM_MODEL_NAME` / `EMBEDDING_MODEL_NAME` /
  `RERANKER_MODEL_NAME`). Never hardcode a model string elsewhere.
- Use `logging` (INFO) for operational lines, `logger.warning` /
  `logger.exception` for errors; entry points call
  `hr_assistant.logging_config.configure_logging()`. `print()` is only for
  a script's own output.
- Keep ingestion separate — only `hr_assistant/ingestion.py` writes to Qdrant.
- Keep the plain pipeline working — `redteam_test.py` needs it as the
  before/after baseline.
- Update every `ask*()` call site together when a signature changes.
- Fail **CLOSED** on an input-guardrail error, **OPEN** on an
  output-guardrail error.
- Match the existing docstring / comment style (explain WHY).
- Update `docs/` + `summary.md` in the same pass as any behaviour change.
- Compile-check (`python -m compileall -q hr_assistant *.py`) after edits.
- Load `verify-pipeline-change` before saying a change is done.

## Don't

- Don't run `ingest.py` / `evaluate.py` / `redteam_test.py` /
  `demo_reliability.py` / `streamlit` — they hit real cloud and cost money.
  Wait for the user.
- Don't edit, print, or share `.env` (live secrets).
- Don't hardcode a key, URL, model name, or threshold outside `config.py`.
- Don't add a dependency for something already covered.
- Don't let a guardrail exception crash a request.
- Don't route the deployed app through the noisy collection — it uses the
  clean `hr_policies` collection with the guarded tool.
- Don't assume POSIX — Windows host, PowerShell shell.
- Don't delete files without a reason — it's a git repo (`origin/main`),
  but deletions still need to be deliberate.
