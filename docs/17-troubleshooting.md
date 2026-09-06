# 17. Troubleshooting

Every error actually hit while building and deploying this project, in
plain words: what you see, why it happens, how to fix it.

## Quick index

| Symptom | Section |
|---|---|
| `Error 400: redirect_uri_mismatch` on the Google sign-in page | [1](#1-error-400-redirect_uri_mismatch) |
| Login succeeds but you land back on the login screen (a loop) | [2](#2-login-loop) |
| `Access blocked: this app's request is invalid` | [3](#3-access-blocked-this-apps-request-is-invalid) |
| First Cloud Run deploy crashes: `Could not load model Qdrant/bm25` | [4](#4-could-not-load-model-qdrantbm25) |
| Every question is refused / "flagged by the input safety guardrail" | [5](#5-everything-is-blocked-by-the-input-guardrail) |
| `RuntimeError: Qdrant collection '…' is missing or empty` | [6](#6-qdrant-collection-missing-or-empty) |
| `langgraph dev` errors about a checkpointer already being set | [7](#7-langgraph-dev-checkpointer-conflict) |
| `gcloud run deploy` splits `ALLOWED_EMPLOYEE_EMAILS` wrongly | [8](#8-gcloud-mangles-the-employee-email-list) |
| Console change to the OAuth client "didn't take" | [9](#9-oauth-changes-take-time-to-propagate) |

---

## 1. `Error 400: redirect_uri_mismatch`

**You see:** Google's sign-in page shows *"Access blocked: this app's
request is invalid"* and, under "error details",
`Error 400: redirect_uri_mismatch`. It names a `redirect_uri=...` value.

**Why:** the `redirect_uri` your app sent to Google is not in the
**Authorized redirect URIs** list on the OAuth client. Google compares the
two strings **exactly** — one different character is a mismatch.

**Fix:**

1. On the error page, click **error details** — it shows the exact URI the
   app sent. That's ground truth.
2. Console → **APIs & Services → Credentials** → open the OAuth client
   whose **Client ID matches the one in your `secrets.toml`** (if you made
   two clients, it's easy to edit the wrong one).
3. Under **Authorized redirect URIs** (not "Authorized JavaScript origins"
   — a different box on the same page), the exact string from step 1 must
   be present.
4. Common differences to check:

| Wrong | Right |
|---|---|
| `https://…run.app` (bare) | `https://…run.app/oauth2callback` |
| `https://…run.app/oauth2callback/` (trailing slash) | `https://…run.app/oauth2callback` |
| `http://…` | `https://…` (Cloud Run is always https) |
| `http://localhost:8502/…` (wrong port) | the port Streamlit actually started on |
| pasted in "Authorized JavaScript origins" | must be in "Authorized redirect URIs" |

5. Click the blue **Save** button. Wait ~2–5 min (see §9), retry in a fresh
   incognito window.

---

## 2. Login loop

**You see:** you click "Log in with Google", pick your account, approve —
and land right back on the "Please log in with your company Google
account" screen. No error.

**Why:** Streamlit's login callback handler only listens at the path
`/oauth2callback`. If `redirect_uri` in `secrets.toml` is the **bare app
URL** with no path, Google sends the auth code back to `/`, Streamlit never
processes it, and you're still logged out.

Cloud Run logs show it clearly — the redirect lands on `/?state=...`
instead of `/oauth2callback`:
```
GET 302  …/auth…                          (off to Google)
GET 200  …run.app/?state=…                (back to ROOT, not /oauth2callback)
```

**Fix:** `redirect_uri` must end in `/oauth2callback`, in **both** places:

```toml
# .streamlit/secrets.toml
redirect_uri = "https://hr-rag-assistant-564821241199.us-central1.run.app/oauth2callback"
```

and the same string under the OAuth client's **Authorized redirect URIs**.
Then:

```bash
gcloud secrets versions add streamlit-auth --data-file=.streamlit/secrets.toml --project=rag-hr-assistant-demo
gcloud run deploy hr-rag-assistant --source . --project=rag-hr-assistant-demo --region=us-central1 \
  --allow-unauthenticated \
  --set-secrets=/app/.streamlit/secrets.toml=streamlit-auth:latest \
  --env-vars-file=deploy.env.yaml
```

A `secrets.toml` change needs both a **new secret version** *and* a
**redeploy** — the running revision keeps the version it was deployed with.

---

## 3. `Access blocked: this app's request is invalid`

**You see:** this message *before* you even get to pick an account.

**Why:** usually the same root cause as §1 (`redirect_uri_mismatch`) — the
sub-line under "error details" says which. Occasionally it's the OAuth
consent screen being misconfigured (no support email, no user type set).

**Fix:** check the error detail line first (§1). If it's not
`redirect_uri_mismatch`, go to Console → **Google Auth Platform →
Branding** and make sure App name, User support email, and Developer
contact email are all filled, and **Audience** is set to **External** with
your email under **Test users**.

---

## 4. `Could not load model Qdrant/bm25`

**You see:** the image builds fine, but the container crashes on startup
with `ValueError: Could not load model Qdrant/bm25 from any source.`

**Why:** hybrid search needs a small BM25 model file. `fastembed`
downloads it from HuggingFace *the first time it's used* — which on Cloud
Run is **every cold start**, because containers keep no disk between runs.
HuggingFace rate-limits Cloud Run's shared outbound IP (`429`) before the
download finishes.

**Fix (already in the `Dockerfile`):** download it at *build* time so it's
baked into the image:

```dockerfile
RUN python -c "from fastembed import SparseTextEmbedding; SparseTextEmbedding(model_name='Qdrant/bm25')"
```

If you hit this, your `Dockerfile` is missing that line — add it and
redeploy. See doc 12.

---

## 5. Everything is blocked by the input guardrail

**You see:** every question — even "how many leave days?" — comes back as
*"I can't process that request — it was flagged by the input safety
guardrail."* Logs show `INPUT GUARDRAIL: block (guardrail provider error —
failing closed …)`.

**Why:** `GUARDRAIL_PROVIDER=model_armor` but the Model Armor call is
*erroring* (not "flagging") — the template doesn't exist, the API isn't
enabled, or the service account lacks `roles/modelarmor.user`. On a
provider **error**, the input check **fails closed** (refuses) on purpose —
an unscreened prompt must never reach the model.

**Fix:** one of —

| Situation | Do this |
|---|---|
| Local dev, no Model Armor set up | `GUARDRAIL_PROVIDER=gemini_lite` in `.env` (one Gemini classify call, no GCP setup) — or `none` to disable |
| Deployed, template missing | create it: `commands-security.md` step 2 |
| Deployed, API off | `gcloud services enable modelarmor.googleapis.com` |
| Deployed, permission denied | `gcloud projects add-iam-policy-binding … --role=roles/modelarmor.user` for `$COMPUTE_SA` |

Check the full error in the logs — it names which of these it is.
(**Output**-side guardrail errors fail **open** instead — a transient error
shouldn't throw away a valid answer. See doc 15.)

---

## 6. Qdrant collection missing or empty

**You see:** `RuntimeError: Qdrant collection 'hr_policies' is missing or
empty. Run \`python ingest.py\` once to ingest the corpus.`

**Why:** the pipeline connects to a collection that ingestion never built
(or that was cleared).

**Fix:**

```bash
python ingest.py                 # builds both collections
python ingest.py --force         # rebuild from scratch
```

`app.py` / `main.py` try to bootstrap ingestion automatically on first run,
but that only works if the GCS bucket and API keys are set. On Cloud Run,
run `ingest.py` (or `docker compose run --rm ingest`) **before** the first
user hits the app, or that first request takes minutes.

---

## 7. `langgraph dev` checkpointer conflict

**You see:** `langgraph dev` fails to load the graph with an error about a
checkpointer already being set / not being overridable.

**Why:** `langgraph dev` (LangGraph Studio) supplies its **own**
persistence layer and rejects a compiled graph that already has an
`InMemorySaver` baked in.

**Fix (already done on `security` / `deployment` / `main`):**
`hr_assistant/studio_graph.py` builds the agent with `checkpointer=False`,
which `pipeline._resolve_checkpointer` turns into "no checkpointer at all".
If you're on an older checkout where `studio_graph.py` calls a builder
with no argument, update it to pass `checkpointer=False`.

---

## 8. gcloud mangles the employee email list

**You see:** after deploy, `ALLOWED_EMPLOYEE_EMAILS` on the service is
truncated or split into several bogus env vars.

**Why:** `--set-env-vars` uses `,` as its delimiter, and email lists
contain commas.

**Fix:** use `--env-vars-file=deploy.env.yaml` (recommended — YAML values
don't have this problem). If you must use `--set-env-vars`, change the
delimiter with a `^;^` prefix:

```bash
--set-env-vars '^;^ALLOWED_EMPLOYEE_EMAILS=a@x.com,b@x.com;OTHER_VAR=value'
```

---

## 9. OAuth changes take time to propagate

**You see:** you fixed the redirect URI / added a test user / changed the
consent screen, but the old behavior persists.

**Why:** Google caches OAuth client config. The Console itself says *"It may
take 5 minutes to a few hours for settings to take effect."* In practice
it's usually 1–5 minutes.

**Fix:** wait, then retry in a **fresh incognito window** (so a stale
cookie or cached OAuth state on your side isn't the real problem). If it's
still failing after ~15 minutes, it's not propagation — recheck §1 for an
actual string mismatch.

---

Next: back to **[README](../README.md)** · full command list in
**[commands.md](../commands.md)**.
