#!/usr/bin/env python3
"""
PreToolUse hook: backstop for genuinely risky Bash commands. The system
prompt asks the model to seek confirmation before destructive actions,
but model judgment is fallible. This hook is the deterministic floor.

Blocks (exit 2) when the command matches any pattern below, with a
message that tells the model what to do: pause, surface the command to
the user verbatim, and only retry after explicit approval.

Patterns are intentionally narrow. `git push --force-with-lease` is
allowed; `git push --force` is not. `gh pr merge --merge --auto` (the
"queue and let CI gate" flow) is allowed; bare `gh pr merge` is not.

Allowlist: when the input command starts with `# user-approved:` (a
literal comment), the hook lets it through. The model uses this prefix
on the retry after the user has explicitly approved the action.

Text-passing carve-out: `git commit -m "..."`, `gh pr create --body
"..."`, and similar commands often embed risky-pattern literals in
the message body (changelog entries, PR descriptions). Heredoc bodies
and `--body`/`-m` flag values are stripped from the command before
pattern matching, but only when the outer command is a known text
tool. Interpreter heredocs (`bash <<EOF ... EOF`) are left intact so
their contents are still scanned.
"""

from __future__ import annotations

import json
import re
import sys

HEREDOC_RE = re.compile(
    r"<<[-]?\s*['\"]?(\w+)['\"]?\s*\n(.*?)\n\s*\1\b",
    re.DOTALL,
)
FLAG_VALUE_RE = re.compile(
    r"(?:^|\s)(--?)(m|message|body|title|body-file)[=\s]+"
    r"(\"((?:[^\"\\]|\\.)*)\"|'((?:[^'\\]|\\.)*)')",
)
TEXT_PASSING_RE = re.compile(
    r"\b(git\s+commit|gh\s+(pr|issue)\s+(create|edit|comment))\b"
)


def strip_text_payloads(cmd: str) -> str:
    """
    Strip heredoc bodies and `-m` / `--body` flag values from text-passing
    commands so risky-pattern literals embedded in commit messages or PR
    bodies do not trip the hook. Only applied when the outer command is
    `git commit`, `gh pr ...`, or `gh issue ...`; interpreter heredocs
    like `bash <<EOF ... EOF` are left intact.
    """
    if not TEXT_PASSING_RE.search(cmd):
        return cmd
    cmd = HEREDOC_RE.sub("", cmd)
    cmd = FLAG_VALUE_RE.sub("", cmd)
    return cmd


RISKY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\bgit\s+push\s+(?:[^\n]*\s)?(?:--force|-f)\b(?!-with-lease)"),
        "git force-push without --force-with-lease",
    ),
    (
        re.compile(r"\bgh\s+pr\s+merge\b(?![^\n]*--auto\b)"),
        "gh pr merge without --auto",
    ),
    (re.compile(r"\bgh\s+(?:repo|pr|issue)\s+delete\b"), "gh delete"),
    (re.compile(r"\bkubectl\s+delete\b"), "kubectl delete"),
    (
        re.compile(r"\bterraform\s+(?:apply|destroy)\b[^\n]*--auto-approve"),
        "terraform apply/destroy with --auto-approve",
    ),
    (re.compile(r"\bterraform\s+destroy\b"), "terraform destroy"),
    (
        re.compile(
            r"\bgcloud\s+(?:sql\s+instances|run\s+services|projects|"
            r"compute\s+instances)\s+delete\b"
        ),
        "gcloud resource delete",
    ),
    (
        re.compile(r"\brm\s+-[rRfF]+[^\n]*\s(?:/|~|\$HOME|\$\{HOME\})(?:\s|$)"),
        "rm -rf against / or $HOME",
    ),
    (re.compile(r"\bdropdb\b"), "dropdb"),
    (re.compile(r"\bDROP\s+(?:TABLE|DATABASE|SCHEMA)\b", re.IGNORECASE), "SQL DROP"),
]

ALLOWLIST_PREFIX = "# user-approved:"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    if payload.get("tool_name") != "Bash":
        return 0

    cmd = (payload.get("tool_input") or {}).get("command", "")
    if not isinstance(cmd, str) or not cmd:
        return 0

    if cmd.lstrip().startswith(ALLOWLIST_PREFIX):
        return 0

    scan_target = strip_text_payloads(cmd)

    matches: list[str] = []
    for pattern, label in RISKY_PATTERNS:
        if pattern.search(scan_target):
            matches.append(label)

    if not matches:
        return 0

    sys.stderr.write(
        "BLOCKED: risky command detected. Pattern(s): "
        + ", ".join(matches)
        + "\n\nSurface the exact command to the user verbatim and ask "
        "for explicit approval before retrying. On the retry, prefix the "
        "command with `" + ALLOWLIST_PREFIX + " ` to indicate the user "
        "has approved it.\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
