# 16. Full Hosting Architecture

Every piece from docs 01–15 in one picture. Project
`rag-hr-assistant-demo`, region `us-central1`.

```mermaid
flowchart TD
    EMP["Employee's browser"]

    subgraph GCP["Google Cloud — rag-hr-assistant-demo"]
        subgraph CR1["Cloud Run: hr-rag-assistant (public)"]
            APP["Streamlit app<br/>+ Google login + allow-list<br/>+ Model Armor in/out + scope filter<br/>+ semantic cache + identity-lock prompt<br/>+ LiteLLM Router (Gemini → Groq)"]
        end
        VX["Vertex AI Gemini"]
        MA["Vertex AI Model Armor"]
        GCS["Cloud Storage<br/>(raw policy documents)"]
        SM["Secret Manager<br/>(streamlit-auth secret)"]
        IAM["IAM<br/>(least-privilege roles)"]
    end

    subgraph EXT["External (not GCP)"]
        QD["Qdrant Cloud<br/>(vector database)"]
        JI["Jina AI<br/>(embeddings + reranker)"]
        GO["Google OAuth<br/>(login screen)"]
        GRQ["Groq<br/>(fallback model)"]
    end

    EMP -->|"1. load the page"| APP
    APP -->|"2. redirect to log in"| GO
    GO -->|"3. verified identity"| APP
    APP -->|"4. screen the question (+ recent history)"| MA
    APP -->|"5. embed the question"| JI
    APP -->|"6. search for matching chunks"| QD
    APP -->|"7. re-rank the results"| JI
    APP -->|"8. ask the model (LiteLLM Router)"| VX
    APP -.->|"8b. fallback if Vertex errors"| GRQ
    APP -->|"9. screen the answer"| MA
    APP -.->|"read secrets at startup"| SM
    APP -.->|"read documents"| GCS
    IAM -.->|"governs every arrow"| APP
```

*Steps 4 and 9 (Model Armor) run before the semantic-cache lookup and
after generation respectively. On step 4 a flagged question stops here; a
cache hit after step 4 skips straight to the answer, past steps 5–8.*

## Reading the diagram

- **Solid arrows** — the live path for one question, in order.
- **Dashed arrows** — background/startup access.
- **`hr-rag-assistant`** is the only service — one Cloud Run deployment.
  Public at the network level, gated by Google login + the allow-list
  before anything works.
- **Model routing** (Gemini primary, Groq fallback) is the LiteLLM Router
  *inside* that service, not a separate deployment — see doc 14.
- **IAM** isn't a step — it's the permission checks running under every
  arrow.
- **Qdrant, Jina, and Groq are outside GCP** — a deliberate multi-vendor
  stack.

## The one service

| | `hr-rag-assistant` |
|---|---|
| Who can reach it | Anyone (network) — gated by app login |
| Ingress setting | `--allow-unauthenticated` |
| What enforces access | Google OAuth + `ALLOWED_EMPLOYEE_EMAILS` |
| Its guardrails | Model Armor in/out, scope filter, identity lock, semantic cache |
| Talks to Gemini | Directly (Vertex AI), via the in-process LiteLLM Router; Groq on fallback |

## Where each secret lives

| Secret | Lives in |
|---|---|
| OAuth client ID / secret / cookie key | Secret Manager, `streamlit-auth` |
| Qdrant + Jina + Groq API keys | Cloud Run env vars on `hr-rag-assistant` |

That's the whole system. See **[commands/commands.md](../commands/commands.md)** to build it,
and **[summary.md](../summary.md)** for the current status and known
limitations.
