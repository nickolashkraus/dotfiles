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
import os
import re
import sys
from pathlib import Path
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
# Bullet items with any lead-in followed by `: lowercase_word` violate
# rules/typography.md, which requires the first word after a colon to
# always be capitalized regardless of whether a clause, value, or
# list-fragment follows. Lead-in may contain `**bold**`, plain text,
# parentheticals, Markdown links, code spans, anything. The post-colon
# guard `[a-z]\S*` requires an alphabetic start, so non-alphabetic
# values (paths, code spans, numbers, URLs) are naturally exempt.
LOWERCASE_AFTER_BOLD_COLON_RE = re.compile(r"^\s*[-*+]\s+\S.*?:\s+[a-z]\S*")
# Retained as an alias so any external consumer that imported the old
# name keeps working; the broadened bullet rule above subsumes both
# bold-lead and plain-text-lead cases.
LOWERCASE_AFTER_PLAIN_COLON_RE = LOWERCASE_AFTER_BOLD_COLON_RE
# Mid-prose colon followed by a lowercase word (e.g., `vacuous: both
# candidates were ...`). Requires a lowercase word before the colon
# to scope this rule to prose; bulleted forms are caught by
# LOWERCASE_AFTER_BOLD_COLON_RE above, and free-floating Title-case
# forms (`Note: ...` mid-paragraph) are treated as inline headings and
# intentionally not flagged. Inline code is scrubbed upstream, so URLs
# / file:line / JSON / config snippets inside backticks don't trip
# this rule.
LOWERCASE_AFTER_PROSE_COLON_RE = re.compile(r"\b[a-z][a-z]+:\s+[a-z]\S*")
# Markdown link followed by colon and lowercase word: `[text](url):
# lowercase word ...`. Common in PR-comment replies like `Addressed in
# [commit](url): added X to Y`. Not caught by the prose rule above
# because the character before the colon is `)`, not a word.
LOWERCASE_AFTER_LINK_COLON_RE = re.compile(r"\]\([^)\n]+\):\s+[a-z]\S*")
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


LIST_MARKER_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s")
# Markdown reference-link definitions (`[label]: url ...`). Each one is a
# standalone metadata line, not prose; consecutive reference defs should
# not be mistaken for a wrapped paragraph.
REF_DEF_RE = re.compile(r"^\s*\[[^\]\n]+\]:\s+\S")


def is_structural_line(line: str) -> bool:
    """A list item or a reference-link definition (treated as block-structural,
    not prose, for hard-wrap detection)."""
    return bool(LIST_MARKER_RE.match(line) or REF_DEF_RE.match(line))


