"""Connect to the LLM. Calls Vertex AI Gemini directly by default. If
LLM_GATEWAY_URL is set (see config.py), routes through the LiteLLM gateway
instead — same model, same answers, just through a service that adds
logging and a fallback model. Leave LLM_GATEWAY_URL unset and this behaves
exactly as before.

Gateway auth is a Google-signed ID token (what Cloud Run's IAM layer
checks), not an API key. Google ID tokens expire after ~1 hour, so instead
of minting one at build time and freezing it, the token is cached with a
shorter TTL and re-minted on demand by an httpx request hook — every call
to the gateway carries a current token, even in a session left open for
hours. Minting is cheap on Cloud Run: the metadata server answers in
milliseconds and refreshes the underlying token itself.
"""

import threading
import time

import google.auth.transport.requests
import google.oauth2.id_token
import httpx

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from hr_assistant import config

# Re-mint comfortably before the ~1 hour Google expiry.
_TOKEN_TTL_SECONDS = 50 * 60
_token_cache: dict = {"value": None, "minted_at": 0.0}
_token_lock = threading.Lock()


def _gateway_id_token() -> str:
    """A Google-signed ID token scoped to the gateway's URL, cached for
    _TOKEN_TTL_SECONDS and re-minted after that. Thread-safe — Streamlit
    and the agent runtime can both reach this."""
    now = time.monotonic()
    with _token_lock:
        cached = _token_cache["value"]
        if cached is None or now - _token_cache["minted_at"] > _TOKEN_TTL_SECONDS:
            audience = config.LLM_GATEWAY_URL.removesuffix("/v1")
            request = google.auth.transport.requests.Request()
            _token_cache["value"] = google.oauth2.id_token.fetch_id_token(request, audience)
            _token_cache["minted_at"] = now
        return _token_cache["value"]


def _attach_fresh_token(request: httpx.Request) -> None:
    """httpx request hook (sync client) — put a current token on every
    outgoing gateway call, replacing the placeholder the OpenAI client
    writes from api_key."""
    request.headers["Authorization"] = f"Bearer {_gateway_id_token()}"


async def _attach_fresh_token_async(request: httpx.Request) -> None:
    """Same, for the async client. The token fetch is a fast, infrequent
    (cached ~50 min) metadata-server call, so doing it inline here is fine."""
    request.headers["Authorization"] = f"Bearer {_gateway_id_token()}"


# One httpx client pair for the whole process, shared by every get_llm()
# call (the guardrail's gemini_lite path calls get_llm() per check). httpx
# clients hold a connection pool; making a fresh pair each call leaks
# sockets. langchain-openai requires both sync and async to be given together.
_http_client: "httpx.Client | None" = None
_http_async_client: "httpx.AsyncClient | None" = None


def _gateway_http_clients() -> "tuple[httpx.Client, httpx.AsyncClient]":
    global _http_client, _http_async_client
    if _http_client is None:
        _http_client = httpx.Client(event_hooks={"request": [_attach_fresh_token]})
        _http_async_client = httpx.AsyncClient(event_hooks={"request": [_attach_fresh_token_async]})
    return _http_client, _http_async_client


def get_llm():
    if config.LLM_GATEWAY_URL:
        sync_client, async_client = _gateway_http_clients()
        return ChatOpenAI(
            model=config.LLM_MODEL_NAME,
            base_url=config.LLM_GATEWAY_URL,
            api_key="unused-token-is-set-per-request",  # real auth: the httpx hooks below
            temperature=0,
            http_client=sync_client,
            http_async_client=async_client,
        )

    return ChatGoogleGenerativeAI(
        model=config.LLM_MODEL_NAME,
        vertexai=True,
        project=config.PROJECT_ID,
        location=config.LOCATION,
        temperature=0,
    )
