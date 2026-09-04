"""One place to turn on readable console logging.

The library modules (pipeline, guardrails, semantic_cache, ingestion,
processor) emit their operational lines — guardrail pass/block, cache
hit/miss, ingestion progress — through `logging` at INFO, not bare
print(). Errors go through logger.warning / logger.exception.

The CLI entry points call `configure_logging()` so those INFO lines show
on stdout. app.py (Streamlit) calls it too; the lines then land in the
server console / Cloud Run logs, which is where operational telemetry
belongs — not in the chat UI.

Bare print() is still used for a script's own *output* (the demo Q&A
display, red-team progress markers, "Ingestion complete") — that is not
logging.
"""

import logging
import os

_CONFIGURED = False


def configure_logging(level: "str | int | None" = None) -> None:
    """Attach a plain-message handler to the root logger, once per process.

    Level: the explicit arg, else $LOG_LEVEL, else INFO. Idempotent —
    safe to call from every entry point and from a Streamlit rerun.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=level or os.getenv("LOG_LEVEL", "INFO"),
        format="%(message)s",
    )
    # Streamlit configures the root logger before our code runs, so
    # basicConfig above is a no-op there; make sure our package's lines
    # still pass the level filter.
    logging.getLogger("hr_assistant").setLevel(level or os.getenv("LOG_LEVEL", "INFO"))
    _CONFIGURED = True