def detect_hard_wraps(text: str) -> list[int]:
    """
    Return line numbers of lines that look like hard wraps within paragraphs
    or wrapped bullets. External content (PR bodies, Linear, Notion, Slack)
    must be single-line-per-paragraph per rules/git.md and rules/writing.md;
    Markdown renderers handle wrapping. This catches in-source soft wraps
    that look fine in an editor but ship as flow-prose to the destination.

    Skipped: code blocks, tables (lines containing `|`), blockquotes (lines
    starting with `>`), and blocks where every continuation line is itself
    a list item (nested lists are sub-items, not wraps).
    """
    in_code = False
    block: list[tuple[int, str]] = []
    violations: list[int] = []

    def flush() -> None:
        if len(block) < 2:
            block.clear()
            return
        has_table = any("|" in line for _, line in block)
        has_blockquote = any(line.lstrip().startswith(">") for _, line in block)
        if has_table or has_blockquote:
            block.clear()
            return
        # Skip pure structural blocks: every continuation line is a list
        # item or a reference-link definition.
        if all(is_structural_line(line) for _, line in block[1:]):
            block.clear()
            return
        for ln, line in block[1:]:
            if not is_structural_line(line):
                violations.append(ln)
        block.clear()

    for lineno, raw in enumerate(text.splitlines(), 1):
        stripped = raw.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            flush()
            in_code = not in_code
            continue
        if in_code:
            continue
        if not stripped:
            flush()
            continue
        block.append((lineno, raw))
    flush()

    return violations


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
    check AND the hard-wrap check; both apply only to outbound content
    (Bash heredocs / MCP payloads), not to in-repo dotfiles Markdown.
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

    # Hard-wrap detection applies to external content (PR bodies,
    # Linear/Notion/Slack payloads, out-of-repo Markdown drafts) but NOT
    # to commit messages, which wrap at 72 chars per rules/git.md.
    # `allow_coauthor=False` is the signal that this is a commit body.
    if check_local_paths and allow_coauthor:
        for ln in detect_hard_wraps(text):
            violations.append(
                f"{field} line {ln}: hard-wrapped paragraph (external "
                "content should be a single unwrapped line per paragraph "
                "per rules/git.md; Markdown renderers handle wrapping)"
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
        if LOWERCASE_AFTER_BOLD_COLON_RE.match(raw):
            violations.append(
                f"{field} line {lineno}: bullet has a lowercase word "
                "after the colon (always capitalize the first word "
                "after a colon per rules/typography.md; non-alphabetic "
                "starts like paths or code spans are naturally exempt)"
            )
        if LOWERCASE_AFTER_PROSE_COLON_RE.search(line):
            violations.append(
                f"{field} line {lineno}: mid-prose colon followed by "
                "a lowercase word (always capitalize the first word "
                "after a colon per rules/typography.md)"
            )
        if LOWERCASE_AFTER_LINK_COLON_RE.search(line):
            violations.append(
                f"{field} line {lineno}: Markdown link followed by "
                "a colon and a lowercase word (always capitalize the "
                "first word after a colon per rules/typography.md)"
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
# `gh api` uses `-f field=value` / `-F field=value` / `--field field=value`
# / `--raw-field field=value` instead of `--body`. Match the field names
# that carry user-visible prose (`body`, `title`) so PR-comment,
# review-comment, and issue-comment posts via raw API get linted just like
# `gh pr comment --body`.
GH_API_FIELD_RE = re.compile(
    r"(?:^|\s)(?:-[fF]|--(?:raw-)?field)\s+(body|title)="
    r"(\"((?:[^\"\\]|\\.)*)\"|'((?:[^'\\]|\\.)*)')",
)
# Bypass patterns: a bare shell-variable expansion (`"$var"` / `'$var'` /
# `"${var}"`) or a gh-`@file` reference. When the extracted value matches
# one of these, the literal string is what reaches `lint_text`, not the
# expanded content, so typography violations slip through. Reject these
# at extraction time and force the body through Write or a heredoc.
BARE_VAR_RE = re.compile(r"^\$\{?\w+\}?$")
AT_FILE_RE = re.compile(r"^@\S+$")

# `gh ... --body-file <path>` and `git commit -F|--file <path>` point the
# command at a file rather than carrying the body inline. The Write call
# that created the file is linted only when it has a Markdown extension,
# so non-`.md` bodies (like `/tmp/commit-msg.txt`) bypass the lint
# entirely. Read the file contents at hook-eval time so the body is
# always inspected regardless of file extension.
BODY_FILE_FLAG_RE = re.compile(r"(?:^|\s)--body-file[=\s]+(\S+)")
COMMIT_FILE_FLAG_RE = re.compile(r"(?:^|\s)(?:-F|--file)[=\s]+(\S+)")


def extract_bash_content(
    command: str,
) -> list[tuple[str, str, bool, bool]]:
    """
    Extract text payloads from `git commit` and `gh {pr,issue} ...` commands.

    Returns a list of (field_label, text, is_commit, is_pr_body). `is_commit`
    toggles the Co-Authored-By check; `is_pr_body` enables the
    `Closes:`/`Fixes:`/`Resolves:` check (PR bodies only per rules/git.md).
    """
    if not re.search(r"\b(git\s+commit|gh\s+(pr|issue)\s+\w+|gh\s+api\b)", command):
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
    for m in GH_API_FIELD_RE.finditer(redacted):
        flag = f"-f {m.group(1)}"
        value = m.group(3) if m.group(3) is not None else m.group(4)
        if value:
            fields.append((f"arg {flag}", value, is_commit, is_pr_body))

    # Also catch `--field body=@file` / `-F body=@file` (gh's read-from-file
    # shorthand), which has no quote group for FLAG/FIELD regexes to match.
    # Emit a synthetic "@file" value so the bypass guard below trips.
    for m in re.finditer(
        r"(?:^|\s)(?:-[fF]|--(?:raw-)?field)\s+(body|title)=(@\S+)",
        redacted,
    ):
        fields.append((f"arg --field {m.group(1)}", m.group(2), is_commit, is_pr_body))

    # `gh ... --body-file <path>` (any gh subcommand). Read the file so
    # the body is linted regardless of its extension. Silent on OSError
    # so a missing path does not block the command (gh itself will
    # surface the file-not-found error at execution time).
    for m in BODY_FILE_FLAG_RE.finditer(redacted):
        path = m.group(1).strip("'\"")
        try:
            text = Path(os.path.expanduser(path)).read_text()
            if text:
                fields.append(
                    (f"arg --body-file {path}", text, is_commit, is_pr_body)
                )
        except OSError:
            pass

    # `git commit -F|--file <path>`. Scoped to git commit because `-F`
    # collides with `gh api -F field=value`.
    if is_commit:
        for m in COMMIT_FILE_FLAG_RE.finditer(redacted):
            path = m.group(1).strip("'\"")
            try:
                text = Path(os.path.expanduser(path)).read_text()
                if text:
                    fields.append((f"arg -F {path}", text, is_commit, is_pr_body))
            except OSError:
                pass

    return fields


def is_bypass_value(value: str) -> str | None:
    """Return a reason string if `value` is a lint-bypassing reference
    (bare `$var` expansion or gh `@file` shorthand), or None if it's a
    real string. These reach `lint_text` as literals, not as their
    expanded content, so the body text is never actually inspected."""
    if BARE_VAR_RE.match(value):
        return (
            "body argument is a bare shell-variable expansion; the hook "
            "lints the literal `$var` string, not the expanded content. "
            "Write the body to a file with the Write tool (which is "
            "linted), then `gh ... --body-file <path>`. Heredoc bodies "
            "(`<<'EOF' ... EOF`) are also linted."
        )
    if AT_FILE_RE.match(value):
        return (
            "body argument uses gh's `@file` shorthand; the hook cannot "
            "see the file contents at parse time. Either inline the body "
            "via a heredoc, or use `gh pr|issue ... --body-file <path>` "
            "(the file's Write call is linted at write time)."
        )
    return None


MARKDOWN_EXTENSIONS = (".md", ".markdown")

# Paths under these prefixes are internal Markdown (source-control'd
# project files OR Claude Code's own state directories like
# `~/.claude/projects/<proj>/memory/`). They follow the <80 char
# typography rule and can reference local-only paths. Markdown outside
# these prefixes (typically `/tmp/*.md` PR/Linear/Notion body drafts) is
# treated as external content and gets the full lint.
IN_REPO_PREFIXES = (
    "/Users/nickolas/.claude/",
    "/Users/nickolas/nickolashkraus/",
    "/Users/nickolas/Function-Health/",
    "/Users/nickolas/Function-Health-Terraform-Modules/",
    "/Users/nickolas/infrable-io/",
    "/Users/nickolas/grind-rip/",
)


def is_in_repo_path(path: str) -> bool:
    return any(path.startswith(p) for p in IN_REPO_PREFIXES)


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
        is_external = not is_in_repo_path(file_path)
        if tool_name == "Edit":
            new_string = tool_input.get("new_string", "")
            if isinstance(new_string, str) and new_string:
                out.append(("new_string", new_string, True, False, is_external))
        else:
            content = tool_input.get("content", "")
            if isinstance(content, str) and content:
                out.append(("content", content, True, False, is_external))
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
        bypass_reason = is_bypass_value(text)
        if bypass_reason is not None:
            all_violations.append(f"{label}: {bypass_reason}")
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
