#!/usr/bin/env python3
"""Stop hook: whole-repo compile check + stale-reference sweep.

Runs when Claude finishes a turn. This is the "does it all still compile"
pass the user asked for. compileall byte-compiles source and never executes
it -- no imports run, no cloud calls, no side effects.

Contract:
  exit 2 (once)  -> compilation failed; Claude fixes it before ending the
                    turn. Guarded by stop_hook_active so it cannot loop.
  exit 0         -> compiles clean. Stale-reference hits are printed as
                    advisory notes only and never block.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

# (regex, why it is worth a look) -- advisory only, never blocks.
STALE_PATTERNS = [
    (r"TODO\(", "unfinished tracked TODO left in the tree"),
    (r"\b(guardrails|semantic_cache|thread_memory|check_input|check_output|ChatLiteLLMRouter|create_guarded_search_tool)\b",
     "reference to a security-branch concept that shouldn't be on basic-rag"),
]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    if payload.get("stop_hook_active"):
        return 0

    root = Path(payload.get("cwd") or ".")
    pkg = root / "hr_assistant"
    targets = [str(pkg)] + [str(p) for p in root.glob("*.py")]

    try:
        result = subprocess.run(
            [sys.executable, "-m", "compileall", "-q", *targets],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except Exception as exc:
        print(f"[hook] could not run compile check: {exc}")
        return 0

    if result.returncode != 0:
        print(
            "[hook] compile check FAILED:\n"
            + (result.stdout or "")
            + (result.stderr or ""),
            file=sys.stderr,
        )
        return 2

    notes = []
    py_files = list(pkg.glob("*.py")) + list(root.glob("*.py"))
    for py in py_files:
        try:
            text = py.read_text(encoding="utf-8")
        except Exception:
            continue
        for rx, why in STALE_PATTERNS:
            if re.search(rx, text):
                notes.append(f"  {py.name}: {why}")

    if notes:
        print("[hook] compile check OK. Advisory (not blocking):\n" + "\n".join(notes))
    else:
        print("[hook] compile check OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
