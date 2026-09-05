# Commands — `security` branch, direct copy-paste

Everything from `commands-basic-rag.md` still applies (project, bucket,
`.env`, ingest). This is only what `security` adds on top: the safety
guardrail (Model Armor), the LiteLLM Gemini→Groq fallback, semantic cache,
evaluation, and red-team. Real values below, confirmed via `gcloud` just
now — not placeholders. Shell: Git Bash.

## Already true, confirmed today — nothing to do here

- `modelarmor.googleapis.com` is already enabled on `rag-hr-assistant-demo`.
- The Model Armor template **already exists**:
  `projects/rag-hr-assistant-demo/locations/us/templates/hr-assistant-guardrail`
  — nothing to create.
- `.env` already has `GUARDRAIL_PROVIDER=model_armor`, `MODEL_ARMOR_LOCATION=us`,
  `MODEL_ARMOR_TEMPLATE_ID=hr-assistant-guardrail`, `GROQ_API_KEY`,
  `LANGSMITH_API_KEY` (tracing on), `QDRANT_NOISY_COLLECTION_NAME` — all
  present and correctly set.
- `hrrenv` already has `google-cloud-modelarmor`, `numpy`, `pydantic`,
  `langchain-openai`, `openevals` installed.

## 1. Install the two packages `hrrenv` is missing

`litellm` and `langchain-litellm` are **not installed yet** — `llm.py` on
this branch needs them for the Gemini→Groq router:

```bash
source hrrenv/Scripts/activate
uv pip install -r requirements.txt
```

(Everything else in `requirements.txt` is already present; this just adds
the two missing packages.)

## 2. Ingest — same corpus, same bucket as `basic-rag`

Nothing new here — if you already ran `python ingest.py` on `basic-rag`,
both collections (`hr_policies`, `hr_policies_noisy_demo`) already exist
and this branch reuses them as-is.

```bash
python ingest.py          # only if you haven't already
```

## 3. Run it

```bash
python main.py                  # CLI — full secure pipeline (guardrails + scope filter + cache)
streamlit run app.py            # chat UI, http://localhost:8501 — sidebar shows the guardrail provider
python demo_reliability.py      # reliability walkthrough against the noisy corpus
langgraph dev                   # LangGraph Studio — the guarded agent, noisy collection
python -m hr_assistant.tracing  # confirm LangSmith tracing
```

## 4. Adversarial red-team pass

```bash
python redteam_test.py     # 7 attacks vs. plain baseline + the guarded pipeline -> results/redteam_results.json
```

## 5. Answer-quality evaluation

Needs `LANGSMITH_API_KEY` + `GROQ_API_KEY` — both already in `.env`.

```bash
python evaluate.py         # correctness + groundedness -> LangSmith 'hr-policy-qa' experiment
```

## If you ever need to (re)create the Model Armor template

Not needed now — it already exists — but for reference:

```bash
gcloud model-armor templates create hr-assistant-guardrail \
  --location=us \
  --project=rag-hr-assistant-demo \
  --pi-and-jailbreak-filter-settings-enforcement=enabled \
  --pi-and-jailbreak-filter-settings-confidence-level=high \
  --basic-config-filter-enforcement=enabled \
  --rai-settings-filters=confidenceLevel=high,filterType=HATE_SPEECH \
  --rai-settings-filters=confidenceLevel=high,filterType=HARASSMENT \
  --rai-settings-filters=confidenceLevel=high,filterType=DANGEROUS \
  --rai-settings-filters=confidenceLevel=high,filterType=SEXUALLY_EXPLICIT \
  --malicious-uri-filter-settings-enforcement=enabled
```

## Cost note

Same as `basic-rag`, plus: Model Armor screens 2 calls/request (input +
output) at Gemini-Flash-adjacent pricing; Groq's free tier covers the
fallback + eval judge at this volume; LangSmith's free tier covers tracing
+ the 18-case eval dataset easily.
