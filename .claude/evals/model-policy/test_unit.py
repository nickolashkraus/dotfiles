#!/usr/bin/env python3
"""
Unit tests for ~/.claude/hooks/model-policy.py.

Feeds the hook PreToolUse payloads and checks which ones it blocks.

Run: python3 .claude/evals/model-policy/test_unit.py [HOOK_PATH]

HOOK_PATH defaults to the hook in this repo. Pass a deliberately broken
copy to confirm the tests catch the break.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK_PATH = (
    Path(sys.argv[1])
    if len(sys.argv) > 1
    else Path(__file__).resolve().parents[2] / "hooks" / "model-policy.py"
)
APPROVED = "# user-approved: "
WORKFLOW = "export const meta = {name: 'x'}\nawait agent('x', {model: '%s'})\n"

_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  [PASS] {name}")
    else:
        _failures.append(f"{name}: {detail}")
        print(f"  [FAIL] {name}  {detail}")


def run_hook(tool: str, tool_input: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps({"tool_name": tool, "tool_input": tool_input}),
        capture_output=True,
        text=True,
        check=False,
    )


CASES = [
    ("Agent with opus", "Agent", {"model": "opus", "prompt": "x"}, False),
    ("Agent with no model", "Agent", {"prompt": "x"}, True),
    ("Agent with an empty model", "Agent", {"model": "", "prompt": "x"}, True),
    (
        "Agent with no model and approval",
        "Agent",
        {"prompt": APPROVED + "x"},
        True,
    ),
    ("Task with no model", "Task", {"prompt": "x"}, True),
    ("fork with no model", "Agent", {"subagent_type": "fork", "prompt": "x"}, False),
    ("Agent with sonnet", "Agent", {"model": "sonnet", "prompt": "x"}, True),
    ("Agent with haiku", "Agent", {"model": "haiku", "prompt": "x"}, True),
    (
        "Agent with sonnet and approval",
        "Agent",
        {"model": "sonnet", "prompt": APPROVED + "x"},
        True,
    ),
    ("Agent with fable", "Agent", {"model": "fable", "prompt": "x"}, True),
    (
        "Agent with approved fable",
        "Agent",
        {"model": "fable", "prompt": APPROVED + "x"},
        False,
    ),
    ("claude --model opus", "Bash", {"command": "claude --model opus -p hi"}, False),
    ("claude --model sonnet", "Bash", {"command": "claude --model sonnet -p hi"}, True),
    (
        "claude --model=haiku after cd",
        "Bash",
        {"command": "cd /tmp && claude --model=haiku -p hi"},
        True,
    ),
    ("claude --model fable", "Bash", {"command": "claude --model fable -p hi"}, True),
    (
        "approved claude --model fable",
        "Bash",
        {"command": APPROVED + "\nclaude --model fable -p hi"},
        False,
    ),
    ("unrelated command", "Bash", {"command": "ls -la"}, False),
    ("workflow with opus", "Workflow", {"script": WORKFLOW % "opus"}, False),
    ("workflow with sonnet", "Workflow", {"script": WORKFLOW % "sonnet"}, True),
    ("workflow with fable", "Workflow", {"script": WORKFLOW % "fable"}, True),
    (
        "approved workflow with fable",
        "Workflow",
        {"script": "// user-approved: yes\n" + WORKFLOW % "fable"},
        False,
    ),
    ("another tool", "Read", {"file_path": "/tmp/x"}, False),
]


def main() -> int:
    for name, tool, tool_input, expect in CASES:
        r = run_hook(tool, tool_input)
        check(
            name,
            (r.returncode == 2) == expect,
            f"exit {r.returncode}: {r.stderr.strip()[:200]}",
        )

    r = run_hook("Agent", {"prompt": "x"})
    check("no-model message names opus", '`model: "opus"`' in r.stderr, r.stderr[:200])

    r = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="not json",
        capture_output=True,
        text=True,
        check=False,
    )
    check("unreadable payload passes", r.returncode == 0, r.stderr[:200])

    print(f"\n{len(_failures)} failure(s)")
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())
