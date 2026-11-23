#!/usr/bin/env python3
"""
Unit tests for ~/.claude/hooks/model-policy.py.

Feeds the hook PreToolUse payloads and checks which ones it blocks.

Run: python3 .claude/evals/model-policy/test_unit.py [HOOK_PATH]

HOOK_PATH defaults to the hook in this repo. Pass a deliberately broken copy to
confirm the tests catch the break.
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
    (
        "claude -p with a line continuation",
        "Bash",
        {"command": 'claude -p "Summarize the diff" \\\n  --model sonnet'},
        True,
    ),
    (
        "double-quoted prompt holding ;",
        "Bash",
        {"command": 'claude -p "Read a.md; then b.md" --model haiku'},
        True,
    ),
    (
        "single-quoted prompt holding |",
        "Bash",
        {"command": "claude -p 'Compare A | B' --model haiku"},
        True,
    ),
    (
        "prompt holding & and a newline",
        "Bash",
        {"command": 'claude -p "A & B\nC" --model haiku'},
        True,
    ),
    (
        "escaped quote inside a prompt",
        "Bash",
        {"command": 'claude -p "say \\"a; b\\"" --model haiku'},
        True,
    ),
    (
        "escaped quote outside quotes",
        "Bash",
        {"command": "claude -p it\\'s --model haiku"},
        True,
    ),
    ("quoted --model", "Bash", {"command": "claude '--model=sonnet' -p hi"}, True),
    (
        "timeout 60 claude",
        "Bash",
        {"command": "timeout 60 claude --model sonnet -p hi"},
        True,
    ),
    (
        "timeout with a flag and a fractional duration",
        "Bash",
        {"command": "timeout --foreground 1.5m claude --model sonnet -p hi"},
        True,
    ),
    ("time claude", "Bash", {"command": "time claude --model sonnet -p hi"}, True),
    (
        "nohup claude",
        "Bash",
        {"command": "nohup claude --model sonnet -p hi > out.txt 2>&1 &"},
        True,
    ),
    (
        "claude by path",
        "Bash",
        {"command": "~/.local/bin/claude --model sonnet -p hi"},
        True,
    ),
    (
        "claude by path with opus",
        "Bash",
        {"command": "~/.local/bin/claude --model opus -p hi"},
        False,
    ),
    (
        "assignment before claude",
        "Bash",
        {"command": "FOO=1 claude --model sonnet -p hi"},
        True,
    ),
    (
        "env -u before claude",
        "Bash",
        {"command": "env -u FOO claude --model sonnet -p hi"},
        True,
    ),
    (
        "command claude",
        "Bash",
        {"command": "command claude --model sonnet -p hi"},
        True,
    ),
    (
        "prompt that only mentions --model",
        "Bash",
        {"command": 'claude -p "never pass --model sonnet"'},
        False,
    ),
    (
        "quoted grep pattern",
        "Bash",
        {"command": "grep -rn 'claude --model sonnet' notes/"},
        False,
    ),
    (
        "quoted grep pattern with a launcher",
        "Bash",
        {"command": 'grep -rn "timeout 60 claude --model sonnet" notes/'},
        False,
    ),
    (
        "quoted grep pattern with a path",
        "Bash",
        {"command": "rg -n '~/.local/bin/claude --model haiku' notes/"},
        False,
    ),
    ("echo naming claude", "Bash", {"command": "echo claude --model sonnet"}, False),
    (
        "path segment that starts with claude",
        "Bash",
        {"command": "~/src/claude-tools/run.py --model sonnet"},
        False,
    ),
    (
        "numbered note line",
        "Bash",
        {"command": "cat >> notes.md <<'EOF'\n1. claude --model sonnet\nEOF"},
        False,
    ),
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
