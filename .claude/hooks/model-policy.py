#!/usr/bin/env python3
"""
PreToolUse hook: enforces @rules/models.md for model choices a session makes on
its own. `availableModels` in settings.json keeps sessions and subagents from
dropping below Opus, but it says nothing about Fable and
`claude --setting-sources ""` skips it, so this hook is the visible check on
top.

Blocks (exit 2) an `Agent` call, a workflow script or a `claude --model`
command that names:

- A model below Opus: Always.
- Fable: Unless the user approved it. The approved retry starts the prompt or
  command with `# user-approved:`, or holds `// user-approved:` in a workflow
  script, which has to begin with its `meta` export.

Also blocks an `Agent` call that names no model, since the subagent would
inherit the session's. A fork is exempt: it always runs on the session's model.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Before `claude`: assignments, launchers, and their flags and durations
# (`env -u NAME`, `timeout --foreground 1.5m`). Between `claude` and
# `--model`: quoted strings whole, so a prompt can hold `;`, `|` or `&`.
CLAUDE_MODEL_RE = re.compile(
    r"(?:^|[;&|(\n])\s*"
    r"(?:(?:\w+=\S*|-u\s+\w+|env|command|nohup|time|timeout|-[\w-]+"
    r"|\d+(?:\.\d+)?[smhd]?)\s+)*"
    r"(?:\S*/claude(?=\s)|claude\b)"
    r"(?:'[^']*'|\"(?:[^\"\\]|\\.)*\"|\\.|[^\n;&|'\"\\])*?"
    r"['\"]?--model[=\s]+['\"]?([\w.\-\[\]]+)"
)
SCRIPT_MODEL_RE = re.compile(r"\bmodel\s*:\s*['\"]([\w.\-\[\]]+)['\"]")


def requested(tool: str, tool_input: dict) -> tuple[list[str], bool]:
    """Return the models a tool call names and whether it carries approval."""
    if tool in ("Agent", "Task"):
        model = tool_input.get("model")
        prompt = str(tool_input.get("prompt", ""))
        approved = prompt.lstrip().startswith("# user-approved:")
        return ([model] if isinstance(model, str) else []), approved
    if tool == "Bash":
        command = str(tool_input.get("command", ""))
        approved = command.lstrip().startswith("# user-approved:")
        return CLAUDE_MODEL_RE.findall(command.replace("\\\n", " ")), approved
    if tool == "Workflow":
        script = str(tool_input.get("script", ""))
        path = tool_input.get("scriptPath")
        if path:
            try:
                script = Path(str(path)).expanduser().read_text(encoding="utf-8")
            except OSError:
                return [], False
        return SCRIPT_MODEL_RE.findall(script), "// user-approved:" in script
    return [], False


def unnamed(tool: str, tool_input: dict) -> bool:
    """Return whether an `Agent` call leaves its model to be inherited."""
    if tool not in ("Agent", "Task") or tool_input.get("subagent_type") == "fork":
        return False
    model = tool_input.get("model")
    return not (isinstance(model, str) and model.strip())


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}

    if unnamed(tool, tool_input):
        sys.stderr.write(
            "BLOCKED: This call names no model, so the subagent would inherit "
            "the session's. @rules/models.md has agents name one on every "
            '`Agent` call. Pass `model: "opus"`.\n'
        )
        return 2

    models, approved = requested(tool, tool_input)
    lowered = [m.lower() for m in models]

    below = [m for m in lowered if "sonnet" in m or "haiku" in m or m == "opusplan"]
    if below:
        sys.stderr.write(
            f"BLOCKED: {', '.join(below)} is below Opus, and @rules/models.md "
            "never allows that. Use `opus`.\n"
        )
        return 2

    if any("fable" in m for m in lowered) and not approved:
        sys.stderr.write(
            "BLOCKED: @rules/models.md keeps Fable for the user's own "
            "sessions. Use `opus`, or tell the user in one line why this "
            "needs Fable and wait for a yes. On the approved retry, start "
            "the prompt or command with `# user-approved:`.\n"
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
