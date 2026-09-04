"""LangSmith tracing — turn it on, and a quick check that it's working.

LangSmith needs no wiring in our own code: LangChain / LangGraph read
LANGSMITH_TRACING / LANGSMITH_ENDPOINT / LANGSMITH_API_KEY /
LANGSMITH_PROJECT straight from the environment (loaded from .env by
config.py) and, when tracing is on, automatically send a trace of every
LLM call, tool call, and agent step to your LangSmith project.

This module does two things:

1. `enable_tracing()` — makes sure the env vars LangChain looks for are
   actually set in os.environ for this process (config.py loads .env, but
   LangChain reads os.environ directly, and the names have to match
   exactly).
2. `check_langsmith_tracing()` — verifies the API key + endpoint + project
   are reachable, and fires one real traced run so you can confirm it
   landed by opening the project in LangSmith. Safe to call anywhere;
   never raises.
"""

import os

from hr_assistant import config


def _tracing_on() -> bool:
    return str(config.LANGSMITH_TRACING).lower() == "true"


def enable_tracing() -> None:
    """Push the LANGSMITH_* values from config into os.environ so LangChain
    picks them up. Idempotent.

    LANGSMITH_TRACING is a string ("true"/"false"), and "false" is truthy —
    so it's normalised through _tracing_on() rather than passed through raw.
    """
    os.environ["LANGSMITH_TRACING"] = "true" if _tracing_on() else "false"
    if config.LANGSMITH_ENDPOINT:
        os.environ["LANGSMITH_ENDPOINT"] = config.LANGSMITH_ENDPOINT
    if config.LANGSMITH_API_KEY:
        os.environ["LANGSMITH_API_KEY"] = config.LANGSMITH_API_KEY
    if config.LANGSMITH_PROJECT:
        os.environ["LANGSMITH_PROJECT"] = config.LANGSMITH_PROJECT


def check_langsmith_tracing() -> tuple[bool, str]:
    """Return (ok, human-readable message).

    ok=True  -> tracing is on, credentials work, and a test run was sent.
    ok=False -> tracing is off, misconfigured, or LangSmith was unreachable.
    Never raises — the caller can show the message and carry on.
    """
    if not _tracing_on():
        return False, "LangSmith tracing is OFF (set LANGSMITH_TRACING=true in .env)."

    if not config.LANGSMITH_API_KEY:
        return False, "LANGSMITH_TRACING=true but LANGSMITH_API_KEY is missing."

    enable_tracing()

    try:
        from langsmith import Client, traceable

        client = Client(api_key=config.LANGSMITH_API_KEY, api_url=config.LANGSMITH_ENDPOINT)

        # Cheap authenticated call — fails fast on a bad key / wrong endpoint.
        next(iter(client.list_projects(limit=1)), None)

        # Fire one real traced run so it's visibly confirmable in the UI.
        @traceable(name="langsmith_connectivity_check", project_name=config.LANGSMITH_PROJECT)
        def _ping() -> str:
            return "HR Policy Assistant tracing check — OK"

        _ping()
        try:
            client.flush()  # best-effort; not all SDK versions have it
        except Exception:
            pass

        return True, (
            f"LangSmith tracing ON — project '{config.LANGSMITH_PROJECT}'. "
            f"A 'langsmith_connectivity_check' run was just sent; open the project to confirm."
        )
    except Exception as exc:  # noqa: BLE001 — this is a health check, report anything
        return False, f"LangSmith tracing is enabled but the connectivity check failed: {exc}"


if __name__ == "__main__":
    ok, message = check_langsmith_tracing()
    print(("[OK] " if ok else "[!!] ") + message)
