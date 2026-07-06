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

Every gated invocation is appended to ~/.claude/lint-outbound.log
(mirroring rule-check.py's log) so blocks are auditable across sessions.

This hook also owns every check that requires counting characters
(commit-subject length, commit-body wrap, Markdown table column padding),
measured deterministically on the raw SOURCE text. rule-check.py's
LLM pass is explicitly told not to do character arithmetic.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Iterable

LOG_FILE = Path.home() / ".claude" / "lint-outbound.log"


def log(msg: str) -> None:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except OSError:
        pass


SMART_QUOTES = {
    "“": "left double quote",
    "”": "right double quote",
    "‘": "left single quote",
    "’": "right single quote",
}
EM_DASH = "—"
EN_DASH = "–"

LIST_LEADIN_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+\*\*[^*\n]+\*\*\s+[-—–]\s+")
# Bullet lead-ins that require a capitalized first word after the colon
# per rules/typography.md: a bold label (`**X**:`), a Markdown-link label
# (`[X](url):`), or a code-span label (`` `X`: ``), optionally followed
# by a short parenthetical. Plain-prose colons inside a bullet are NOT
# flagged here: a colon joining two clauses in a flowing sentence keeps
# lowercase, and telling a label apart from a clause in plain text needs
# judgment, so that case is left to the semantic rule check. The
# post-colon guard `[a-z]` requires an alphabetic start, so
# non-alphabetic values (paths, code spans, numbers, URLs) are naturally
# exempt.
LOWERCASE_AFTER_BOLD_COLON_RE = re.compile(
    r"^\s*(?:[-*+]|\d+[.)])\s+"
    r"(?:\*\*[^*\n]+\*\*|\[[^\]\n]+\]\([^)\n]+\)|`[^`\n]+`)"
    r"(?:\s*\([^)\n]*\))?\s*:\s+[a-z]"
)
# Retained as an alias so any external consumer that imported the old
# name keeps working.
LOWERCASE_AFTER_PLAIN_COLON_RE = LOWERCASE_AFTER_BOLD_COLON_RE
# Line-initial Markdown link lead-in followed by a colon and a lowercase word.
# Catches reference-list lines like `[EPD-1337](url): lowercase title`.
# Capitalization is required only for label/lead-in colons; a colon joining two
# clauses inside a flowing sentence keeps lowercase per rules/typography.md, so
# plain mid-prose colons and mid-prose links are intentionally not flagged.
LOWERCASE_AFTER_LINK_COLON_RE = re.compile(r"^\s*\[[^\]\n]+\]\([^)\n]+\):\s+[a-z]\S*")
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


LIST_MARKER_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")
# A real hard wrap breaks near the wrap column, so the line BEFORE the
# break is long. When the preceding line is shorter than this, adjacent
# lines are two distinct short lines (title + lead-in, label + value),
# not a wrapped paragraph.
WRAP_MIN_PREV_LEN = 64
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
        prev = block[0][1]
        for ln, line in block[1:]:
            if (
                not is_structural_line(line)
                and len(prev.rstrip()) >= WRAP_MIN_PREV_LEN
            ):
                violations.append(ln)
            prev = line
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
        # An ATX header is a standalone block: the line after it is a new
        # paragraph, not a wrap of the header.
        if stripped.startswith("#"):
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


TABLE_SEPARATOR_CELL_RE = re.compile(r"^\s*:?-{3,}:?\s*$")


def split_table_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return re.split(r"(?<!\\)\|", s)


def detect_table_padding(text: str) -> list[str]:
    """Flag Markdown tables whose columns are not padded to equal SOURCE
    width per rules/typography.md. Width is measured on the raw source
    text: code spans and links count at their full character length,
    matching how a monospace editor aligns the table (GitHub renders any
    valid table regardless, so source width is the only width that
    matters). Tables whose rows disagree on column count are skipped
    rather than flagged: malformed structure is not a padding problem."""
    violations: list[str] = []
    in_code = False
    block: list[tuple[int, str]] = []

    def check_block() -> None:
        if len(block) < 2:
            block.clear()
            return
        rows = [(ln, split_table_row(line)) for ln, line in block]
        sep_cells = rows[1][1]
        if not all(TABLE_SEPARATOR_CELL_RE.match(c) for c in sep_cells):
            block.clear()
            return
        ncols = len(rows[0][1])
        if any(len(cells) != ncols for _, cells in rows):
            block.clear()
            return
        for col in range(ncols):
            widths = {len(cells[col]) for _, cells in rows}
            if len(widths) > 1:
                violations.append(
                    f"table at line {block[0][0]}, column {col + 1}: cells "
                    f"are not padded to equal source width "
                    f"(widths {sorted(widths)}); pad every column to its "
                    "widest cell, counting raw source characters "
                    "(backticks and link syntax included) per "
                    "rules/typography.md"
                )
        block.clear()

    for lineno, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            check_block()
            in_code = not in_code
            continue
        if in_code:
            continue
        if stripped.startswith("|") and stripped.count("|") >= 2:
            block.append((lineno, raw))
        else:
            check_block()
    check_block()
    return violations


LINEAR_SLUG_SUBJECT_RE = re.compile(r"^[A-Z]{2,10}-\d+: ")
CONVENTIONAL_SUBJECT_RE = re.compile(r"^[a-z][a-z0-9]*(?:\([^)]+\))?!?: ")
AUTO_SUBJECT_RE = re.compile(r'^(?:Merge |Revert ")')
COMMIT_SUBJECT_LIMIT = 50
CONVENTIONAL_SUBJECT_LIMIT = 72
COMMIT_BODY_WRAP = 72


def lint_commit_message(text: str, field: str) -> list[str]:
    """Deterministic checks for a FULL commit message (heredoc, `-F
    <file>`, or a sole `-m`). Subject: 50 chars max, except Linear-slug
    subjects (`BYB-1345: Exact Issue Title`, no cap per rules/git.md),
    Conventional Commits subjects (72 chars per the carve-out), and
    auto-generated Merge/Revert subjects. Body: wrap at 72, skipping
    fenced code and lines an URL or single unbreakable token makes long.
    These length checks live here, not in the LLM rule check, so the
    verdict never depends on model arithmetic."""
    violations: list[str] = []
    lines = text.splitlines()
    if not lines:
        return violations
    subject = lines[0].rstrip()
    if (
        len(subject) > COMMIT_SUBJECT_LIMIT
        and not LINEAR_SLUG_SUBJECT_RE.match(subject)
        and not AUTO_SUBJECT_RE.match(subject)
        and not (
            CONVENTIONAL_SUBJECT_RE.match(subject)
            and len(subject) <= CONVENTIONAL_SUBJECT_LIMIT
        )
    ):
        violations.append(
            f"{field} line 1: commit subject is {len(subject)} chars "
            "(50 max per rules/git.md; `SLUG: Exact Issue Title` subjects "
            "are exempt)"
        )
    if len(lines) >= 2 and lines[1].strip():
        violations.append(
            f"{field} line 2: missing blank line between commit subject "
            "and body (rules/git.md)"
        )
    in_code = False
    for lineno, raw in enumerate(lines[2:], 3):
        stripped = raw.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code = not in_code
            continue
        if in_code:
            continue
        line = raw.rstrip()
        if len(line) > COMMIT_BODY_WRAP:
            if "://" in line or " " not in line[:COMMIT_BODY_WRAP]:
                continue
            violations.append(
                f"{field} line {lineno}: commit body line is "
                f"{len(line)} chars (wrap at 72 per rules/git.md)"
            )
    return violations


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

    violations.extend(f"{field}: {v}" for v in detect_table_padding(text))

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
        if LOWERCASE_AFTER_LINK_COLON_RE.search(line):
            violations.append(
                f"{field} line {lineno}: link lead-in followed by "
                "a colon and a lowercase word (capitalize the first "
                "word after a label colon per rules/typography.md)"
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
# Bypass pattern: a bare shell-variable expansion (`"$var"` / `'$var'` /
# `"${var}"`). When the extracted value matches, the literal string is
# what reaches `lint_text`, not the expanded content, so typography
# violations slip through. Reject at extraction time and force the body
# through Write or a heredoc. (gh's `@file` shorthand is handled by
# reading the file at hook-eval time, not by blocking.)
BARE_VAR_RE = re.compile(r"^\$\{?\w+\}?$")

# Heredocs that are stdin for a code interpreter (`python3 - <<'PY'`)
# carry source code, not outbound prose, and must not be linted as such.
CODE_INTERPRETERS = frozenset(
    {
        "python",
        "python3",
        "node",
        "ruby",
        "perl",
        "php",
        "osascript",
        "psql",
        "sqlite3",
        "jq",
        "awk",
    }
)


def heredoc_feeds_interpreter(command: str, heredoc_start: int) -> bool:
    """True when the command word owning the heredoc at `heredoc_start`
    is a code interpreter."""
    prefix = command[:heredoc_start]
    segment = re.split(r"[|;&\n]|\$\(", prefix)[-1].strip()
    words = segment.split()
    first = os.path.basename(words[0]) if words else ""
    return first in CODE_INTERPRETERS

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
) -> list[tuple[str, str, bool, bool, bool]]:
    """
    Extract text payloads from `git commit` and `gh {pr,issue} ...` commands.

    Returns a list of (field_label, text, is_commit, is_pr_body,
    is_full_commit). `is_commit` toggles the Co-Authored-By check;
    `is_pr_body` enables the `Closes:`/`Fixes:`/`Resolves:` check (PR
    bodies only per rules/git.md); `is_full_commit` enables the
    deterministic subject-length and body-wrap checks, so it is set only
    when the field is unambiguously an entire commit message.
    """
    if not re.search(r"\b(git\s+commit|gh\s+(pr|issue)\s+\w+|gh\s+api\b)", command):
        return []

    is_commit = bool(re.search(r"\bgit\s+commit\b", command))
    has_gh = bool(re.search(r"\bgh\s+(pr|issue|api)\b", command))
    is_pr_body = bool(re.search(r"\bgh\s+pr\s+(create|edit)\b", command))
    fields: list[tuple[str, str, bool, bool, bool]] = []

    # A heredoc in a commit-only command is the whole commit message. In
    # a compound command that also runs gh, ownership is ambiguous, so
    # the length checks stay off rather than risk running the commit
    # subject rule against a PR body.
    heredoc_is_commit = is_commit and not has_gh
    for m in HEREDOC_RE.finditer(command):
        if heredoc_feeds_interpreter(command, m.start()):
            continue
        fields.append(
            (
                f"heredoc<{m.group(1)}>",
                m.group(2),
                is_commit,
                is_pr_body,
                heredoc_is_commit,
            )
        )

    redacted = HEREDOC_RE.sub("", command)
    message_flags = [
        m for m in FLAG_VALUE_RE.finditer(redacted) if m.group(2) in ("m", "message")
    ]
    for m in FLAG_VALUE_RE.finditer(redacted):
        flag = f"{m.group(1)}{m.group(2)}"
        value = m.group(4) if m.group(4) is not None else m.group(5)
        if value:
            # Label each flag by the command that owns it: -m/--message
            # are commit flags; --body/--title/--body-file belong to gh.
            # The body of a PR is what carries the autoclose keywords;
            # the title is too short to bother filtering, but applying
            # the check there is also harmless.
            field_is_commit = is_commit and m.group(2) in ("m", "message")
            is_body = is_pr_body and m.group(2) in ("body", "body-file")
            # A sole -m is the entire commit message (subject only);
            # with multiple -m flags, later ones are body paragraphs.
            is_full = field_is_commit and len(message_flags) == 1
            fields.append((f"arg {flag}", value, field_is_commit, is_body, is_full))
    for m in GH_API_FIELD_RE.finditer(redacted):
        flag = f"-f {m.group(1)}"
        value = m.group(3) if m.group(3) is not None else m.group(4)
        if value:
            fields.append((f"arg {flag}", value, False, is_pr_body, False))

    # `--field body=@file` / `-F body=@file` (gh's read-from-file
    # shorthand). Read the file at hook-eval time so the body is linted;
    # never block just because the content lives in a file. Silent on
    # OSError (gh surfaces file-not-found itself), and `@-` is stdin,
    # which the heredoc branch already covers.
    for m in re.finditer(
        r"(?:^|\s)(?:-[fF]|--(?:raw-)?field)\s+(body|title)=@(\S+)",
        redacted,
    ):
        path = m.group(2).strip("'\"")
        if path == "-":
            continue
        try:
            text = Path(os.path.expanduser(path)).read_text()
        except OSError:
            continue
        if text:
            fields.append(
                (f"arg --field {m.group(1)} @{path}", text, False, is_pr_body, False)
            )

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
                    (f"arg --body-file {path}", text, False, is_pr_body, False)
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
                    fields.append((f"arg -F {path}", text, True, False, True))
            except OSError:
                pass

    return fields


def is_bypass_value(value: str) -> str | None:
    """Return a reason string if `value` is a lint-bypassing reference
    (bare `$var` expansion), or None if it's a real string. A bare
    expansion reaches `lint_text` as the literal `$var`, not as its
    expanded content, so the body text is never actually inspected."""
    if BARE_VAR_RE.match(value):
        return (
            "body argument is a bare shell-variable expansion; the hook "
            "lints the literal `$var` string, not the expanded content. "
            "Write the body to a file with the Write tool (which is "
            "linted), then `gh ... --body-file <path>`. Heredoc bodies "
            "(`<<'EOF' ... EOF`) are also linted."
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
) -> list[tuple[str, str, bool, bool, bool, bool]]:
    """
    Return a list of (field_label, text, allow_coauthor, is_pr_body,
    check_local_paths, is_full_commit) tuples to lint.

    `allow_coauthor` is False only for commit messages, where the rule
    forbids `Co-Authored-By:` lines. `is_pr_body` is True only for PR body
    content, where the `Closes:`/`Fixes:`/`Resolves:` rule applies.
    `check_local_paths` is False for in-repo Markdown edits, where
    references to local paths are legitimate. `is_full_commit` enables
    the deterministic commit subject-length and body-wrap checks.
    """
    out: list[tuple[str, str, bool, bool, bool, bool]] = []

    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        if isinstance(cmd, str):
            for label, text, is_commit, is_pr_body, is_full in extract_bash_content(
                cmd
            ):
                out.append((label, text, not is_commit, is_pr_body, True, is_full))
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
                out.append(("new_string", new_string, True, False, is_external, False))
        else:
            content = tool_input.get("content", "")
            if isinstance(content, str) and content:
                out.append(("content", content, True, False, is_external, False))
        return out

    for label, value in walk_strings(tool_input):
        if not value or len(value) < 2:
            continue
        out.append((label, value, True, False, True, False))

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
    for label, text, allow_coauthor, is_pr_body, check_local_paths, is_full in fields:
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
        if is_full:
            all_violations.extend(lint_commit_message(text, label))

    log(
        f"CHECK tool={tool_name} fields={len(fields)} "
        f"violations={len(all_violations)}"
    )
    for v in all_violations:
        log(f"  VIOLATION {v}")

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
