#!/usr/bin/env python3
"""
PreToolUse hook: lints content destined for external platforms (Linear,
Notion, Slack, Gmail, GitHub, Git) against ~/.claude/rules/typography.md.

Reads the Claude Code hook payload on stdin, extracts text fields from the
tool input, scans for typography violations, and exits with code 2 (blocking
the tool call) when any are found. Stderr is shown to Claude so it can fix
the content and retry.

Skips content inside fenced code blocks and inline code spans to avoid
false positives on legitimate code.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Iterable


SMART_QUOTES = {
    "“": "left double quote",
    "”": "right double quote",
    "‘": "left single quote",
    "’": "right single quote",
}
EM_DASH = "—"
EN_DASH = "–"

LIST_LEADIN_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+\*\*[^*\n]+\*\*\s+[-—–]\s+")
REF_LINK_SHORTHAND_RE = re.compile(r"\[[^\]\n]+\]\[\]")
COAUTHOR_RE = re.compile(r"^\s*Co-Authored-By:", re.IGNORECASE | re.MULTILINE)
# Local-only paths that must not appear in external content
# (PRs, Linear, Notion, Slack, Gmail) per rules/general.md.
LOCAL_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_/])(?:"
    r"agent-os(?:/[A-Za-z0-9_./-]*)?"
    r"|~/nickolashkraus(?:/[A-Za-z0-9_./-]*)?"
    r"|~/\.claude(?:/[A-Za-z0-9_./-]*)?"
    r"|~/dotfiles(?:/[A-Za-z0-9_./-]*)?"
    r"|/Users/[A-Za-z0-9_./-]+"
    r")"
)
# `Closes:` / `Fixes:` / `Resolves:` keywords are forbidden in PR
# descriptions per rules/git.md. The Linear ref is rendered elsewhere
# as a Markdown link and GitHub does not auto-close Linear issues
# from these keywords, so the line is redundant noise.
PR_AUTOCLOSE_RE = re.compile(
    r"^\s*(?:Closes|Fixes|Resolves)\s*[:#]",
    re.IGNORECASE | re.MULTILINE,
)


def scrub_inline_code(line: str) -> str:
    """
    Remove inline code spans from a line so violations inside backticks are
    ignored. Handles single-backtick spans only; multi-backtick spans are
    rare in our content.
    """
    return re.sub(r"`[^`\n]*`", "", line)


def lint_text(
    text: str,
    field: str,
    allow_coauthor: bool = True,
    is_pr_body: bool = False,
    check_local_paths: bool = True,
) -> list[str]:
    """
    Return a list of violation strings for the given text.

    `field` is included in each message so the caller knows which field of
    the tool input tripped the rule. `is_pr_body` enables the
    `Closes:`/`Fixes:`/`Resolves:` check, which is scoped to PR bodies
    only per rules/git.md. `check_local_paths` enables the local-path
    check, which is scoped to outbound content per rules/general.md (the
    in-repo dotfiles Markdown legitimately references local paths).
    """
    violations: list[str] = []

    if not allow_coauthor and COAUTHOR_RE.search(text):
        violations.append(
            f"{field}: contains `Co-Authored-By:` "
            "(forbidden in commits per rules/git.md)"
        )

    if is_pr_body and PR_AUTOCLOSE_RE.search(text):
        violations.append(
            f"{field}: contains `Closes:` / `Fixes:` / `Resolves:` "
            "(forbidden in PR descriptions per rules/git.md; render the "
            "Linear ref as a Markdown link instead)"
        )

    in_code = False
    for lineno, raw in enumerate(text.splitlines(), 1):
        stripped = raw.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code = not in_code
            continue
        if in_code:
            continue

        line = scrub_inline_code(raw)

        if EM_DASH in line:
            violations.append(
                f"{field} line {lineno}: em dash (use comma, paren, "
                "semicolon, or rewrite)"
            )
        if EN_DASH in line:
            violations.append(
                f"{field} line {lineno}: en dash (use straight hyphen or " "rewrite)"
            )
        for ch, name in SMART_QUOTES.items():
            if ch in line:
                violations.append(f"{field} line {lineno}: {name} (use straight quote)")
                break
        if LIST_LEADIN_RE.match(raw):
            violations.append(
                f"{field} line {lineno}: list item uses `**X** -` "
                "(use `**X**:` per rules/typography.md)"
            )
        if REF_LINK_SHORTHAND_RE.search(line):
            violations.append(
                f"{field} line {lineno}: reference link shorthand "
                "`[label][]` (use `[text][label]` per rules/typography.md)"
            )
        if check_local_paths:
            for local_match in LOCAL_PATH_RE.finditer(line):
                violations.append(
                    f"{field} line {lineno}: local-only path "
                    f"`{local_match.group(0)}` (forbidden in external "
                    "content per rules/general.md; inline a summary "
                    "instead)"
                )

    return violations


def walk_strings(obj, path: str = "") -> Iterable[tuple[str, str]]:
    """
    Yield (path, string) pairs for every string leaf in a nested structure.

    Used for tools like notion-create-pages whose payloads contain content
    nested inside arrays of objects.
    """
    if isinstance(obj, str):
        yield path or "<root>", obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            sub = f"{path}.{k}" if path else k
            yield from walk_strings(v, sub)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            sub = f"{path}[{i}]"
            yield from walk_strings(v, sub)


HEREDOC_RE = re.compile(
    r"<<[-]?\s*['\"]?(\w+)['\"]?\s*\n(.*?)\n\s*\1\b",
    re.DOTALL,
)
FLAG_VALUE_RE = re.compile(
    r"(?:^|\s)(--?)(m|message|body|title|body-file)[=\s]+"
    r"(\"((?:[^\"\\]|\\.)*)\"|'((?:[^'\\]|\\.)*)')",
)


def extract_bash_content(
    command: str,
) -> list[tuple[str, str, bool, bool]]:
    """
    Extract text payloads from `git commit` and `gh {pr,issue} ...` commands.

    Returns a list of (field_label, text, is_commit, is_pr_body). `is_commit`
    toggles the Co-Authored-By check; `is_pr_body` enables the
    `Closes:`/`Fixes:`/`Resolves:` check (PR bodies only per rules/git.md).
    """
    if not re.search(r"\b(git\s+commit|gh\s+(pr|issue)\s+\w+)", command):
        return []

    is_commit = bool(re.search(r"\bgit\s+commit\b", command))
    is_pr_body = bool(re.search(r"\bgh\s+pr\s+(create|edit)\b", command))
    fields: list[tuple[str, str, bool, bool]] = []

    for m in HEREDOC_RE.finditer(command):
        fields.append((f"heredoc<{m.group(1)}>", m.group(2), is_commit, is_pr_body))

    redacted = HEREDOC_RE.sub("", command)
    for m in FLAG_VALUE_RE.finditer(redacted):
        flag = f"{m.group(1)}{m.group(2)}"
        value = m.group(4) if m.group(4) is not None else m.group(5)
        if value:
            # The body of a PR is what carries the autoclose keywords; the
            # title is too short to bother filtering, but applying the check
            # there is also harmless.
            is_body = is_pr_body and m.group(2) in ("body", "body-file")
            fields.append((f"arg {flag}", value, is_commit, is_body))

    return fields


MARKDOWN_EXTENSIONS = (".md", ".markdown")


def extract_fields(
    tool_name: str, tool_input: dict
) -> list[tuple[str, str, bool, bool, bool]]:
    """
    Return a list of (field_label, text, allow_coauthor, is_pr_body,
    check_local_paths) tuples to lint.

    `allow_coauthor` is False only for commit messages, where the rule
    forbids `Co-Authored-By:` lines. `is_pr_body` is True only for PR body
    content, where the `Closes:`/`Fixes:`/`Resolves:` rule applies.
    `check_local_paths` is False for in-repo Markdown edits, where
    references to local paths are legitimate.
    """
    out: list[tuple[str, str, bool, bool, bool]] = []

    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        if isinstance(cmd, str):
            for label, text, is_commit, is_pr_body in extract_bash_content(cmd):
                out.append((label, text, not is_commit, is_pr_body, True))
        return out

    if tool_name in ("Edit", "Write"):
        file_path = tool_input.get("file_path", "")
        if not isinstance(file_path, str):
            return out
        if not file_path.endswith(MARKDOWN_EXTENSIONS):
            return out
        if tool_name == "Edit":
            new_string = tool_input.get("new_string", "")
            if isinstance(new_string, str) and new_string:
                out.append(("new_string", new_string, True, False, False))
        else:
            content = tool_input.get("content", "")
            if isinstance(content, str) and content:
                out.append(("content", content, True, False, False))
        return out

    for label, value in walk_strings(tool_input):
        if not value or len(value) < 2:
            continue
        out.append((label, value, True, False, True))

    return out


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    if not isinstance(tool_input, dict):
        return 0

    fields = extract_fields(tool_name, tool_input)
    if not fields:
        return 0

    all_violations: list[str] = []
    for label, text, allow_coauthor, is_pr_body, check_local_paths in fields:
        if not isinstance(text, str):
            continue
        all_violations.extend(
            lint_text(
                text,
                label,
                allow_coauthor=allow_coauthor,
                is_pr_body=is_pr_body,
                check_local_paths=check_local_paths,
            )
        )

    if not all_violations:
        return 0

    sys.stderr.write(
        "Typography violations detected. Fix the content and retry.\n"
        "\n"
        + "\n".join(f"  - {v}" for v in all_violations)
        + "\n\nRules: ~/.claude/rules/typography.md\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
