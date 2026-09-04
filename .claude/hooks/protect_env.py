#!/usr/bin/env python3
"""PreToolUse hook: block edits/writes to .env.

.env holds real Jina / Qdrant / LangSmith / Groq credentials sitting in the
working tree (this is not a git repo -- there is no history to recover a
clobbered file from). Configuration changes belong in
hr_assistant/config.py (code defaults) and .env.example (documentation),
never in a machine-written edit to .env itself.

Contract:
  exit 2 + stderr  -> deny the tool call (target is .env)
  exit 0           -> allow (anything else, including any unexpected error,
                      so a hook bug can never wedge the session)
"""
import json
import os
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path") or ""
    if not path:
        return 0

    base = os.path.basename(path.replace("\\", "/"))
    if base == ".env":
        print(
            "[hook] refusing to modify .env -- it holds live secrets. "
            "Put code defaults in hr_assistant/config.py, document the "
            "variable in .env.example, and ask the user to edit .env.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
