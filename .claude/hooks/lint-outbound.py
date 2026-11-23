#!/usr/bin/env python3
"""
PreToolUse hook: lints content destined for external platforms (Linear, Notion,
Slack, Gmail, GitHub, Git) against ~/.claude/rules/typography.md.

Reads the Claude Code hook payload on stdin, extracts text fields from the tool
input, scans for typography violations, and exits with code 2 (blocking the
tool call) when any are found. Stderr is shown to Claude so it can fix the
content and retry.

Skips content inside fenced code blocks and inline code spans to avoid false
positives on legitimate code.

Every gated invocation is appended to ~/.claude/lint-outbound.log (mirroring
rule-check.py's log) so blocks are auditable across sessions.

This hook also owns every check that requires counting characters
(commit-subject length, commit-body wrap, Markdown table column padding),
measured deterministically on the raw SOURCE text. rule-check.py's LLM pass is
explicitly told not to do character arithmetic.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from collections.abc import Iterable
from pathlib import Path

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

# AI-slop phraseology per rules/general.md ("do not speak like an LLM").
# The catalog lives in ai_slop.py so the regexes here and the prose
# bullets in rules/general.md cannot drift apart; see that module's
# --sync-rules. rule-check.py's LLM pass still owns the structural
# patterns (rule-of-three reflex, fake-balance framing, novel antithesis
# shapes). Checked against inline-code-scrubbed prose outside fenced
# blocks, so identifiers like `landed_at` in code spans do not trip it.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ai_slop import AI_SLOP_CONTEXT, AI_SLOP_PATTERNS

LIST_LEADIN_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+\*\*[^*\n]+\*\*\s+[-—–]\s+")

# British spellings, per rules/typography.md. Only forms with no American
# homograph are listed, so a hit is always wrong rather than a judgment call.
# Fenced blocks and inline code spans are already stripped before this runs,
# which is what exempts identifiers, API fields and log output. "towards" is
# left out on purpose: both it and "toward" are acceptable American usage, so
# the rule states a preference and the linter does not gate it.
BRITISH_SPELLINGS = {
    "amongst": "among",
    "behaviour": "behavior",
    "behavioural": "behavioral",
    "behaviours": "behaviors",
    "cancelled": "canceled",
    "cancelling": "canceling",
    "canonicalise": "canonicalize",
    "canonicalised": "canonicalized",
    "canonicalises": "canonicalizes",
    "canonicalising": "canonicalizing",
    "centre": "center",
    "centred": "centered",
    "centres": "centers",
    "centring": "centering",
    "colour": "color",
    "coloured": "colored",
    "colourful": "colorful",
    "colours": "colors",
    "defence": "defense",
    "defences": "defenses",
    "fulfil": "fulfill",
    "fulfils": "fulfills",
    "initialise": "initialize",
    "initialised": "initialized",
    "initialises": "initializes",
    "initialising": "initializing",
    "labelled": "labeled",
    "labelling": "labeling",
    "learnt": "learned",
    "licence": "license",
    "licences": "licenses",
    "modelled": "modeled",
    "modelling": "modeling",
    "normalise": "normalize",
    "normalised": "normalized",
    "normalises": "normalizes",
    "normalising": "normalizing",
    "optimise": "optimize",
    "optimised": "optimized",
    "optimises": "optimizes",
    "optimising": "optimizing",
    "organisation": "organization",
    "organisations": "organizations",
    "organise": "organize",
    "organised": "organized",
    "organises": "organizes",
    "organising": "organizing",
    "prioritise": "prioritize",
    "prioritised": "prioritized",
    "prioritises": "prioritizes",
    "prioritising": "prioritizing",
    "recognisable": "recognizable",
    "recognise": "recognize",
    "recognised": "recognized",
    "recognises": "recognizes",
    "recognising": "recognizing",
    "serialise": "serialize",
    "serialised": "serialized",
    "serialises": "serializes",
    "serialising": "serializing",
    "summarise": "summarize",
    "summarised": "summarized",
    "summarises": "summarizes",
    "summarising": "summarizing",
    "travelled": "traveled",
    "travelling": "traveling",
    "whilst": "while",
}

BRITISH_RE = re.compile(
    r"\b(" + "|".join(sorted(BRITISH_SPELLINGS)) + r")\b", re.IGNORECASE
)
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
    r"(?:\s*\([^)\n]*\))?\s*:\s+(?![a-z][a-z0-9+.-]*://)[a-z]"
)
# Retained as an alias so any external consumer that imported the old
# name keeps working.
LOWERCASE_AFTER_PLAIN_COLON_RE = LOWERCASE_AFTER_BOLD_COLON_RE
# Line-initial Markdown link lead-in followed by a colon and a lowercase word.
# Catches reference-list lines like `[EPD-1337](url): lowercase title`.
# Capitalization is required only for label/lead-in colons; a colon joining two
# clauses inside a flowing sentence keeps lowercase per rules/typography.md, so
# plain mid-prose colons and mid-prose links are intentionally not flagged.
LOWERCASE_AFTER_LINK_COLON_RE = re.compile(
    r"^\s*\[[^\]\n]+\]\([^)\n]+\):\s+(?![a-z][a-z0-9+.-]*://)[a-z]\S*"
)
# A line-initial PLAIN-TEXT bullet label followed by `: lowercase`, e.g.
# `- Conventional Commits: the carve-out ...`. The bold/link/code-span label
# forms are caught by the regexes above; this catches the unadorned label the
# semantic check misses. Classification happens in
# `plain_label_colon_violation` so the judgment is legible; the regex only
# captures the marker and the pre-colon segment.
PLAIN_LABEL_BULLET_RE = re.compile(
    r"^\s*(?:[-*+]|\d+[.)])\s+([^:\n]+?):\s+(?![a-z][a-z0-9+.-]*://)[a-z]"
)
# Short function words allowed inside an otherwise Title-Case label without
# breaking the all-capitalized test (`Terms of Service:`, `Ship to Prod:`).
LABEL_CONNECTOR_WORDS = frozenset(
    {"of", "and", "to", "for", "the", "a", "an", "in", "on", "with", "or"}
)
# A single label word: Capitalized (`Conventional`), or an acronym with an
# optional plural `s` (`PR`, `PRs`, `IDs`).
LABEL_WORD_RE = re.compile(r"[A-Z][A-Za-z]*|[A-Z]{2,}s?")


def plain_label_colon_violation(raw: str) -> bool:
    """True when a bullet uses an unadorned Title-Case label
    (`- Conventional Commits: the ...`) whose first word after the colon should
    be capitalized. Deliberately narrow: every label word must be capitalized,
    an acronym, or a short connector, and the label is 1-4 words. That excludes
    imperative instruction bullets (`- Trace the data lifecycle: creation ...`,
    where `the`/`data`/`lifecycle` are lowercase) and clause colons, which are
    left to the semantic check. A label with a lowercase content word
    (`- PR titles: when ...`) is indistinguishable from a clause here and is
    also left to the semantic check."""
    m = PLAIN_LABEL_BULLET_RE.match(raw)
    if not m:
        return False
    label = m.group(1).strip()
    # Bold/link/code-span labels are handled by dedicated regexes; skip them
    # here so the finding stays specific and is not double-reported.
    if label[:1] in ("*", "[", "`"):
        return False
    words = label.split()
    if not (1 <= len(words) <= 4):
        return False
    for i, word in enumerate(words):
        if word.lower() in LABEL_CONNECTOR_WORDS and i != 0:
            continue
        if not LABEL_WORD_RE.fullmatch(word):
            return False
    return True


# Fix counterparts of the label-colon detectors above. Each consumes the whole
# marker + label + colon so the captured `[a-z]` is the value's first letter,
# never a colon inside the label or an inline-code span. Kept in lockstep with
# the detectors by `test_autofix_resolves_detected` (a fixed line must no
# longer be flagged).
LOWERCASE_AFTER_BOLD_COLON_FIX_RE = re.compile(
    r"^(\s*(?:[-*+]|\d+[.)])\s+"
    r"(?:\*\*[^*\n]+\*\*|\[[^\]\n]+\]\([^)\n]+\)|`[^`\n]+`)"
    r"(?:\s*\([^)\n]*\))?\s*:\s+)([a-z])"
)
LOWERCASE_AFTER_LINK_COLON_FIX_RE = re.compile(
    r"^(\s*\[[^\]\n]+\]\([^)\n]+\):\s+)([a-z])"
)


def _capitalize_after_colon(m: re.Match[str]) -> str:
    return m.group(1) + m.group(2).upper()


def _starts_with_identifier(rest: str) -> bool:
    """True when `rest` opens with an identifier such as `ppp-service`,
    `a1b2c3d` or `v2.1`, which capitalizing would corrupt."""
    words = rest.split(maxsplit=1)
    word = words[0].rstrip(".,;:)!?") if words else ""
    return bool(re.search(r"[-_/.\d]", word))


def autofix_label_colon_line(raw: str) -> str | None:
    """If `raw` is a deterministic label-colon violation (bold/link/code-span
    label, line-initial link label, or Title-Case plain label followed by
    a lowercase word), return the line with that word's first letter
    capitalized. Otherwise None. Only the cases the detectors flag with zero
    false positives are touched; the ambiguous lowercase-tail plain label is
    left for the semantic check. An identifier after the colon is left unfixed
    so the block asks for backticks instead."""
    for fix_re in (
        LOWERCASE_AFTER_BOLD_COLON_FIX_RE,
        LOWERCASE_AFTER_LINK_COLON_FIX_RE,
    ):
        m = fix_re.match(raw)
        if m:
            if _starts_with_identifier(raw[m.start(2) :]):
                return None
            return fix_re.sub(_capitalize_after_colon, raw, count=1)
    if plain_label_colon_violation(raw):
        # The plain label carries no internal colon, so the first `: ` is the
        # label colon.
        m = re.search(r"(:\s+)([a-z])", raw)
        if m is None or _starts_with_identifier(raw[m.start(2) :]):
            return None
        return re.sub(r"(:\s+)([a-z])", _capitalize_after_colon, raw, count=1)
    return None


def autofix_label_colons(text: str, existing: frozenset[str] = frozenset()) -> str:
    """Return `text` with every deterministic label-colon violation fixed.
    Skips fenced code blocks, matching `lint_text`'s per-line handling so the
    fix never touches a colon inside a code block."""
    lines = text.splitlines(keepends=True)
    in_code = False
    for idx, raw in enumerate(lines):
        body = raw.rstrip("\n")
        if body.lstrip().startswith(("```", "~~~")):
            in_code = not in_code
            continue
        if in_code or (body.strip() and body.strip() in existing):
            continue
        fixed = autofix_label_colon_line(body)
        if fixed is not None:
            lines[idx] = fixed + raw[len(body) :]
    return "".join(lines)


REF_LINK_SHORTHAND_RE = re.compile(r"\[[^\]\n]+\]\[\]")
COAUTHOR_RE = re.compile(r"^\s*Co-Authored-By:", re.IGNORECASE | re.MULTILINE)
# Local-only paths that must not appear in external content
# (PRs, Linear, Notion, Slack, Gmail) per rules/general.md. The private
# notes repo is also matched by its GitHub name: a URL or an
# `owner/repo#12` reference puts the name after a `/`, where the bare
# `agent-os` form does not match. GitHub names ignore case. It is matched
# by its `master` worktree after any directory too (`../agent-os/master`),
# and every worktree by its short link under `~/w` (rules/git.md).
LOCAL_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_/])(?:"
    r"agent-os(?:/[A-Za-z0-9_./-]*)?"
    r"|(?:~|\$HOME|\$\{HOME\})/nickolashkraus(?:/[A-Za-z0-9_./-]*)?"
    r"|(?:~|\$HOME|\$\{HOME\})/\.claude(?:/[A-Za-z0-9_./-]*)?"
    r"|(?:~|\$HOME|\$\{HOME\})/dotfiles(?:/[A-Za-z0-9_./-]*)?"
    r"|(?:~|\$HOME|\$\{HOME\})/w(?![A-Za-z0-9_-])(?:/[A-Za-z0-9_./-]*)?"
    r"|/Users/[A-Za-z0-9_./-]+"
    r")"
    r"|(?<![A-Za-z0-9_-])(?i:nickolashkraus/agent-os)(?![A-Za-z0-9_-])"
    r"(?:/[A-Za-z0-9_./-]*)?"
    r"|(?<![A-Za-z0-9_-])agent-os/master(?![A-Za-z0-9_-])"
    r"(?:/[A-Za-z0-9_./-]*)?"
)
# `Closes:` / `Fixes:` / `Resolves:` keywords are forbidden in PR
# descriptions per rules/git.md. The Linear ref is rendered elsewhere
# as a Markdown link and GitHub does not auto-close Linear issues
# from these keywords, so the line is redundant noise.
PR_AUTOCLOSE_RE = re.compile(
    r"^\s*(?:Closes|Fixes|Resolves)\s*[:#]",
    re.IGNORECASE | re.MULTILINE,
)

LINEAR_REF_RE = re.compile(r"\b([A-Z]{2,10}-\d+)\b")
LINEAR_ISSUE_ROOT = Path.home() / "nickolashkraus/agent-os/master/domains"

# A PR body and its Linear issue answer different questions: the issue says why
# the work exists and what it has to do, the body says what a reviewer of this
# diff needs that the diff does not show. A sentence appearing verbatim in both
# means one was pasted into the other, which leaves the reader two copies to
# read and one of them to re-read on every later edit.
#
# Matching per sentence rather than per paragraph, because a reflow changes
# line breaks but not sentences. Short sentences collide by coincidence, so the
# floor is deliberately high.
DUPLICATED_SENTENCE_MIN_WORDS = 12
DUPLICATED_SENTENCE_REPORT_LIMIT = 3
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
# The "Generated with Claude Code" footer, which is never wanted on any
# surface. Matched at line start in every shape it ships in: with or without
# the robot emoji, as a Markdown link or as bare text, "generated with" or
# "generated by", and pointing at either claude.com or claude.ai. Anchoring
# to the line start keeps prose that merely discusses the footer legible.
CLAUDE_FOOTER_RE = re.compile(
    r"^[^\w\n]{0,6}(?:co-)?generated\s+(?:with|by)\s+\[?\s*claude\s+code",
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
# Notion-flavored-Markdown XML block lines (<table>, <tr>, <td>...</td>,
# <callout ...>, </callout>, <table_of_contents/>, ...). These are block
# structure, not prose; consecutive XML lines are not a wrapped paragraph.
XML_TAG_LINE_RE = re.compile(r"^\s*<[^\n]*>\s*$")


def is_structural_line(line: str) -> bool:
    """A list item, a reference-link definition, or a Notion XML block line
    (treated as block-structural, not prose, for hard-wrap detection)."""
    return bool(
        LIST_MARKER_RE.match(line)
        or REF_DEF_RE.match(line)
        or XML_TAG_LINE_RE.match(line)
    )


def detect_hard_wraps(text: str) -> list[int]:
    """
    Return line numbers of lines that look like hard wraps within paragraphs or
    wrapped bullets. External content (PR bodies, Linear, Notion, Slack) must
    be single-line-per-paragraph per rules/git.md and rules/writing.md;
    Markdown renderers handle wrapping. This catches in-source soft wraps that
    look fine in an editor but ship as flow-prose to the destination.

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
            if not is_structural_line(line) and len(prev.rstrip()) >= WRAP_MIN_PREV_LEN:
                violations.append(ln)
            prev = line
        block.clear()

    for lineno, raw in enumerate(text.splitlines(), 1):
        stripped = raw.lstrip()
        if stripped.startswith(("```", "~~~")):
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
    ignored. Handles single-backtick spans only; multi-backtick spans are rare
    in our content.
    """
    return re.sub(r"`[^`\n]*`", "", line)


def scrub_code_spans(lines: list[str]) -> list[str]:
    """
    Return `lines` with inline code spans removed, one output line per input
    line. A span that wraps onto the next line of the same paragraph or list
    item is removed whole. A block with an odd number of backticks, or with
    a pair more than one line break apart, holds stray backticks, so it is
    scrubbed line by line instead of guessing the pairs.
    """
    out: list[str] = []
    block: list[str] = []

    def flush() -> None:
        joined = "\n".join(block)
        spans = re.findall(r"`[^`]*`", joined)
        if joined.count("`") % 2 == 0 and all(s.count("\n") < 2 for s in spans):
            kept = re.sub(r"`[^`]*`", lambda m: "\n" * m.group(0).count("\n"), joined)
            out.extend(kept.split("\n") if block else [])
        else:
            out.extend(scrub_inline_code(line) for line in block)
        block.clear()

    for raw in lines:
        stripped = raw.lstrip()
        alone = not stripped or stripped.startswith(("#", "|", "```", "~~~"))
        if alone or is_structural_line(raw):
            flush()
        block.append(raw)
        if alone:
            flush()
    flush()
    return out


TABLE_SEPARATOR_CELL_RE = re.compile(r"^\s*:?-{3,}:?\s*$")


def split_table_row(line: str) -> list[str]:
    s = line.strip()
    s = s.removeprefix("|")
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return re.split(r"(?<!\\)\|", s)


def detect_table_padding(text: str) -> list[str]:
    """Flag Markdown tables whose columns are not padded to equal SOURCE width
    per rules/typography.md. Width is measured on the raw source text: code
    spans and links count at their full character length, matching how
    a monospace editor aligns the table (GitHub renders any valid table
    regardless, so source width is the only width that matters). Tables whose
    rows disagree on column count are skipped rather than flagged: malformed
    structure is not a padding problem."""
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
        if stripped.startswith(("```", "~~~")):
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
    """Deterministic checks for a FULL commit message (heredoc, `-F <file>`, or
    a sole `-m`). Subject: 50 chars max, except Linear-slug subjects
    (`BYB-1345: Exact Issue Title`, no cap per rules/git.md), Conventional
    Commits subjects (72 chars per the carve-out), and auto-generated
    Merge/Revert subjects. Body: wrap at 72, skipping fenced code and lines an
    URL or single unbreakable token makes long. These length checks live here,
    not in the LLM rule check, so the verdict never depends on model
    arithmetic."""
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
        if stripped.startswith(("```", "~~~")):
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


def _sentences(text: str) -> list[str]:
    """Split prose into whitespace-normalized sentences.

    Paragraphs are split first, so a heading does not run into the sentence
    below it. A merged pair matches nothing, which would hide the copy this
    check exists to find.
    """
    out: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        collapsed = re.sub(r"\s+", " ", block).strip()
        if not collapsed:
            continue
        out.extend(
            part.strip() for part in _SENTENCE_SPLIT_RE.split(collapsed) if part.strip()
        )
    return out


def strip_frontmatter(text: str) -> str:
    """Drop a leading YAML frontmatter block.

    The issue files open with one, and its keys and titles are not prose, so
    leaving them in makes a title collide with a PR body that legitimately
    names the same thing.
    """
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    return text if end == -1 else text[end + 5 :]


def linear_issue_bodies(text: str) -> list[tuple[str, str]]:
    """Return (slug, issue text) for every Linear issue the text references.

    Reads the local issue files rather than calling Linear, so the check stays
    deterministic and free. A slug with no file on disk is skipped.
    """
    found: list[tuple[str, str]] = []
    for slug in dict.fromkeys(LINEAR_REF_RE.findall(text)):
        if not LINEAR_ISSUE_ROOT.is_dir():
            break
        for path in LINEAR_ISSUE_ROOT.glob(f"**/linear/issues/{slug}-*.md"):
            try:
                found.append((slug, strip_frontmatter(path.read_text())))
            except OSError:
                continue
            break
    return found


def duplicated_from_linear(text: str, field: str) -> list[str]:
    """Flag sentences the PR body shares verbatim with its Linear issue."""
    body_sentences = [
        sentence
        for sentence in _sentences(text)
        if len(sentence.split()) >= DUPLICATED_SENTENCE_MIN_WORDS
    ]
    if not body_sentences:
        return []

    violations: list[str] = []
    for slug, issue in linear_issue_bodies(text):
        issue_sentences = set(_sentences(issue))
        shared = [s for s in body_sentences if s in issue_sentences]
        if not shared:
            continue
        shown = shared[:DUPLICATED_SENTENCE_REPORT_LIMIT]
        detail = "; ".join(f'"{s[:70]}..."' for s in shown)
        more = (
            f" (and {len(shared) - len(shown)} more)"
            if len(shared) > len(shown)
            else ""
        )
        violations.append(
            f"{field}: {len(shared)} sentence(s) copied verbatim from {slug} "
            f"{detail}{more} -- the issue says why the work exists, the PR body "
            "says what this diff needs a reviewer to know; do not paste one "
            "into the other"
        )
    return violations


# A straight-double-quoted span, which word-level checks skip so quoted
# material is reproduced verbatim (rules/typography.md).
QUOTED_SPAN_RE = re.compile(r'"[^"\n]*"')


def lint_text(
    text: str,
    field: str,
    allow_coauthor: bool = True,
    is_pr_body: bool = False,
    check_local_paths: bool = True,
    existing: frozenset[str] = frozenset(),
) -> list[str]:
    """
    Return a list of violation strings for the given text.

    `field` is included in each message so the caller knows which field of the
    tool input tripped the rule. `is_pr_body` enables the
    `Closes:`/`Fixes:`/`Resolves:` check, which is scoped to PR bodies only per
    rules/git.md. `check_local_paths` enables the local-path check AND the
    hard-wrap check; both apply only to outbound content (Bash heredocs / MCP
    payloads), not to in-repo dotfiles Markdown. `existing` holds the stripped
    lines already in the file being edited; word-level checks skip them so
    content edited in place keeps its wording, while punctuation checks still
    apply.
    """
    violations: list[str] = []

    if not allow_coauthor and COAUTHOR_RE.search(text):
        violations.append(
            f"{field}: contains `Co-Authored-By:` "
            "(forbidden in commits per rules/git.md)"
        )

    if CLAUDE_FOOTER_RE.search(text):
        violations.append(
            f"{field}: contains the `Generated with Claude Code` footer "
            "(never wanted on any surface; delete the line)"
        )

    if is_pr_body:
        violations.extend(duplicated_from_linear(text, field))

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
    scrubbed = scrub_code_spans(text.splitlines())
    for lineno, raw in enumerate(text.splitlines(), 1):
        stripped = raw.lstrip()
        if stripped.startswith(("```", "~~~")):
            in_code = not in_code
            continue
        if in_code:
            continue

        line = scrubbed[lineno - 1]
        # Word-level checks (slop, spelling, label colons) skip lines that
        # already exist in the file, blockquotes, and quoted spans.
        check_words = not (raw.strip() and raw.strip() in existing)
        prose = QUOTED_SPAN_RE.sub("", line)
        if stripped.startswith(">"):
            prose = ""

        for ch, name in SMART_QUOTES.items():
            if ch in line:
                violations.append(f"{field} line {lineno}: {name} (use straight quote)")
                break
        for slop_re, slop_label, slop_hint in AI_SLOP_PATTERNS:
            if not check_words:
                break
            m = slop_re.search(prose)
            context_re = AI_SLOP_CONTEXT.get(slop_label)
            if m and context_re is not None and not context_re.search(raw):
                m = None
            if m:
                violations.append(
                    f"{field} line {lineno}: AI slop, {slop_label} "
                    f"(`{m.group(0)}`; {slop_hint}; see rules/general.md)"
                )
        british = BRITISH_RE.search(prose) if check_words else None
        if british:
            found = british.group(1)
            american = BRITISH_SPELLINGS[found.lower()]
            if found[:1].isupper():
                american = american.capitalize()
            violations.append(
                f'{field} line {lineno}: British spelling "{found}" '
                f'(use "{american}" per rules/typography.md)'
            )
        if LIST_LEADIN_RE.match(raw):
            violations.append(
                f"{field} line {lineno}: list item uses `**X** -` "
                "(use `**X**:` per rules/typography.md)"
            )
        if check_words and LOWERCASE_AFTER_BOLD_COLON_RE.match(raw):
            violations.append(
                f"{field} line {lineno}: bullet has a lowercase word "
                "after the colon (always capitalize the first word "
                "after a colon per rules/typography.md; non-alphabetic "
                "starts like paths or code spans are naturally exempt, so "
                "wrap a repo name or SHA in backticks)"
            )
        if check_words and LOWERCASE_AFTER_LINK_COLON_RE.search(line):
            violations.append(
                f"{field} line {lineno}: link lead-in followed by "
                "a colon and a lowercase word (capitalize the first "
                "word after a label colon per rules/typography.md)"
            )
        if check_words and plain_label_colon_violation(raw):
            violations.append(
                f"{field} line {lineno}: bullet label followed by "
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
# `-m "$(cat <<'EOF' ... EOF)"` wraps a heredoc in a command
# substitution. The heredoc branch lints the content; redacting only the
# heredoc would leave the multi-line residue `$(cat \n)` as the -m
# value, which then fails the commit-message shape checks. Redact the
# whole wrapper down to an empty string so the flag loop skips it.
CAT_HEREDOC_SUBST_RE = re.compile(
    r"\$\(\s*cat\s*<<[-]?\s*['\"]?(\w+)['\"]?\s*\n.*?\n\s*\1\b\s*\)",
    re.DOTALL,
)
# A quoted message, body or title. `-am` and `-qm` are `git commit` flags
# combined with `-m`; only flags that take no value combine this way, so `-Sm`
# (a signing key named `m`) is not a message. `-b` and `-t` are gh's short
# `--body` and `--title`. Both short forms count only under the command that
# gives them that meaning (see `flag_kind`). A `--body-file` value is a path
# and is read separately.
FLAG_VALUE_RE = re.compile(
    r"(?:^|\s)(--?(?:m|message|body|title)|-[apsneioqvz]+m|-[bt])[=\s]+"
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
# A heredoc fed to a shell (`bash <<'EOF'`) is a script: the messages in it
# are found by reading it as a command of its own, not by linting it as prose.
SHELLS = frozenset({"bash", "dash", "ksh", "sh", "zsh"})
# Programs that run the command after them (`env FOO=1 python3`, `time -p
# python3`, `uv run python`), skipped when finding what reads a heredoc.
COMMAND_WRAPPERS = frozenset(
    {"command", "env", "exec", "nice", "nohup", "sudo", "time"}
)
COMMAND_RUNNERS = frozenset({"hatch", "pdm", "pipenv", "poetry", "rye", "uv"})
REDIRECT_RE = re.compile(r"\d*(?:<|>>?)&?\s*[^\s;|&<>()]*")


# Heredocs that are stdin for a loop or a text filter (`done <<'EOF'`,
# `sort <<'EOF'`) carry data, not outbound prose, even when the same command
# later runs `git commit`.
DATA_CONSUMERS = frozenset(
    {
        "done",
        "while",
        "read",
        "xargs",
        "sort",
        "uniq",
        "grep",
        "sed",
        "tr",
        "wc",
        "head",
        "tail",
        "cut",
        "column",
        "comm",
        "diff",
    }
)


def heredoc_command(command: str, heredoc_start: int) -> list[str]:
    """Words of the simple command that reads the heredoc at `heredoc_start`,
    from its program on. Leading variable assignments and wrappers such as
    `env`, `time` or `uv run`, with their flags, are skipped."""
    segment = re.split(r"[|;&\n]|\$\(", command[:heredoc_start])[-1]
    words = segment.split()
    while words:
        if re.fullmatch(r"\w+=\S*", words[0]):
            words = words[1:]
            continue
        if os.path.basename(words[0]) in COMMAND_WRAPPERS:
            words = words[1:]
        elif words[0] in COMMAND_RUNNERS and words[1:2] == ["run"]:
            words = words[2:]
        else:
            break
        while words and words[0].startswith("-"):
            words = words[1:]
    return words


def heredoc_program(command: str, heredoc_start: int) -> str:
    """Base name of the program that reads the heredoc at `heredoc_start`."""
    words = heredoc_command(command, heredoc_start)
    return os.path.basename(words[0]) if words else ""


def heredoc_args(command: str, heredoc_start: int) -> list[str]:
    """Arguments of the program that reads the heredoc at `heredoc_start`,
    without redirections such as `>/dev/null`."""
    words = heredoc_command(command, heredoc_start)[1:]
    return REDIRECT_RE.sub(" ", " ".join(words)).split()


def heredoc_feeds_data_consumer(command: str, heredoc_start: int) -> bool:
    """True when the program reading the heredoc at `heredoc_start` is a loop
    terminator or a text filter."""
    return heredoc_program(command, heredoc_start) in DATA_CONSUMERS


def heredoc_feeds_interpreter(command: str, heredoc_start: int) -> bool:
    """True when the program reading the heredoc at `heredoc_start` is a code
    interpreter, versioned (`python3.12`) or not."""
    program = heredoc_program(command, heredoc_start)
    return (
        program in CODE_INTERPRETERS
        or program.rstrip("0123456789.") in CODE_INTERPRETERS
    )


def heredoc_feeds_shell(command: str, heredoc_start: int) -> bool:
    """True when the heredoc at `heredoc_start` is the script a shell runs
    (`bash <<'EOF'`, `sh -s x <<'EOF'`), not the input of a script named on the
    command line (`bash run.sh <<'EOF'`)."""
    if heredoc_program(command, heredoc_start) not in SHELLS:
        return False
    args = heredoc_args(command, heredoc_start)
    return "-s" in args or all(arg.startswith("-") for arg in args)


# A `cat` heredoc redirected into a file (`cat > lint.yml <<'EOF'`), or a
# `tee` heredoc (`tee -a notes.md <<'EOF'`), is that file's content, not
# outbound prose, unless the same command reads the file back as a message
# (`git commit -F`, `--body-file`, `--input`, `body=@file`, `< file`,
# `$(cat file)`).
HEREDOC_REDIRECT_RE = re.compile(r"(?:^|\s)>>?\s*([^\s;|&<>()]+)")
FILE_READER_RE = re.compile(
    r"(?:(?:^|\s)(?:-[A-Za-z]*F|--file|--body-file|--input)[=\s]+"
    r"|=@|<\s*|\bcat\s+)"
    r"([^\s;|&<>()]+)"
)


def file_name(token: str) -> str:
    """Base name of a path token with its quotes dropped."""
    return os.path.basename(token.strip("'\""))


def heredoc_writes_other_file(command: str, heredoc_start: int) -> bool:
    """True when the heredoc at `heredoc_start` is `cat` output redirected into
    a file, or `tee` input written to files, that nothing else in the command
    reads back. Files compare by base name. A name held in a variable cannot be
    compared, so when the command reads any file back the heredoc stays
    a payload."""
    program = heredoc_program(command, heredoc_start)
    if program not in ("cat", "tee"):
        return False
    segment = re.split(r"[|;&\n]|\$\(", command[:heredoc_start])[-1]
    names = [file_name(t) for t in HEREDOC_REDIRECT_RE.findall(segment)]
    if program == "tee":
        names += map(file_name, heredoc_args(command, heredoc_start))
    if not names:
        return False
    found = FILE_READER_RE.findall(HEREDOC_RE.sub("", command))
    readers = [r for r in map(file_name, found) if r != "-"]
    opaque = any("$" in n or "`" in n for n in [*names, *readers])
    return not any(n in readers for n in names) and not (opaque and readers)


# `gh ... --body-file <path>`, `gh pr create -F <path>` and `git commit
# -F|--file <path>` point the command at a file rather than carrying the body
# inline. The Write call that created the file is linted only when it has
# a Markdown extension, so non-`.md` bodies (like `/tmp/commit-msg.txt`)
# bypass the lint entirely. Read the file contents at hook-eval time so the
# body is always inspected regardless of file extension. `-F` means
# a different thing under each command (see `extract_bash_content`).
PATH_TOKEN = r"(\"[^\"]*\"|'[^']*'|[^\s;|&<>()]+)"
BODY_FILE_FLAG_RE = re.compile(rf"(?:^|\s)--body-file[=\s]+{PATH_TOKEN}")
FILE_FLAG_RE = re.compile(rf"(?:^|\s)(?:--file|-[apsneioqvz]*F)[=\s]+{PATH_TOKEN}")
# `-m "$(cat body.md)"` sends the file's text as the value.
CAT_FILE_SUBST_RE = re.compile(rf"\$\(\s*(?:cat\s+|<\s*){PATH_TOKEN}\s*\)")


def read_file(token: str) -> str:
    """Text of the file a path token names, or an empty string when it cannot
    be read."""
    try:
        return Path(os.path.expanduser(token.strip("'\""))).read_text()
    except (OSError, UnicodeDecodeError):
        return ""


def resolve_value(value: str) -> str:
    """`value` with a whole-value `$(cat <file>)` replaced by the file's text,
    as the shell would pass it. Unchanged when the file cannot be read."""
    m = CAT_FILE_SUBST_RE.fullmatch(value)
    text = read_file(m.group(1)) if m else ""
    return text.rstrip("\n") if text else value


# Git accepts global options between `git` and the subcommand, so
# `git -c core.hooksPath=/dev/null commit` is a commit that a bare
# `git\s+commit` test misses. That miss skipped the `Co-Authored-By:`
# check (which fires on commit fields only) and linted the commit body as
# external content, where its 72-char wrap reads as a hard wrap.
#
# Every token between `git` and the subcommand must look like a flag or a
# known flag's value, so other subcommands (`git log ... commit`) stay
# out. Separate-value options are enumerated to keep each token's arity
# unambiguous, which bounds backtracking. `-c`/`-C` always take a value,
# so `git -c commit.gpgsign=false tag` does not read as a commit.
GIT_GLOBAL_OPT = (
    r"-[cC](?:=|\s+)\S+"
    r"|--(?:git-dir|work-tree|namespace|exec-path|config-env|super-prefix)"
    r"(?:=|\s+)\S+"
    r"|--[\w-]+(?:=\S+)?"
    r"|-(?![cC]\s)[A-Za-z]+"
)
# `(?![-\w])` keeps `git commit-graph` from reading as a commit.
GIT_COMMIT_RE = re.compile(rf"\bgit(?:\s+(?:{GIT_GLOBAL_OPT}))*\s+commit(?![-\w])")
# gh accepts `-R`/`--repo` before its subcommand and between `pr` and the
# subcommand (`gh -R o/r pr create`, `gh pr -R o/r comment 12`).
GH_OPT = r"(?:-R|--repo)(?:=|\s+)\S+"
GH_PREFIX = rf"\bgh(?:\s+(?:{GH_OPT}))*\s+"
GH_COMMAND_RE = re.compile(
    rf"{GH_PREFIX}(?:(pr|issue)(?:\s+(?:{GH_OPT}))*\s+(\w+)|api\b)"
)
# The `gh pr` and `gh issue` subcommands whose `-b`, `-t` and `-F` are a body,
# a title and a body file. Elsewhere they mean other things (`gh pr checkout
# -b` is a branch).
GH_TEXT_SUBCOMMANDS = frozenset({"comment", "create", "edit", "merge", "review"})
OUTBOUND_COMMAND_RE = re.compile(rf"{GIT_COMMIT_RE.pattern}|{GH_COMMAND_RE.pattern}")
QUOTED_RE = re.compile(r"\"(?:[^\"\\]|\\.)*\"|'[^']*'")
# What ends a simple command. The `&` of a redirection such as `2>&1` does not.
SEPARATOR_RE = re.compile(r"[;|\n]|(?<![<>])&")


def command_owners(command: str) -> list[tuple[int, int, int, str]]:
    """Start, end, end of its simple command, and kind of every `git commit`
    and `gh` command in `command`, in order. The kind is `commit`, `gh-text` (a
    subcommand in `GH_TEXT_SUBCOMMANDS`) or `gh`."""
    masked = QUOTED_RE.sub(
        lambda m: " " * len(m.group(0)), command.replace("\\\n", "  ")
    )
    found = [(m.start(), m.end(), "commit") for m in GIT_COMMIT_RE.finditer(command)]
    for m in GH_COMMAND_RE.finditer(command):
        kind = "gh-text" if m.group(2) in GH_TEXT_SUBCOMMANDS else "gh"
        found.append((m.start(), m.end(), kind))
    owners = []
    for start, end, kind in sorted(found):
        stop = SEPARATOR_RE.search(masked, end)
        owners.append((start, end, stop.start() if stop else len(command), kind))
    return owners


def flag_owner(
    owners: list[tuple[int, int, int, str]], flag_start: int
) -> tuple[int, str]:
    """Start and kind of the command whose flag starts at `flag_start`, or
    `(-1, "")` when no `git commit` or `gh` command precedes it in the same
    simple command."""
    for start, end, stop, kind in reversed(owners):
        if end <= flag_start:
            return (start, kind) if flag_start < stop else (-1, "")
    return -1, ""


def flag_kind(flag: str, owner: str) -> str:
    """What a `FLAG_VALUE_RE` value is under the command that owns it:
    `message`, `body`, `title`, or an empty string when that command gives the
    flag another meaning (`git commit -t` names a template)."""
    name = flag.lstrip("-")
    if name in ("m", "message"):
        return "message"
    if name in ("body", "title"):
        return name
    if owner == "commit" and name.endswith("m"):
        return "message"
    if owner == "gh-text":
        return {"b": "body", "t": "title"}.get(name, "")
    return ""


def heredoc_feeds_gh_input(command: str, heredoc_start: int) -> bool:
    """True when the heredoc at `heredoc_start` is the request body that
    `gh api --input -` reads."""
    segment = re.split(r"[|;&\n]|\$\(", command[:heredoc_start])[-1]
    return bool(
        re.search(r"\bgh\s+api\b", segment)
        and re.search(r"(?:^|\s)--input[=\s]+-", segment)
    )


def json_strings(text: str) -> list[tuple[str, str]] | None:
    """(path, value) for every string in `text` read as JSON, or None when
    `text` is not JSON."""
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return list(walk_strings(data))


def extract_bash_content(
    command: str,
) -> list[tuple[str, str, bool, bool, bool]]:
    """
    Extract text payloads from `git commit` and `gh {pr,issue} ...` commands.

    Returns a list of (field_label, text, is_commit, is_pr_body,
    is_full_commit). `is_commit` toggles the Co-Authored-By check; `is_pr_body`
    enables the `Closes:`/`Fixes:`/`Resolves:` check (PR bodies only per
    rules/git.md); `is_full_commit` enables the deterministic subject-length
    and body-wrap checks, so it is set only when the field is unambiguously an
    entire commit message. The `-m` values of one commit form one field, joined
    the way git joins them.
    """
    if not OUTBOUND_COMMAND_RE.search(command):
        return []

    is_commit = bool(GIT_COMMIT_RE.search(command))
    has_gh = bool(re.search(rf"{GH_PREFIX}(?:pr|issue|api)\b", command))
    is_pr_body = any(
        m.group(1) == "pr" and m.group(2) in ("create", "edit")
        for m in GH_COMMAND_RE.finditer(command)
    )
    fields: list[tuple[str, str, bool, bool, bool]] = []

    # A heredoc in a commit-only command is the whole commit message. In
    # a compound command that also runs gh, ownership is ambiguous, so
    # the length checks stay off rather than risk running the commit
    # subject rule against a PR body.
    heredoc_is_commit = is_commit and not has_gh
    for m in HEREDOC_RE.finditer(command):
        if heredoc_feeds_shell(command, m.start()):
            fields.extend(extract_bash_content(m.group(2)))
            continue
        if heredoc_feeds_interpreter(command, m.start()):
            continue
        if heredoc_feeds_data_consumer(command, m.start()):
            continue
        if heredoc_writes_other_file(command, m.start()):
            continue
        label = f"heredoc<{m.group(1)}>"
        # A JSON request body is linted one string at a time, so its syntax
        # is never read as wrapped prose.
        strings = None
        if heredoc_feeds_gh_input(command, m.start()):
            strings = json_strings(m.group(2))
        if strings is not None:
            fields.extend(
                (f"{label} {path}", text, is_commit, is_pr_body, False)
                for path, text in strings
            )
            continue
        fields.append((label, m.group(2), is_commit, is_pr_body, heredoc_is_commit))

    redacted = HEREDOC_RE.sub("", CAT_HEREDOC_SUBST_RE.sub("", command))
    owners = command_owners(redacted)
    flags: list[tuple[str, str, str, int]] = []
    for m in FLAG_VALUE_RE.finditer(redacted):
        start, owner = flag_owner(owners, m.start())
        kind = flag_kind(m.group(1), owner)
        value = resolve_value(m.group(3) if m.group(3) is not None else m.group(4))
        if kind and value:
            commit = start if kind == "message" and owner == "commit" else -1
            flags.append((m.group(1), value, kind, commit))
    messages: dict[int, list[tuple[str, str]]] = {}
    for flag, value, _, commit in flags:
        if commit != -1:
            messages.setdefault(commit, []).append((flag, value))
    for flag, value, kind, commit in flags:
        if commit == -1:
            # The body of a PR is what carries the autoclose keywords; the
            # title is too short to bother filtering, but applying the check
            # there is also harmless.
            is_message = is_commit and kind == "message"
            is_body = is_pr_body and kind == "body"
            fields.append((f"arg {flag}", value, is_message, is_body, False))
            continue
        # Git joins the `-m` values of one commit as paragraphs: the first is
        # the subject and each later one a body paragraph. A variable among
        # them hides the message, so the values stay apart to be blocked.
        parts = messages.pop(commit, [])
        if any(is_bypass_value(part) for _, part in parts):
            fields.extend((f"arg {f}", part, True, False, False) for f, part in parts)
        elif parts:
            text = "\n\n".join(part for _, part in parts)
            fields.append((f"arg {flag}", text, True, False, True))
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
    # the body is linted regardless of its extension. Silent when the file
    # cannot be read so a missing path does not block the command (gh itself
    # will surface the file-not-found error at execution time). A quoted
    # variable hides the body, so it is blocked like a variable `--body`.
    for m in BODY_FILE_FLAG_RE.finditer(redacted):
        path = m.group(1).strip("'\"")
        if path != m.group(1) and BARE_VAR_RE.match(path):
            fields.append(("arg --body-file", path, False, is_pr_body, False))
            continue
        text = read_file(path)
        if text:
            fields.append((f"arg --body-file {path}", text, False, is_pr_body, False))

    # `-F` is the message file under `git commit` and the body file under gh's
    # text subcommands, but a field under `gh api`. An `-F` that no command
    # owns is read as the commit message whenever the command commits.
    for m in FILE_FLAG_RE.finditer(redacted):
        path = m.group(1).strip("'\"")
        _, owner = flag_owner(owners, m.start())
        if owner == "gh-text":
            is_message = False
        elif owner == "commit" or (not owner and is_commit):
            is_message = True
        else:
            continue
        text = read_file(path)
        if text:
            is_body = is_pr_body and not is_message
            fields.append((f"arg -F {path}", text, is_message, is_body, is_message))

    return fields


# A heredoc whose marker line may carry a trailing redirect, as in
# `cat <<'EOF' >> notes.md`, which HEREDOC_RE does not match.
FILE_HEREDOC_RE = re.compile(
    r"<<-?\s*(['\"]?)(\w+)\1([^\n]*)\n(.*?)\n\s*\2\b",
    re.DOTALL,
)
MARKDOWN_TARGET_RE = re.compile(
    r"(?:>>?|\btee(?:\s+-a)?)\s*"
    r"(?:'([^'$]+\.(?:md|markdown))'"
    r"|\"([^\"$]+\.(?:md|markdown))\""
    r"|([^\s'\"$;|&<>]+\.(?:md|markdown))(?=[\s)]|$))"
)


def extract_markdown_heredocs(command: str) -> list[tuple[str, str, str]]:
    """
    Return (field_label, text, path) for each heredoc a Bash command writes
    into a Markdown file (`cat >> f.md <<'EOF'`, `tee -a f.md <<EOF`).

    Only the heredoc body is returned, so a shared file's earlier entries are
    not linted. Targets held in shell variables are skipped.
    """
    fields: list[tuple[str, str, str]] = []
    for m, raw in _markdown_heredoc_matches(command):
        path = os.path.abspath(os.path.expanduser(raw))
        fields.append((f"heredoc<{m.group(2)}> into {raw}", m.group(4), path))
    return fields


def _markdown_heredoc_matches(
    command: str,
) -> Iterable[tuple[re.Match[str], str]]:
    for m in FILE_HEREDOC_RE.finditer(command):
        if heredoc_feeds_interpreter(command, m.start()):
            continue
        owner = re.split(r"[;&\n]|\$\(", command[: m.start()])[-1] + m.group(3)
        target = MARKDOWN_TARGET_RE.search(owner)
        if target is not None:
            yield m, next(g for g in target.groups() if g)


def autofix_markdown_heredocs(command: str) -> str:
    """Return `command` with label-colon fixes applied inside each heredoc it
    writes into a Markdown file. Heredoc bodies are literal text, so the
    rewrite cannot change how the shell parses the command."""
    parts: list[str] = []
    last = 0
    for m, _ in _markdown_heredoc_matches(command):
        parts += [command[last : m.start(4)], autofix_label_colons(m.group(4))]
        last = m.end(4)
    return "".join(parts) + command[last:]


def is_bypass_value(value: str) -> str | None:
    """Return a reason string if `value` is a lint-bypassing reference (bare
    `$var` expansion), or None if it's a real string. A bare expansion reaches
    `lint_text` as the literal `$var`, not as its expanded content, so the body
    text is never actually inspected."""
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
_HOME = Path.home()
IN_REPO_PREFIXES = tuple(
    f"{_HOME / name}/"
    for name in (
        ".claude",
        ".claude-fh",
        "w",
        "nickolashkraus",
        "Function-Health",
        "Function-Health-Terraform-Modules",
        "infrable-io",
        "grind-rip",
    )
)


def is_in_repo_path(path: str) -> bool:
    return any(path.startswith(p) for p in IN_REPO_PREFIXES)


def is_linear_mirror_path(path: str) -> bool:
    """Linear copies are stored verbatim, so typography rules do not apply."""
    return (
        path.startswith(f"{LINEAR_ISSUE_ROOT}/")
        and "/linear/" in path
        and not path.endswith("/README.md")
    )


def extract_fields(
    tool_name: str, tool_input: dict
) -> list[tuple[str, str, bool, bool, bool, bool]]:
    """
    Return a list of (field_label, text, allow_coauthor, is_pr_body,
    check_local_paths, is_full_commit) tuples to lint.

    `allow_coauthor` is False only for commit messages, where the rule forbids
    `Co-Authored-By:` lines. `is_pr_body` is True only for PR body content,
    where the `Closes:`/`Fixes:`/`Resolves:` rule applies. `check_local_paths`
    is False for in-repo Markdown edits, where references to local paths are
    legitimate. `is_full_commit` enables the deterministic commit
    subject-length and body-wrap checks.
    """
    out: list[tuple[str, str, bool, bool, bool, bool]] = []

    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        if isinstance(cmd, str):
            for label, text, is_commit, is_pr_body, is_full in extract_bash_content(
                cmd
            ):
                out.append((label, text, not is_commit, is_pr_body, True, is_full))
            for label, text, path in extract_markdown_heredocs(cmd):
                out.append((label, text, True, False, not is_in_repo_path(path), False))
        return out

    if tool_name in ("Edit", "Write"):
        file_path = tool_input.get("file_path", "")
        if not isinstance(file_path, str):
            return out
        if not file_path.endswith(MARKDOWN_EXTENSIONS):
            return out
        if is_linear_mirror_path(file_path):
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


def existing_file_lines(tool_name: str, tool_input: dict) -> frozenset[str]:
    """Stripped non-blank lines of the file an Edit or Write targets, so
    word-level checks can tell content edited in place from new text."""
    if tool_name not in ("Edit", "Write"):
        return frozenset()
    path = tool_input.get("file_path")
    if not isinstance(path, str):
        return frozenset()
    try:
        text = Path(path).read_text()
    except (OSError, UnicodeDecodeError):
        return frozenset()
    return frozenset(line.strip() for line in text.splitlines() if line.strip())


def collect_violations(tool_name: str, tool_input: dict) -> list[str]:
    """Run every lint over the tool's outbound fields and return the flat list
    of violation strings."""
    violations: list[str] = []
    existing = existing_file_lines(tool_name, tool_input)
    for (
        label,
        text,
        allow_coauthor,
        is_pr_body,
        check_local_paths,
        is_full,
    ) in extract_fields(tool_name, tool_input):
        if not isinstance(text, str):
            continue
        bypass_reason = is_bypass_value(text)
        if bypass_reason is not None:
            violations.append(f"{label}: {bypass_reason}")
            continue
        violations.extend(
            lint_text(
                text,
                label,
                allow_coauthor=allow_coauthor,
                is_pr_body=is_pr_body,
                check_local_paths=check_local_paths,
                existing=existing,
            )
        )
        if is_full:
            violations.extend(lint_commit_message(text, label))
    return violations


def try_autofix_input(tool_name: str, tool_input: dict) -> dict | None:
    """Return a modified tool_input with label-colon violations auto-fixed, or
    None when nothing safe to fix applies. Scoped to Markdown content (Edit,
    Write, and Bash heredocs written into a `.md` file), where capitalizing the
    word after a label colon is an unambiguous fix; Bash commit/PR bodies are
    left to block so their quoting is never rewritten."""
    if tool_name == "Bash":
        command = tool_input.get("command")
        if not isinstance(command, str):
            return None
        fixed_command = autofix_markdown_heredocs(command)
        if fixed_command == command:
            return None
        return {**tool_input, "command": fixed_command}
    if tool_name not in ("Edit", "Write"):
        return None
    key = "new_string" if tool_name == "Edit" else "content"
    original = tool_input.get(key)
    if not isinstance(original, str) or not original:
        return None
    fixed = autofix_label_colons(original, existing_file_lines(tool_name, tool_input))
    if fixed == original:
        return None
    new_input = dict(tool_input)
    new_input[key] = fixed
    return new_input


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    if not isinstance(tool_input, dict):
        return 0

    if not extract_fields(tool_name, tool_input):
        return 0

    all_violations = collect_violations(tool_name, tool_input)

    log(f"CHECK tool={tool_name} violations={len(all_violations)}")
    for v in all_violations:
        log(f"  VIOLATION {v}")

    if not all_violations:
        return 0

    # Auto-fix the capitalize-after-label-colon case rather than
    # block-and-retry, but only when the fix fully resolves every flagged
    # issue. If any non-auto-fixable violation remains (smart quote, hard
    # wrap), fall through to the block so the agent sees all of them.
    fixed_input = try_autofix_input(tool_name, tool_input)
    if fixed_input is not None and not collect_violations(tool_name, fixed_input):
        log("AUTOFIX label-colon capitalization applied")
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "allow",
                        "updatedInput": fixed_input,
                        "permissionDecisionReason": (
                            "Auto-capitalized the word after a label colon "
                            "(rules/typography.md)."
                        ),
                    }
                }
            )
        )
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
