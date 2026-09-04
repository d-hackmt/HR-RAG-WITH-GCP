"""Connect to the LLM.

Every model call in the app goes through one place: get_llm(). It returns a
LangChain chat model backed by a LiteLLM *Router* (the litellm SDK, running
in-process — NOT a separate proxy service):

    primary   -> Vertex AI Gemini  (config.LLM_MODEL_NAME)
    fallback  -> Groq              (config.FALLBACK_MODEL_NAME), used only if
                                    the Vertex call errors after num_retries

The app always asks for one logical model ("hr-llm"); the Router decides
what actually serves it. Adding, swapping, or reordering backends is a
change here and in config.py — never in the calling code (agent.py,
guardrails.py).

Why the SDK and not a hosted proxy: with one app there's nothing a separate
gateway service buys that this doesn't — provider-agnostic calls and
automatic failover both live in the Router. It also removes an entire class
of deployment problem (a second Cloud Run service, its IAM binding, and
minting a Google ID token per request). Vertex auth is plain Application
Default Credentials, exactly as a direct Gemini call would use.
"""

import litellm
from langchain_litellm import ChatLiteLLMRouter
from litellm import Router

from hr_assistant import config

# Gemini accepts params (e.g. some tool/response-format options) that Groq's
# OpenAI-compatible endpoint rejects. Drop unsupported params on the way to
# whichever backend serves the call, rather than 400-ing on the fallback.
litellm.drop_params = True

_PRIMARY_GROUP = "hr-llm"
_FALLBACK_GROUP = "hr-llm-fallback"

# One Router for the whole process — it holds per-deployment state
# (cooldowns, retry counters). get_llm() is called per guardrail check and
# once per agent build, so a fresh Router each call would throw that away.
_router: "Router | None" = None


def _get_router() -> Router:
    global _router
    if _router is None:
        _router = Router(
            model_list=[
                {
                    "model_name": _PRIMARY_GROUP,
                    "litellm_params": {
                        "model": f"vertex_ai/{config.LLM_MODEL_NAME}",
                        "vertex_project": config.PROJECT_ID,
                        "vertex_location": config.LOCATION,
                    },
                },
                {
                    "model_name": _FALLBACK_GROUP,
                    "litellm_params": {
                        "model": f"groq/{config.FALLBACK_MODEL_NAME}",
                        "api_key": config.GROQ_API_KEY,
                    },
                },
            ],
            # Retry the primary a couple of times, THEN cross over to Groq.
            num_retries=2,
            fallbacks=[{_PRIMARY_GROUP: [_FALLBACK_GROUP]}],
        )
    return _router


def get_llm():
    """The app's chat model: Gemini primary, Groq fallback, one retry policy.

    A LangChain chat model (supports tool calling and structured output), so
    agent.py and guardrails.py use it unchanged. temperature=0 is set once
    here — the single source of truth for both backends."""
    return ChatLiteLLMRouter(router=_get_router(), model_name=_PRIMARY_GROUP, temperature=0)
