#!/usr/bin/env python3
"""PostToolUse hook: byte-compile a just-edited .py file.

Runs after Edit/Write/MultiEdit. This does NOT import or execute the module
-- py_compile only parses and compiles source to bytecode -- so it is safe
under this project's "never run anything" rule. It catches syntax errors,
bad indentation, and stray tokens the moment an edit introduces them.

Contract:
  exit 2 + stderr  -> a real SyntaxError; Claude sees it and fixes the file
  exit 0 (silent)  -> anything else: non-Python file, missing path, or an
                      internal hook error (a broken hook must never block
                      real work)
"""
import json
import py_compile
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path") or ""
    if not path or not path.endswith(".py"):
        return 0

    try:
        py_compile.compile(path, doraise=True)
    except py_compile.PyCompileError as exc:
        print(f"[hook] syntax check FAILED for {path}:\n{exc}", file=sys.stderr)
        return 2
    except FileNotFoundError:
        return 0
    except Exception:
        # Never let the hook itself break the workflow.
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
