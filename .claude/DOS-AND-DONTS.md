# Dos and Don'ts — HR Policy Assistant (`basic-rag` branch)

Quick rules. Full context: the `hr-assistant-dev` skill and `docs/`.

## Do

- Read a file completely before editing it.
- Module docstring's first line is `NN · name — purpose`. Keep files small
  and single-purpose; split + renumber if one grows two jobs.
- Put every setting in `hr_assistant/config.py` (values) or `prompts.py`
  (instruction text), sourced from `.env`. Never hardcode a model string.
- Use `logging` (INFO) for operational lines, `logger.warning` /
  `logger.exception` for errors; entry points call
  `hr_assistant.logging_config.configure_logging()`. `print()` is only for
  a script's own output.
- Keep ingestion separate — only `hr_assistant/ingestion.py` writes to Qdrant.
- Update every `ask()` call site together when the signature changes.
- Match the existing docstring / comment style (explain WHY).
- Update `docs/` in the same pass as any behaviour change.
- Compile-check (`python -m compileall -q hr_assistant *.py`) after edits.
- Load `verify-pipeline-change` before saying a change is done.

## Don't

- Don't run `ingest.py` / `streamlit` — they hit real cloud and cost money.
  Wait for the user.
- Don't edit, print, or share `.env` (live secrets).
- Don't hardcode a key, URL, model name, or threshold outside `config.py`.
- Don't add a dependency for something already covered.
- Don't assume POSIX — Windows host, PowerShell shell.
- Don't delete files without a reason — it's a git repo, but deletions
  still need to be deliberate.
- Don't pull `security` / `deployment` concepts (guardrails, Model Armor,
  semantic cache, LLM fallback, OAuth, Docker) back into this branch.
