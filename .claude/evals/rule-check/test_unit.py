#!/usr/bin/env python3
"""
Deterministic unit tests for ~/.claude/hooks/rule-check.py.

Covers the parts that don't spawn Opus: payload extraction from Bash and MCP
tool inputs, the override sentinel regex, the body-file resolver, and the
load_rules concatenation. These run in milliseconds, cost nothing, and catch
the bugs CI is actually good at catching.

Run: python3 .claude/evals/rule-check/test_unit.py

The end-to-end Opus eval lives in eval.py and is not run from here.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

HOOK_PATH = Path(__file__).resolve().parents[2] / "hooks" / "rule-check.py"
SETTINGS_PATH = HOOK_PATH.parents[1] / "settings.json"

spec = importlib.util.spec_from_file_location("rule_check", HOOK_PATH)
assert spec is not None and spec.loader is not None, f"cannot load {HOOK_PATH}"
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)


_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  [PASS] {name}")
    else:
        _failures.append(f"{name}: {detail}")
        print(f"  [FAIL] {name}  {detail}")


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def verdict_json(verdict: str, violations: list[dict]) -> str:
    return json.dumps(
        {"structured_output": {"verdict": verdict, "violations": violations}}
    )


class FakeSubprocess:
    """Stands in for the hook's `subprocess` module so no test reaches the
    `claude` CLI. Records each call and answers with `stdout`."""

    TimeoutExpired = subprocess.TimeoutExpired

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.returncode = 0
        self.stdout = verdict_json("pass", [])
        self.timeout = False

    def run(self, args: list[str], **kwargs) -> subprocess.CompletedProcess:
        self.calls.append({"args": args, **kwargs})
        if self.timeout:
            raise subprocess.TimeoutExpired(args, kwargs.get("timeout", 0))
        return subprocess.CompletedProcess(args, self.returncode, self.stdout, "")


@contextlib.contextmanager
def sandbox(rules: str = "Never use smart quotes.\n"):
    """Point the hook's rule, log and cache paths at a temp dir and swap in
    FakeSubprocess, so a test never touches ~/.claude or calls a model."""
    names = ("RULES_DIR", "CLAUDE_MD", "LOG_FILE", "CACHE_FILE", "subprocess")
    saved = {name: getattr(rc, name) for name in names}
    env_names = ("CLAUDE_RULE_CHECK_DISABLE", "CLAUDE_RULE_CHECK_NO_CACHE")
    saved_env = {name: os.environ.pop(name, None) for name in env_names}
    fake = FakeSubprocess()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        rc.RULES_DIR = root / "rules"
        rc.RULES_DIR.mkdir()
        if rules:
            (rc.RULES_DIR / "general.md").write_text(rules)
        rc.CLAUDE_MD = root / "CLAUDE.md"
        rc.LOG_FILE = root / "rule-check.log"
        rc.CACHE_FILE = root / "rule-check-cache.json"
        rc.subprocess = fake
        try:
            yield fake
        finally:
            for name, value in saved.items():
                setattr(rc, name, value)
            for name, value in saved_env.items():
                os.environ.pop(name, None)
                if value is not None:
                    os.environ[name] = value


def run_main(payload: dict | str) -> tuple[int, str]:
    """Run the hook's main() with `payload` on stdin; return the exit code and
    stderr."""
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    saved = sys.stdin, sys.stderr
    sys.stdin, sys.stderr = io.StringIO(stdin), io.StringIO()
    try:
        return rc.main(), sys.stderr.getvalue()
    finally:
        sys.stdin, sys.stderr = saved


def test_extract_bash_payloads_heredoc_commit() -> None:
    section("extract_bash_payloads: heredoc commit body")
    cmd = (
        "git commit -m \"$(cat <<'EOF'\n"
        "Add upgrade gate\n\n"
        "Introduces upgrade_eligible column on members.\n"
        "EOF\n"
        ')"'
    )
    out = rc.extract_bash_payloads(cmd)
    check("returns one heredoc payload", len(out) == 1, f"got {out!r}")
    if out:
        label, text = out[0]
        check(
            "surface is git commit",
            "git commit" in label,
            f"label={label!r}",
        )
        check(
            "body contains heredoc content",
            "upgrade_eligible" in text,
            f"text={text[:120]!r}",
        )


def test_extract_bash_payloads_heredoc_forms() -> None:
    section("extract_bash_payloads: <<- heredocs and several heredocs per command")
    out = rc.extract_bash_payloads(
        "git commit -F- <<-EOF\n\tAdd the retry guard\n\tEOF"
    )
    check(
        "<<- heredoc with an indented terminator extracted",
        [t.strip() for _, t in out] == ["Add the retry guard"],
        f"got {out!r}",
    )
    cmd = (
        "git commit -F- <<'EOF'\nAdd the retry guard\nEOF\n"
        "gh pr comment 12 --body-file - <<'EOF'\nAdds the retry guard.\nEOF"
    )
    texts = [t for lbl, t in rc.extract_bash_payloads(cmd) if "heredoc" in lbl]
    check(
        "each heredoc is its own payload",
        texts == ["Add the retry guard", "Adds the retry guard."],
        f"got {texts!r}",
    )
    cmd = (
        "gh pr create --title 'Add the retry guard' --body-file - <<'EOF'\n"
        "Rerun with `gh pr comment 12 --body 'Retried after the fix.'`.\n"
        "EOF"
    )
    texts = [t for _, t in rc.extract_bash_payloads(cmd)]
    check(
        "a flag quoted inside a heredoc body is not its own payload",
        "Retried after the fix." not in texts,
        f"got {texts!r}",
    )


def test_extract_bash_payloads_inline_m_flag() -> None:
    section("extract_bash_payloads: inline -m flag")
    cmd = "git commit -m 'BYB-1234: Add Upgrade Gate Column'"
    out = rc.extract_bash_payloads(cmd)
    check("returns one payload", len(out) == 1, f"got {out!r}")
    if out:
        _, text = out[0]
        check(
            "extracted text matches",
            text == "BYB-1234: Add Upgrade Gate Column",
            f"text={text!r}",
        )


def test_extract_bash_payloads_flag_spellings() -> None:
    section("extract_bash_payloads: --message, --flag=value, quoting and wrappers")
    cases = [
        ("git commit --message 'Add the retry guard'", ["Add the retry guard"]),
        (
            "gh pr create --title='Add the retry guard' --body='Adds the guard.'",
            ["Add the retry guard", "Adds the guard."],
        ),
        ('git commit -m "Add the \\"retry\\" guard"', ['Add the \\"retry\\" guard']),
        (
            "git mv draft-title \"Final Title.md\" && git commit -m 'Rename the draft'",
            ["Rename the draft"],
        ),
        ('git commit -m "${COMMIT_MESSAGE}"', []),
        (
            "gh pr create --title 'Add the retry guard' --body \" $(cat body.md)\"",
            ["Add the retry guard"],
        ),
    ]
    for cmd, expected in cases:
        texts = [t for _, t in rc.extract_bash_payloads(cmd)]
        check(f"{cmd!r} -> {expected!r}", texts == expected, f"got {texts!r}")


def test_extract_bash_payloads_subject_vs_body_m_flags() -> None:
    section("extract_bash_payloads: first -m is subject, rest are body")
    cmd = "git commit -m 'Add the thing' -m 'Adds a body paragraph here.'"
    out = rc.extract_bash_payloads(cmd)
    labels = [lbl for lbl, _ in out]
    check(
        "subject labeled 'git commit message arg -m'",
        any(lbl == "git commit message arg -m" for lbl in labels),
        f"labels={labels!r}",
    )
    check(
        "body labeled 'git commit message body arg -m'",
        any(lbl == "git commit message body arg -m" for lbl in labels),
        f"labels={labels!r}",
    )


def test_extract_bash_payloads_gh_pr_create() -> None:
    section("extract_bash_payloads: gh pr create with --body and --title")
    cmd = (
        "gh pr create --title 'BYB-1234: Add Gate' "
        "--body 'Adds the upgrade gate column to members.'"
    )
    out = rc.extract_bash_payloads(cmd)
    check("returns two payloads (title + body)", len(out) == 2, f"got {out!r}")
    labels = [lbl for lbl, _ in out]
    check(
        "labels include arg --title and arg --body",
        any("--title" in lbl for lbl in labels)
        and any("--body" in lbl for lbl in labels),
        f"labels={labels!r}",
    )


def test_extract_bash_payloads_gh_pr_comment() -> None:
    section("extract_bash_payloads: gh pr comment")
    cmd = "gh pr comment 1234 --body 'Reproduced; see PR #5678 for the fix.'"
    out = rc.extract_bash_payloads(cmd)
    check("returns one payload", len(out) == 1, f"got {out!r}")
    if out:
        label, _ = out[0]
        check("surface is GitHub PR", "GitHub PR" in label, f"label={label!r}")


def test_extract_bash_payloads_gh_issue_create() -> None:
    section("extract_bash_payloads: gh issue create")
    cmd = (
        "gh issue create --title 'Track followups' "
        "--body 'Loose ends from the upgrade-gate rollout.'"
    )
    out = rc.extract_bash_payloads(cmd)
    check("returns two payloads (title + body)", len(out) == 2, f"got {out!r}")
    labels = [lbl for lbl, _ in out]
    check(
        "surface is GitHub issue",
        all("GitHub issue" in lbl for lbl in labels),
        f"labels={labels!r}",
    )


def test_extract_bash_payloads_gh_api() -> None:
    section("extract_bash_payloads: gh api with -f body=")
    cmd = (
        "gh api repos/org/repo/issues/123/comments "
        "-f body='Closing as resolved by [PR #200](https://github.com/x/y/pull/200).'"
    )
    out = rc.extract_bash_payloads(cmd)
    check("returns one payload", len(out) == 1, f"got {out!r}")
    if out:
        _, text = out[0]
        check(
            "extracted text matches",
            "Closing as resolved" in text,
            f"text={text!r}",
        )


def test_extract_bash_payloads_gh_api_field_spellings() -> None:
    section("extract_bash_payloads: gh api --raw-field, --field and double quotes")
    cmd = (
        "gh api repos/org/repo/issues --raw-field title='Track the retry guard' "
        '--field body="Adds the \\"retry\\" guard."'
    )
    out = rc.extract_bash_payloads(cmd)
    check(
        "both fields extracted under the GitHub API surface",
        out
        == [
            ("GitHub API -f title", "Track the retry guard"),
            ("GitHub API -f body", 'Adds the \\"retry\\" guard.'),
        ],
        f"got {out!r}",
    )
    cmd = (
        "gh api repos/org/repo/issues/1/comments "
        "-f body=\"$(cat <<'EOF'\nAdds the retry guard.\nEOF\n)\""
    )
    out = rc.extract_bash_payloads(cmd)
    check(
        "heredoc wrapper residue is not a second payload",
        [t for _, t in out] == ["Adds the retry guard."],
        f"got {out!r}",
    )


def test_extract_bash_payloads_commit_F_flag() -> None:
    section("extract_bash_payloads: git commit -F reads file content")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Add upgrade gate\n\nIntroduces the membership upgrade flag.\n")
        path = f.name
    try:
        cmd = f"git commit -F {path}"
        out = rc.extract_bash_payloads(cmd)
        labels = [lbl for lbl, _ in out]
        texts = [t for _, t in out]
        check(
            "extracts file content as commit body",
            any("membership upgrade flag" in t for t in texts),
            f"texts={texts!r}",
        )
        check(
            "label is git commit -F <path>",
            any("git commit message -F" in lbl for lbl in labels),
            f"labels={labels!r}",
        )
    finally:
        Path(path).unlink()


def test_extract_bash_payloads_commit_long_file_flag() -> None:
    section("extract_bash_payloads: git commit --file reads file content")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Fix race in upgrade flag\n\nReorders the locking.")
        path = f.name
    try:
        cmd = f"git commit --file {path}"
        out = rc.extract_bash_payloads(cmd)
        texts = [t for _, t in out]
        check(
            "extracts file content via --file",
            any("Reorders the locking" in t for t in texts),
            f"texts={texts!r}",
        )
    finally:
        Path(path).unlink()


def test_extract_bash_payloads_gh_api_minus_F_not_treated_as_commit_file() -> None:
    section(
        "extract_bash_payloads: gh api -F field=value is NOT treated as a "
        "commit-file path (no collision)"
    )
    cmd = "gh api repos/org/repo/issues -F body='Long enough body text to extract.'"
    out = rc.extract_bash_payloads(cmd)
    labels = [lbl for lbl, _ in out]
    check(
        "no -F file payload produced",
        not any(lbl.endswith("-F field=value") for lbl in labels),
        f"labels={labels!r}",
    )
    check(
        "regular gh api -f body extraction still works",
        any("-f body" in lbl for lbl in labels),
        f"labels={labels!r}",
    )


def test_extract_bash_payloads_body_file() -> None:
    section("extract_bash_payloads: --body-file reads file content")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("Body content from disk for the test fixture.")
        path = f.name
    try:
        cmd = f"gh pr create --title 'Test' --body-file {path}"
        out = rc.extract_bash_payloads(cmd)
        labels = [lbl for lbl, _ in out]
        texts = [t for _, t in out]
        check(
            "includes the --body-file payload",
            any("Body content from disk" in t for t in texts),
            f"texts={texts!r}",
        )
        check(
            "label references the file path",
            any("--body-file" in lbl for lbl in labels),
            f"labels={labels!r}",
        )
    finally:
        Path(path).unlink()


def test_extract_bash_payloads_file_path_spellings() -> None:
    section("extract_bash_payloads: quoted, `=` and `~` paths to message files")
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "msg.md"
        path.write_text("Adds the retry guard from a file.")
        saved_home, saved_cwd = os.environ.get("HOME"), os.getcwd()
        os.environ["HOME"] = tmpdir
        try:
            for cmd in (
                f"gh pr create --title 'Add guard' --body-file='{path}'",
                "gh pr create --title 'Add guard' --body-file ~/msg.md",
                f"gh api repos/org/repo/issues --field title=@'{path}'",
                "gh api repos/org/repo/issues -F body=@~/msg.md",
                f"git commit --file='{path}'",
                "git commit -F ~/msg.md",
            ):
                texts = [t for _, t in rc.extract_bash_payloads(cmd)]
                check(
                    f"{cmd.replace(tmpdir, '<tmp>')!r} reads the file",
                    "Adds the retry guard from a file." in texts,
                    f"got {texts!r}",
                )
            os.chdir(tmpdir)
            Path("-").write_text("Contents of a file literally named dash.")
            out = rc.extract_bash_payloads(
                "gh api repos/o/r/issues -F body=@- < msg.md"
            )
            check("@- reads stdin, never a file named -", out == [], f"got {out!r}")
        finally:
            os.chdir(saved_cwd)
            os.environ.pop("HOME", None)
            if saved_home is not None:
                os.environ["HOME"] = saved_home


def test_extract_bash_payloads_unrelated_command() -> None:
    section("extract_bash_payloads: unrelated command short-circuits")
    out = rc.extract_bash_payloads("ls -la /tmp")
    check("returns empty list", out == [], f"got {out!r}")
    out = rc.extract_bash_payloads("python3 report.py --title 'Weekly retry report'")
    check(
        "ungated command with a --title flag returns empty", out == [], f"got {out!r}"
    )


def test_extract_mcp_payloads_linear() -> None:
    section("extract_mcp_payloads: Linear save_issue")
    out = rc.extract_mcp_payloads(
        "mcp__linear__save_issue",
        {
            "title": "Add Idempotency Key to Webhook Handler",
            "description": (
                "## Overview\n\nAdds idempotency-key support to the Stripe "
                "webhook handler so retried deliveries do not double-record."
            ),
        },
    )
    texts = [t for _, t in out]
    check(
        "extracts description (title too short, filtered)",
        any("idempotency-key" in t for t in texts),
        f"texts={texts!r}",
    )


def test_extract_mcp_payloads_nested_notion() -> None:
    section("extract_mcp_payloads: Notion nested pages array")
    out = rc.extract_mcp_payloads(
        "mcp__notion__notion-create-pages",
        {
            "pages": [
                {
                    "properties": {"title": "Rollout Plan"},
                    "content": (
                        "## Overview\n\nCaptures the rollout plan for the "
                        "membership-upgrade feature flag."
                    ),
                }
            ]
        },
    )
    texts = [t for _, t in out]
    check(
        "walks into nested array element",
        any("rollout plan" in t for t in texts),
        f"texts={texts!r}",
    )
    labels = [lbl for lbl, _ in out]
    check(
        "label includes array index path",
        any("pages[0]" in lbl for lbl in labels),
        f"labels={labels!r}",
    )


def test_extract_mcp_payloads_short_values_filtered() -> None:
    section("extract_mcp_payloads: filters values < 20 chars")
    out = rc.extract_mcp_payloads(
        "mcp__linear__save_issue",
        {"title": "Short", "state": "open"},
    )
    check("short values filtered out", out == [], f"got {out!r}")


def test_extract_mcp_payloads_length_boundary() -> None:
    section("extract_mcp_payloads: 20 chars is the shortest value checked")
    out = rc.extract_mcp_payloads("mcp__linear__save_comment", {"body": "a" * 19})
    check("19 chars filtered", out == [], f"got {out!r}")
    out = rc.extract_mcp_payloads("mcp__linear__save_comment", {"body": "a" * 20})
    check(
        "20 chars extracted, labeled with the bare tool name",
        out == [("save_comment body", "a" * 20)],
        f"got {out!r}",
    )


def test_extract_mcp_payloads_non_prose_fields_filtered() -> None:
    section("extract_mcp_payloads: filters non-prose identifier fields")
    out = rc.extract_mcp_payloads(
        "mcp__linear__save_issue",
        {
            "team": "Membership Management",
            "project": "Subscription Lifecycle Overhaul",
            "labels": ["Needs Triage and Estimation"],
            "links": [{"url": "https://linear.app/functionhealth/issue/BYB-1337"}],
            "description": (
                "## Overview\n\nAdds idempotency-key support to the Stripe "
                "webhook handler so retried deliveries do not double-record."
            ),
        },
    )
    labels = [lbl for lbl, _ in out]
    check(
        "scalar identifier field filtered",
        not any("team" in lbl for lbl in labels),
        f"labels={labels!r}",
    )
    check(
        "identifier inside array filtered",
        not any("labels" in lbl for lbl in labels),
        f"labels={labels!r}",
    )
    check(
        "identifier nested under array element filtered",
        not any("url" in lbl for lbl in labels),
        f"labels={labels!r}",
    )
    check(
        "prose field still extracted",
        any("description" in lbl for lbl in labels),
        f"labels={labels!r}",
    )


def test_extract_mcp_payloads_every_identifier_field() -> None:
    section("extract_mcp_payloads: every identifier field, as the tools spell it")
    fields = (
        "accountId",
        "addReleases",
        "assignee",
        "bcc",
        "blockedBy",
        "blocks",
        "calendarId",
        "cc",
        "channel",
        "channelId",
        "comment_id",
        "cursor",
        "cycle",
        "delegate",
        "draftId",
        "dueDate",
        "duplicateOf",
        "estimate",
        "eventId",
        "id",
        "instructions_version",
        "labels",
        "messageId",
        "milestone",
        "pageId",
        "parent",
        "parentId",
        "priority",
        "project",
        "query",
        "relatedTo",
        "removeBlockedBy",
        "removeBlocks",
        "removeReleases",
        "removeRelatedTo",
        "replyThreadId",
        "replyToMessageId",
        "setReleases",
        "skill",
        "state",
        "team",
        "to",
        "url",
    )
    prose = "The retry budget resets every hour, so a burst cannot page twice."
    for name in ("to", "cc", "skill", "state", "url", "id"):
        for shape in (
            {"properties": {name: prose}},
            {"pages": [{"properties": {name: prose}}]},
        ):
            out = rc.extract_mcp_payloads("mcp__notion__notion-create-pages", shape)
            check(
                f"a page property named {name} is sent ({next(iter(shape))})",
                [text for _, text in out] == [prose],
                f"got {out!r}",
            )
    for name in fields:
        value = "0b7f9c2e-5d4a-4c1e-9f3a-2b6d8e1a7c55"
        out = rc.extract_mcp_payloads("mcp__linear__save_issue", {name: value})
        check(f"{name} filtered", out == [], f"got {out!r}")


def test_field_name_paths() -> None:
    section("field_name: bare field name from a walk_strings path")
    cases = [
        ("description", "description"),
        ("links[0].title", "title"),
        ("labels[0]", "labels"),
        ("pages[0].properties.title", "title"),
        ("Team", "team"),
        ("<root>", "<root>"),
    ]
    for path, expected in cases:
        got = rc.field_name(path)
        check(f"{path!r} -> {expected!r}", got == expected, f"got {got!r}")


def test_skip_sentinel_html_comment() -> None:
    section("SKIP_RE: HTML comment with reason")
    m = rc.SKIP_RE.search(
        'before <!-- rule-check: skip reason="false positive" --> after'
    )
    check("matches", m is not None, "no match")
    if m:
        check(
            "captures reason",
            m.group(1) == "false positive",
            f"got {m.group(1)!r}",
        )


def test_skip_sentinel_hash_comment() -> None:
    section("SKIP_RE: hash comment")
    m = rc.SKIP_RE.search('# rule-check: skip reason="intentional"')
    check("matches", m is not None, "no match")


def test_skip_sentinel_slash_comment() -> None:
    section("SKIP_RE: // comment")
    m = rc.SKIP_RE.search("// rule-check: skip")
    check("matches without reason", m is not None, "no match")


def test_skip_sentinel_case_insensitive() -> None:
    section("SKIP_RE: matches in any case")
    m = rc.SKIP_RE.search("<!-- RULE-CHECK: SKIP -->")
    check("matches uppercase", m is not None, "no match")


def test_skip_sentinel_no_match() -> None:
    section("SKIP_RE: no match on unrelated text")
    m = rc.SKIP_RE.search("nothing to see here")
    check("does not match", m is None, f"got {m!r}")


def test_gated_mcp_matches() -> None:
    section("GATED_MCP_RE: matches expected tools")
    cases = [
        ("mcp__linear__save_issue", True),
        ("mcp__linear__save_comment", True),
        ("mcp__notion__notion-create-pages", True),
        ("mcp__notion__notion-update-page", True),
        ("mcp__notion__notion-create-comment", True),
        ("mcp__claude_ai_Slack__slack_send_message_draft", True),
        ("mcp__claude_ai_Slack__slack_send_message", True),
        ("mcp__claude_ai_Slack__slack_create_canvas", True),
        ("mcp__claude_ai_Slack__slack_update_canvas", True),
        ("mcp__claude_ai_Slack__slack_schedule_message", True),
        ("mcp__claude_ai_Gmail__create_draft", True),
        ("mcp__claude_ai_Gmail__send_message", True),
        ("mcp__claude_ai_Gmail__reply", True),
        ("mcp__claude_ai_Gmail__forward", True),
        ("mcp__claude_ai_Gmail__update_draft", True),
        ("mcp__notion__notion-update-comment", True),
        ("mcp__notion__notion-create-meeting-note", True),
        ("mcp__linear__list_issues", False),
        ("mcp__notion__notion-fetch", False),
        ("mcp__notion__notion-update-page-favorites", False),
        ("mcp__notion__notion-get-comments", False),
        ("mcp__notion__notion-delete-comment", False),
        ("mcp__notion__notion-query-meeting-notes", False),
        ("mcp__claude_ai_Slack__slack_read_channel", False),
        ("mcp__claude_ai_Gmail__search_threads", False),
        ("mcp__claude_ai_Gmail__get_draft", False),
        ("mcp__claude_ai_Gmail__delete_draft", False),
        ("Bash", False),
        ("Edit", False),
    ]
    for tool, expected in cases:
        actual = bool(rc.GATED_MCP_RE.match(tool))
        check(
            f"{tool} -> {expected}",
            actual == expected,
            f"got {actual}",
        )


def test_extract_payloads_dispatch() -> None:
    section("extract_payloads: dispatches by tool name")
    bash_out = rc.extract_payloads(
        "Bash",
        {"command": "git commit -m 'Test message body here'"},
    )
    check("Bash dispatch returns payloads", len(bash_out) >= 1, f"got {bash_out!r}")

    mcp_out = rc.extract_payloads(
        "mcp__linear__save_issue",
        {"description": "A long enough description string to pass the filter"},
    )
    check("MCP dispatch returns payloads", len(mcp_out) >= 1, f"got {mcp_out!r}")

    skip_out = rc.extract_payloads("Read", {"file_path": "/etc/hosts"})
    check("non-gated tool returns empty", skip_out == [], f"got {skip_out!r}")

    edit_out = rc.extract_payloads(
        "Edit",
        {
            "file_path": "/repo/README.md",
            "new_string": "A long paragraph of new prose.",
        },
    )
    check(
        "non-gated tool with long prose returns empty",
        edit_out == [],
        f"got {edit_out!r}",
    )

    none_out = rc.extract_payloads("Bash", {"command": None})
    check("non-string Bash command returns empty", none_out == [], f"got {none_out!r}")


def hook_matcher(script: str) -> str:
    """The PreToolUse matcher of the settings.json entry that runs `script`."""
    settings = json.loads(SETTINGS_PATH.read_text())
    for entry in settings["hooks"]["PreToolUse"]:
        if any(h.get("command", "").endswith(script) for h in entry["hooks"]):
            return entry["matcher"]
    raise AssertionError(f"no PreToolUse entry runs {script}")


def test_settings_matcher_gates_outbound_tools() -> None:
    section("settings.json: the rule-check matcher runs on every gated tool")
    # Claude Code tests a matcher that is not a plain list of names as an
    # unanchored JavaScript regex, which `re.search` mirrors.
    matcher = hook_matcher("rule-check.py")
    for tool in (
        "mcp__claude_ai_Gmail__create_draft",
        "mcp__claude_ai_Gmail__send_message",
        "mcp__claude_ai_Gmail__reply",
        "mcp__claude_ai_Gmail__forward",
        "mcp__claude_ai_Gmail__update_draft",
        "mcp__notion__notion-update-comment",
        "mcp__notion__notion-create-meeting-note",
    ):
        check(f"{tool} gated", re.search(matcher, tool) is not None)
        check(f"{tool} in GATED_MCP_RE", rc.GATED_MCP_RE.match(tool) is not None)
    for tool in (
        "mcp__claude_ai_Gmail__search_threads",
        "mcp__claude_ai_Gmail__get_thread",
        "mcp__claude_ai_Gmail__get_draft",
        "mcp__claude_ai_Gmail__list_drafts",
        "mcp__claude_ai_Gmail__delete_draft",
        "mcp__notion__notion-fetch",
        "mcp__notion__notion-get-comments",
        "mcp__notion__notion-delete-comment",
        "mcp__notion__notion-query-meeting-notes",
        "mcp__notion__notion-link-meeting-note-to-calendar-event",
    ):
        check(f"{tool} not gated", re.search(matcher, tool) is None)


def test_extract_mcp_payloads_email_and_comments() -> None:
    section("extract_mcp_payloads: email, comment and meeting-note fields")
    address = "member.support@example.com"
    reference = "sha256:" + "0" * 64 + ":/Users/nobody/Downloads/menu.pdf"
    attachments = [
        {
            "content": reference,
            "filename": "quarterly-membership-report.pdf",
            "mimeType": "application/octet-stream",
        }
    ]
    prose = "Thanks for the quick turnaround on the gate."
    for tool, tool_input, expected in (
        (
            "mcp__claude_ai_Gmail__send_message",
            {
                "to": [address],
                "cc": [address],
                "bcc": [address],
                "subject": "Membership upgrade gate is live",
                "body": prose,
                "htmlBody": f"<p>{prose}</p>",
                "replyThreadId": "18c2f0a1b2c3d4e5f6a7b8c9",
                "replyToMessageId": "18c2f0a1b2c3d4e5f6a7b8c9",
                "draftId": "r-1234567890123456789012",
                "attachments": attachments,
            },
            ["subject", "body", "htmlBody"],
        ),
        (
            "mcp__claude_ai_Gmail__reply",
            {
                "messageId": "18c2f0a1b2c3d4e5f6a7b8c9",
                "to": [address],
                "body": prose,
                "attachments": attachments,
            },
            ["body"],
        ),
        (
            "mcp__claude_ai_Gmail__forward",
            {
                "messageId": "18c2f0a1b2c3d4e5f6a7b8c9",
                "to": [address],
                "forwardText": prose,
                "htmlBody": f"<p>{prose}</p>",
            },
            ["forwardText", "htmlBody"],
        ),
        (
            "mcp__claude_ai_Gmail__update_draft",
            {
                "draftId": "r-1234567890123456789012",
                "subject": "Membership upgrade gate is live",
                "body": prose,
                "attachments": attachments,
            },
            ["subject", "body"],
        ),
        (
            "mcp__notion__notion-update-comment",
            {
                "comment_id": "1f2e3d4c-5b6a-4789-8abc-def012345678",
                "markdown": prose,
                "skill": "notion-meeting-preparation",
            },
            ["markdown"],
        ),
        (
            "mcp__notion__notion-create-meeting-note",
            {
                "title": "Membership upgrade weekly sync",
                "content": f"## Notes\n\n{prose}",
                "parent": {"type": "page", "url": "https://www.notion.so/abc"},
                "calendarEvent": {
                    "calendar": {
                        "accountId": "0b7f9c2e-5d4a-4c1e-9f3a-2b6d8e1a7c55",
                        "calendarId": address,
                    },
                    "eventId": "0b7f9c2e-5d4a-4c1e-9f3a-2b6d8e1a7c55",
                },
            },
            ["title", "content"],
        ),
    ):
        out = rc.extract_payloads(tool, tool_input)
        labels = [label.split(" ", 1)[1] for label, _ in out]
        check(
            f"{tool.split('__')[-1]}: only prose extracted",
            labels == expected,
            f"got {labels!r}",
        )
    nested = rc.extract_mcp_payloads(
        "mcp__notion__notion-create-pages",
        {"pages": [{"attachments": prose, "content": prose}]},
    )
    check(
        "`attachments` below the top level is still checked",
        [label for label, _ in nested]
        == [
            "notion-create-pages pages[0].attachments",
            "notion-create-pages pages[0].content",
        ],
        f"got {nested!r}",
    )


def test_extract_bash_payloads_gh_release() -> None:
    section("extract_bash_payloads: gh release notes and titles")
    with tempfile.TemporaryDirectory() as tmp:
        notes = Path(tmp) / "notes.md"
        notes.write_text("Adds the membership gate.\n")
        text = "Adds the membership gate.\n"
        for cmd, expected in (
            (
                'gh release create v1.2.3 --title "v1.2.3" --notes "Adds the gate."',
                [
                    ("GitHub release arg --title", "v1.2.3"),
                    ("GitHub release arg --notes", "Adds the gate."),
                ],
            ),
            (
                "gh release create v1.2.3 -t 'v1.2.3' -n 'Adds the gate.'",
                [
                    ("GitHub release arg -t", "v1.2.3"),
                    ("GitHub release arg -n", "Adds the gate."),
                ],
            ),
            (
                'gh release edit v1.2.3 --notes="Adds the gate."',
                [("GitHub release arg --notes", "Adds the gate.")],
            ),
            (
                'gh release new v1.2.3 -n "Adds the gate."',
                [("GitHub release arg -n", "Adds the gate.")],
            ),
            (
                'gh -R o/r release edit v1.2.3 -n "Adds the gate."',
                [("GitHub release arg -n", "Adds the gate.")],
            ),
            (
                f"gh release create v1 -F '{notes}'",
                [(f"GitHub release -F {notes}", text)],
            ),
            (
                f"gh release edit v1 --notes-file {notes}",
                [(f"GitHub release --notes-file {notes}", text)],
            ),
            (
                "gh release create v1 -F - <<'EOF'\nAdds the gate.\nEOF",
                [("GitHub release heredoc<EOF>", "Adds the gate.")],
            ),
            (
                (
                    "cat > notes.md <<'EOF'\nAdds the gate.\nEOF\n"
                    "gh release create v1 --notes-file notes.md"
                ),
                [("GitHub release heredoc<EOF>", "Adds the gate.")],
            ),
            (
                'git commit -m "Fix the lock" && gh release create v1 -n "Adds the gate."',
                [
                    ("git commit message arg -m", "Fix the lock"),
                    ("GitHub release arg -n", "Adds the gate."),
                ],
            ),
            ("gh release view v1 -t '{{.body}} of the release'", []),
            ("gh release list -L 5 -t '{{.tagName}} of the release'", []),
            ("gh release download v1 -p 'dist-*.tar.gz' -O 'release.tar.gz'", []),
            ("gh release download v1 -n 'not release notes'", []),
            (f"gh release view v1 -F '{notes}'", []),
            ("gh release create v1 --notes-from-tag 'dist/asset.zip'", []),
        ):
            out = rc.extract_bash_payloads(cmd)
            check(f"`{cmd[:44]}`", out == expected, f"got {out!r}")


def test_extract_mcp_payloads_email_quoted_history() -> None:
    section("extract_mcp_payloads: quoted history is dropped from email bodies")
    own = "Noon works for me, thanks for asking."
    curly = "Noon “works” for me, thanks for asking."
    quoted = (
        "> Is noon “ok” for everyone on the team?\n"
        ">> Earlier “draft” of the rollout plan.\n"
        "  > Indented “quote” from the thread."
    )
    for tool, ids, field in (
        ("mcp__claude_ai_Gmail__create_draft", {"to": ["a@example.com"]}, "body"),
        ("mcp__claude_ai_Gmail__send_message", {"to": ["a@example.com"]}, "body"),
        ("mcp__claude_ai_Gmail__reply", {"messageId": "18c2f0a1"}, "body"),
        ("mcp__claude_ai_Gmail__forward", {"messageId": "18c2f0a1"}, "forwardText"),
        ("mcp__claude_ai_Gmail__update_draft", {"draftId": "r-123"}, "body"),
    ):
        name = tool.split("__")[-1]
        label = f"{name} {field}"
        out = rc.extract_payloads(tool, {**ids, field: f"{own}\n\n{quoted}"})
        check(
            f"{name}: quoted lines dropped",
            out == [(label, f"{own}\n")],
            f"got {out!r}",
        )
        out = rc.extract_payloads(tool, {**ids, field: f"{curly}\n{quoted}"})
        check(
            f"{name}: a smart quote in its own line is sent",
            out == [(label, curly)],
            f"got {out!r}",
        )
        out = rc.extract_payloads(tool, {**ids, field: quoted})
        check(f"{name}: only quoted lines sends nothing", out == [], f"got {out!r}")
    for tool, field, text in (
        ("mcp__claude_ai_Gmail__reply", "htmlBody", f"<p>{own}</p>\n{quoted}"),
        ("mcp__claude_ai_Gmail__send_message", "subject", "> Re: is noon ok for all?"),
        ("mcp__claude_ai_Slack__slack_send_message", "message", quoted),
        ("mcp__notion__notion-update-comment", "markdown", quoted),
        ("mcp__notion__notion-create-meeting-note", "content", quoted),
        ("mcp__linear__save_comment", "body", quoted),
    ):
        out = rc.extract_payloads(tool, {field: text})
        check(
            f"{tool.split('__')[-1]} {field}: quoted lines kept",
            [t for _, t in out] == [text],
            f"got {out!r}",
        )
    out = rc.extract_bash_payloads(f'gh pr comment 1 --body "{quoted}"')
    check(
        "a quoted Bash --body is kept",
        [t for _, t in out] == [quoted],
        f"got {out!r}",
    )


def test_load_rules_smoke() -> None:
    section("load_rules: returns non-empty concatenation when rules exist")
    text = rc.load_rules()
    if rc.RULES_DIR.exists() and any(rc.RULES_DIR.glob("*.md")):
        check("includes a rules/ header", "=== rules/" in text, "no header found")
        check("non-trivial length", len(text) > 1000, f"len={len(text)}")
    else:
        check("returns empty when no rules dir", text == "", f"got {len(text)} chars")


def test_load_rules_order_and_sources() -> None:
    section("load_rules: CLAUDE.md first, then rules/*.md in name order")
    with sandbox(rules=""):
        text = rc.load_rules()
        check("no CLAUDE.md and no rule files gives ''", text == "", f"got {text!r}")
        rc.CLAUDE_MD.write_text("global rules")
        for name in ("zeta", "beta", "alpha", "mid"):
            (rc.RULES_DIR / f"{name}.md").write_text(f"{name} rules")
        (rc.RULES_DIR / "notes.txt").write_text("not a rule file")
        text = rc.load_rules()
    headers = [line for line in text.splitlines() if line.startswith("===")]
    expected = [
        "=== CLAUDE.md ===",
        "=== rules/alpha.md ===",
        "=== rules/beta.md ===",
        "=== rules/mid.md ===",
        "=== rules/zeta.md ===",
    ]
    check("CLAUDE.md, then sorted *.md only", headers == expected, f"got {headers!r}")


def test_prompt_quotes_rules_verbatim() -> None:
    section("build_prompt: sentences quoted from rules/git.md exist in it")
    prompt = rc.build_prompt("", "GitHub PR", "")
    git_md = (HOOK_PATH.parents[1] / "rules" / "git.md").read_text()
    line = next(ln for ln in prompt.splitlines() if "explicitly permits" in ln)
    quoted = [s for s in line.split('"')[1::2] if s.endswith(".")]
    check("two trivial-body examples quoted", len(quoted) == 2, f"got {quoted!r}")
    for sentence in quoted:
        check(f"`{sentence}` is in rules/git.md", sentence in git_md, "not found")


def test_interpreter_heredoc_skipped() -> None:
    section("extract_bash_payloads: interpreter heredocs are not prose")
    cmd = (
        "gh api graphql -f query='...' && python3 - <<'PY'\n"
        "import sys\n"
        "print('this is source code, not outbound prose')\n"
        "PY"
    )
    out = rc.extract_bash_payloads(cmd)
    check(
        "python3 heredoc not extracted",
        not any("heredoc" in lbl for lbl, _ in out),
        f"got {out!r}",
    )
    cat_cmd = "git commit -F- <<'EOF'\nSubject line here\n\nBody.\nEOF"
    out = rc.extract_bash_payloads(cat_cmd)
    check(
        "git-owned heredoc still extracted",
        any("heredoc" in lbl for lbl, _ in out),
        f"got {out!r}",
    )

    def heredocs(cmd: str) -> list[str]:
        return [t for lbl, t in rc.extract_bash_payloads(cmd) if "heredoc" in lbl]

    interpreters = (
        "python",
        "python3",
        "/usr/bin/python3",
        "node",
        "ruby",
        "perl",
        "php",
        "osascript",
        "psql",
        "sqlite3",
        "jq",
        "awk",
    )
    for interp in interpreters:
        cmd = f"gh api graphql -f query='x' && {interp} <<'EOF'\nsource code\nEOF"
        check(f"{interp} heredoc not extracted", heredocs(cmd) == [], f"got {cmd!r}")
    comment = "gh pr comment 1 --body 'Posted the retry report.'"
    script = "python3 - <<'PY'\nprint('report')\nPY"
    for sep in ("; ", " | ", "\n"):
        cmd = comment + sep + script
        check(f"interpreter after {sep!r} not extracted", heredocs(cmd) == [], cmd)
    cmd = 'gh pr comment 1 --body "$(' + script + '\n)"'
    check("interpreter inside $( not extracted", heredocs(cmd) == [], cmd)
    cmd = "git commit -F- \\\n<<'EOF'\nAdd the retry guard\nEOF"
    check(
        "heredoc after a line continuation extracted",
        heredocs(cmd) == ["Add the retry guard"],
        f"got {heredocs(cmd)!r}",
    )


def test_file_heredoc_is_not_the_message() -> None:
    section("extract_bash_payloads: a heredoc written into another file")

    def heredocs(cmd: str) -> list[str]:
        return [f[1] for f in rc.extract_bash_payloads(cmd) if "heredoc" in f[0]]

    workflow = (
        "cat {redirect} .github/workflows/lint.yml <<'EOF'\n"
        "name: lint\n"
        "run: cat .github/workflows/lint.yml\n"
        "EOF"
    )
    for redirect in (">", ">>"):
        cmd = "git commit -m 'Clear the lint findings' -- a.sh && " + workflow.format(
            redirect=redirect
        )
        check(
            f"heredoc after `cat {redirect}` not extracted",
            heredocs(cmd) == [],
            f"got {heredocs(cmd)!r}",
        )
    cmd = "git commit -m 'Clear the lint findings' -- a.sh && " + workflow.format(
        redirect=">"
    )
    check(
        "inline message still extracted",
        "Clear the lint findings" in [f[1] for f in rc.extract_bash_payloads(cmd)],
        f"got {rc.extract_bash_payloads(cmd)!r}",
    )

    message = "cat > /tmp/unit-msg.txt <<'MSG'\nAdd the lint workflow\nMSG\n"
    both = (
        message
        + workflow.format(redirect=">")
        + "\ngit commit -F /tmp/unit-msg.txt -- .github/workflows/lint.yml"
    )
    check(
        "message heredoc extracted, workflow heredoc not",
        heredocs(both) == ["Add the lint workflow"],
        f"got {heredocs(both)!r}",
    )
    for reader in (
        "git commit -F /tmp/unit-msg.txt",
        "git commit --file=/tmp/unit-msg.txt",
        "cd ~/repo && git commit -F unit-msg.txt",
        "gh pr create --title 'Add lint' --body-file /tmp/unit-msg.txt",
        "gh api repos/o/r/issues --input /tmp/unit-msg.txt",
        "gh api repos/o/r/issues/1/comments --field body=@/tmp/unit-msg.txt",
        "gh pr comment 1 --body-file - < /tmp/unit-msg.txt",
        'git commit -m "$(cat /tmp/unit-msg.txt)"',
        "git commit -aF /tmp/unit-msg.txt",
    ):
        check(
            f"heredoc read back by `{reader}` extracted",
            heredocs(message + reader) == ["Add the lint workflow"],
            f"got {heredocs(message + reader)!r}",
        )

    for name, cmd in (
        (
            "variable target read back with braces",
            (
                "f=/tmp/m\ncat > $f <<'MSG'\nAdd the lint workflow\nMSG\n"
                "git commit -F ${f}"
            ),
        ),
        (
            "variable target, another file read back",
            "cat > $f <<'MSG'\nAdd the lint workflow\nMSG\ngit commit -F m.txt",
        ),
        (
            "named target, a variable read back",
            "cat > m.txt <<'MSG'\nAdd the lint workflow\nMSG\ngit commit -F $f",
        ),
        (
            "named target, a command's output read back",
            (
                "cat > m.txt <<'MSG'\nAdd the lint workflow\nMSG\n"
                "git commit -F `ls -t | head -1`"
            ),
        ),
    ):
        check(
            f"{name}: heredoc stays a payload",
            heredocs(cmd) == ["Add the lint workflow"],
            f"got {heredocs(cmd)!r}",
        )
    unread = "cat > $f <<'EOF'\nname: lint\nEOF\ngit commit -F - -- $f"
    check(
        "variable target that nothing reads back is not a payload",
        heredocs(unread) == [],
        f"got {heredocs(unread)!r}",
    )

    stdin = "git commit -F - > /tmp/commit.log <<'EOF'\nSubject line here\nEOF"
    check(
        "stdin heredoc of a redirected git commit extracted",
        heredocs(stdin) == ["Subject line here"],
        f"got {heredocs(stdin)!r}",
    )


def test_file_heredoc_separators_and_quoting() -> None:
    section("extract_bash_payloads: file heredocs after separators and quoted paths")

    def heredocs(cmd: str) -> list[str]:
        return [t for lbl, t in rc.extract_bash_payloads(cmd) if "heredoc" in lbl]

    commit = "git commit -m 'Add the retry notes'"
    notes = "cat > notes.md <<'EOF'\nRetry notes.\nEOF"
    for sep in ("; ", " | ", "\n"):
        cmd = commit + sep + notes
        check(f"file heredoc after {sep!r} not extracted", heredocs(cmd) == [], cmd)
    cmd = commit + ' && x="$(' + notes + '\n)"'
    check("file heredoc inside $( not extracted", heredocs(cmd) == [], cmd)
    cmd = commit + " && cat >notes.md <<'EOF'\nRetry notes.\nEOF"
    check("`cat >file` without a space not extracted", heredocs(cmd) == [], cmd)

    for message, reader in (
        ("cat > '/tmp/unit-msg.txt'", "git commit -F /tmp/unit-msg.txt"),
        ("cat > /tmp/unit-msg.txt", "git commit -F '/tmp/unit-msg.txt'"),
    ):
        cmd = f"{message} <<'MSG'\nAdd the lint workflow\nMSG\n{reader}"
        check(
            f"quoted path read back by {reader!r} extracted",
            heredocs(cmd) == ["Add the lint workflow"],
            f"got {heredocs(cmd)!r}",
        )


def test_git_global_options_before_commit() -> None:
    section("extract_bash_payloads: git global options before `commit`")
    for prefix in (
        "git -C ~/repo commit",
        "git -c core.hooksPath=/dev/null commit",
        "git -c a=b -c c=d commit",
        "git --no-pager -p commit",
        "git --git-dir=/x/.git --work-tree=/x commit",
        "git --work-tree /srv/app commit",
    ):
        out = rc.extract_bash_payloads(f"{prefix} -m 'Add the upgrade gate'")
        check(
            f"`{prefix}` message extracted as a commit message",
            out == [("git commit message arg -m", "Add the upgrade gate")],
            f"got {out!r}",
        )
    for cmd in (
        "git -C ~/repo log --grep commit -m 'Add the upgrade gate'",
        "git commit-graph write -m 'Add the upgrade gate'",
        "git show HEAD --stat && echo commit -m 'Add the upgrade gate'",
        "git -c commit.gpgsign=false tag -a v1 -m 'Add the upgrade gate'",
        "git -C commit log -m 'Add the upgrade gate'",
    ):
        out = rc.extract_bash_payloads(cmd)
        check(f"`{cmd.split(' -m')[0]}` is not a commit", out == [], f"got {out!r}")
    for cmd in (
        "gh pr comment 1 --body 'Adds the upgrade gate.'",
        "gh issue create --title 'Add the upgrade gate'",
        "gh api repos/o/r/issues -f title='Add the upgrade gate'",
    ):
        out = rc.extract_bash_payloads(cmd)
        check(
            f"`{' '.join(cmd.split()[:2])}` still extracted",
            len(out) == 1 and out[0][0].startswith("GitHub"),
            f"got {out!r}",
        )


def test_git_global_options_with_values() -> None:
    section("extract_bash_payloads: git global options that take a value")
    for prefix in (
        "git --git-dir /srv/app/gitdir commit",
        "git --namespace staging commit",
        "git --config-env user.name=GIT_NAME commit",
        "git --attr-source=HEAD commit",
    ):
        out = rc.extract_bash_payloads(f"{prefix} -m 'Add the upgrade gate'")
        check(
            f"`{prefix}` message extracted as a commit message",
            out == [("git commit message arg -m", "Add the upgrade gate")],
            f"got {out!r}",
        )


def test_compound_command_per_flag_surfaces() -> None:
    section(
        "extract_bash_payloads: compound `git commit && gh pr create` labels "
        "flags by owning command"
    )
    cmd = (
        "git commit -m 'Add upgrade gate' && "
        "gh pr create --title 'BYB-1: A Long PR Title Well Past Fifty Chars OK' "
        "--body 'Adds the upgrade gate column to members.'"
    )
    out = rc.extract_bash_payloads(cmd)
    labels = [lbl for lbl, _ in out]
    check(
        "-m labeled git commit message",
        any(lbl.startswith("git commit message") and "-m" in lbl for lbl in labels),
        f"labels={labels!r}",
    )
    check(
        "--title labeled GitHub PR (never a commit subject)",
        any(lbl.startswith("GitHub PR") and "--title" in lbl for lbl in labels),
        f"labels={labels!r}",
    )
    check(
        "--body labeled GitHub PR",
        any(lbl.startswith("GitHub PR") and "--body" in lbl for lbl in labels),
        f"labels={labels!r}",
    )
    cmd = (
        "git commit -m 'Add upgrade gate' && "
        "gh issue create --title 'Track the upgrade gate rollout'"
    )
    labels = [lbl for lbl, _ in rc.extract_bash_payloads(cmd)]
    check(
        "--title of gh issue labeled GitHub issue",
        "GitHub issue arg --title" in labels,
        f"labels={labels!r}",
    )


def test_gh_api_at_file_read() -> None:
    section("extract_bash_payloads: gh api -F body=@file reads file content")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("Comment body loaded from disk for the fixture.")
        path = f.name
    try:
        cmd = f"gh api repos/org/repo/issues/1/comments -F body=@{path}"
        out = rc.extract_bash_payloads(cmd)
        texts = [t for _, t in out]
        check(
            "reads @file content",
            any("loaded from disk" in t for t in texts),
            f"texts={texts!r}",
        )
    finally:
        Path(path).unlink()
    out = rc.extract_bash_payloads("gh api graphql -F query=@- <<'EOF'\nq\nEOF")
    check(
        "@- (stdin) produces no file payload",
        not any("@-" in lbl for lbl, _ in out),
        f"got {out!r}",
    )


def test_width_arithmetic_filter() -> None:
    section("_is_width_arithmetic_violation: drops char-counting findings")
    table_finding = {
        "rule_quote": "Pad all columns to equal width",
        "payload_excerpt": "| --- |",
        "suggested_fix": (
            "The separator row's Reason column has 2 extra dashes compared "
            "to the header rows (107 vs 105 chars)."
        ),
    }
    check(
        "table-width finding dropped",
        rc._is_width_arithmetic_violation(table_finding),
        "not dropped",
    )
    subject_finding = {
        "rule_quote": "50 characters or less",
        "payload_excerpt": "BYB-3384: Something",
        "suggested_fix": "Shorten the subject; it exceeds 50 characters.",
    }
    check(
        "subject-length finding dropped",
        rc._is_width_arithmetic_violation(subject_finding),
        "not dropped",
    )
    semantic_finding = {
        "rule_quote": "Always render Linear issue references as Markdown links",
        "payload_excerpt": "| BYB-3384 | pending | ---- |",
        "suggested_fix": "Replace the bare slug with a Markdown link.",
    }
    check(
        "semantic finding about a table cell kept",
        not rc._is_width_arithmetic_violation(semantic_finding),
        "wrongly dropped",
    )


def test_width_arithmetic_phrases() -> None:
    section("_is_width_arithmetic_violation: each counting phrase, in either field")
    cases = [
        ("suggested_fix", "Fix the separator row."),
        ("suggested_fix", "Remove the extra dash."),
        ("suggested_fix", "Use three dashes."),
        ("suggested_fix", "The column width is uneven."),
        ("suggested_fix", "The width of the second column is off."),
        ("rule_quote", "Cells must be padded"),
        ("rule_quote", "Keep the padding even"),
        ("suggested_fix", "Make it 3 chars wide."),
        ("suggested_fix", "It is 80 characters wide."),
        ("suggested_fix", "The line is 81 vs 79."),
        ("suggested_fix", "The line is 81 versus 79."),
        ("rule_quote", "50 characters or less"),
        ("rule_quote", "Wrap lines at 72 characters"),
        ("suggested_fix", "This line exceeds 100 chars."),
        ("suggested_fix", "The subject is 51 chars."),
        ("suggested_fix", "Fix the PADDING."),
    ]
    for field, text in cases:
        finding = {"rule_quote": "Follow the rule.", "suggested_fix": "Fix it."}
        finding[field] = text
        check(
            f"{field} {text!r} dropped",
            rc._is_width_arithmetic_violation(finding),
            "not dropped",
        )
    excerpt_only = {
        "rule_quote": "Always render Linear issue references as Markdown links",
        "payload_excerpt": "| retry padding | 72 characters | BYB-3384 |",
        "suggested_fix": "Link BYB-3384.",
    }
    check(
        "counting words only in payload_excerpt kept",
        not rc._is_width_arithmetic_violation(excerpt_only),
        "wrongly dropped",
    )


def test_phantom_char_filter() -> None:
    section("_is_phantom_char_violation: a char finding needs the char in the payload")
    clean = "Use straight quotes and commas here."

    def finding(**fields: str) -> dict:
        return {
            "rule_quote": "Follow the rule.",
            "payload_excerpt": "here",
            "suggested_fix": "Fix it.",
            **fields,
        }

    for v in (
        finding(rule_quote="Never use smart quotes."),
        finding(payload_excerpt="curly quotes here"),
        finding(suggested_fix="Replace the quotation marks."),
        finding(rule_quote="Never use Smart Quotes."),
        finding(payload_excerpt="\u201chere\u201d"),
    ):
        check(
            f"phantom dropped: {v!r}",
            rc._is_phantom_char_violation(v, clean),
            "kept",
        )
    for c in "\u2018\u2019\u201c\u201d":
        v = finding(rule_quote="Never use smart quotes.", payload_excerpt=c)
        check(
            f"real U+{ord(c):04X} kept",
            not rc._is_phantom_char_violation(v, f"Say {c}here."),
            "dropped",
        )
    v = finding(rule_quote="Always render Linear issue references as Markdown links")
    check(
        "finding about something else kept",
        not rc._is_phantom_char_violation(v, clean),
        "dropped",
    )
    v = finding(rule_quote="Never use em dashes.", payload_excerpt="\u2014")
    check(
        "a dash is not a forbidden character",
        not rc._is_phantom_char_violation(v, clean),
        "dropped here, which is _is_dash_violation's job",
    )


def test_dash_filter() -> None:
    section("_is_dash_violation: no finding against an em or en dash survives")
    clean = "Use straight quotes and commas here."
    dashed = "Wait \u2014 see pages 1\u20132."

    def finding(**fields: str) -> dict:
        return {
            "rule_quote": "Follow the rule.",
            "payload_excerpt": "here",
            "suggested_fix": "Fix it.",
            **fields,
        }

    for quote in (
        "Never use em dashes.",
        "Never use an Em Dash.",
        "No em-dashes (`\u2014`). Use commas.",
        "No emdash in prose.",
        "Use a hyphen, not an en dash.",
        "No EN-DASH in ranges.",
    ):
        for label, payload in (("absent", clean), ("present", dashed)):
            check(
                f"dash rule dropped, dash {label}: {quote}",
                rc._is_dash_violation(finding(rule_quote=quote), payload),
                "kept",
            )
    for v in (
        finding(suggested_fix="Remove the em-dash."),
        finding(suggested_fix="Replace the en dash with a hyphen."),
        finding(suggested_fix="Remove the Em Dash."),
        finding(payload_excerpt="an em dash here"),
        finding(payload_excerpt="Wait \u2014 no."),
        finding(payload_excerpt="Pages 1\u20132."),
    ):
        check(f"phantom dash dropped: {v!r}", rc._is_dash_violation(v, clean), "kept")
        check(
            f"same finding kept when the dash is real: {v!r}",
            not rc._is_dash_violation(v, dashed),
            "dropped",
        )
    for dash in "\u2014\u2013":
        item = f"- **Element** {dash} description"
        leadin = finding(
            rule_quote="Never use ` - ` or ` \u2014 ` as the lead-in separator.",
            payload_excerpt=item,
            suggested_fix="Replace the em dash with a colon.",
        )
        check(
            f"U+{ord(dash):04X} list lead-in finding kept",
            not rc._is_dash_violation(leadin, f"{item}\n"),
            "dropped",
        )
    other = finding(
        rule_quote="Always render Linear issue references as Markdown links"
    )
    for label, payload in (("no dash", clean), ("a dash", dashed)):
        check(
            f"finding about something else kept, payload with {label}",
            not rc._is_dash_violation(other, payload),
            "dropped",
        )
    check(
        "words that only contain the letters kept",
        not rc._is_dash_violation(
            finding(rule_quote="Keep the system dashboard."), clean
        ),
        "dropped",
    )
    mixed = finding(rule_quote="No em dashes, no smart quotes.")
    for label, payload in (("no dash", clean), ("a dash", dashed)):
        check(
            f"quote that also names smart quotes left alone, payload with {label}",
            not rc._is_dash_violation(mixed, payload),
            "dropped",
        )
    check(
        "that quote is dropped as a phantom when no smart quote is present",
        rc._is_phantom_char_violation(mixed, dashed),
        "kept",
    )
    check(
        "and kept when a smart quote is present",
        not rc._is_phantom_char_violation(mixed, "Say \u201chi\u201d \u2014 now."),
        "dropped",
    )
    prompt = rc.build_prompt("", "GitHub PR", "")
    check("the prompt names no dash rule", not rc.DASH_RULE_RE.search(prompt), "found")
    for kept in ("contexts: smart quotes", "the body: no smart quotes"):
        check(f"the prompt still says `{kept}`", kept in prompt, "missing")
    check(
        "a capitalized quote that names smart quotes is left alone too",
        not rc._is_dash_violation(
            finding(rule_quote="No Em Dashes, no Smart Quotes."), dashed
        ),
        "dropped",
    )


def test_run_check_invocation() -> None:
    section("run_check: the prompt and the claude CLI arguments")
    with sandbox() as fake:
        result = rc.run_check("RULE TEXT", "SURFACE NAME", "PAYLOAD TEXT")
    check("pass verdict returned", result == ("pass", []), f"got {result!r}")
    call = fake.calls[0]
    args = call["args"]
    check(
        "prompt holds rules, surface and payload",
        all(s in call["input"] for s in ("RULE TEXT", "SURFACE NAME", "PAYLOAD TEXT")),
        call["input"][-300:],
    )
    check("print mode", "--print" in args, f"args={args!r}")
    check(
        "no tools, so the subprocess fires no hooks",
        "--allowed-tools" in args and args[args.index("--allowed-tools") + 1] == "",
        f"args={args!r}",
    )
    check(
        "model is opus",
        "--model" in args and args[args.index("--model") + 1] == "opus",
        f"args={args!r}",
    )
    check("session not persisted", "--no-session-persistence" in args, f"args={args!r}")
    check(
        "verdict schema passed",
        "--json-schema" in args
        and json.loads(args[args.index("--json-schema") + 1]) == rc.VERDICT_SCHEMA,
        f"args={args!r}",
    )
    check(
        "timeout set",
        call.get("timeout") == rc.SUBPROCESS_TIMEOUT_SEC,
        f"call={call!r}",
    )


def test_run_check_truncates_long_payloads() -> None:
    section("run_check: payloads over MAX_PAYLOAD_CHARS are truncated")
    limit = rc.MAX_PAYLOAD_CHARS
    with sandbox() as fake:
        rc.run_check("rules", "surface", "x" * limit)
        rc.run_check("rules", "surface", "x" * (limit + 1))
    at_limit, over = (c["input"] for c in fake.calls)
    check(
        "payload at the limit kept whole",
        "x" * limit in at_limit and "[... truncated ...]" not in at_limit,
        "truncated",
    )
    check(
        "payload over the limit cut, with a marker",
        "x" * (limit + 1) not in over and "[... truncated ...]" in over,
        "not truncated",
    )


def test_run_check_verdict_parsing() -> None:
    section("run_check: verdict parsing fails open on anything unexpected")
    finding = {
        "rule_file": "rules/git.md",
        "rule_quote": "Always render Linear issue references as Markdown links",
        "payload_excerpt": "BYB-1234",
        "suggested_fix": "Link BYB-1234.",
    }
    fail = {"verdict": "fail", "violations": [finding]}
    fenced = "```json\n" + json.dumps(fail) + "\n```"
    cases = [
        (
            "structured_output used",
            0,
            verdict_json("fail", [finding]),
            ("fail", [finding]),
        ),
        ("fenced result text", 0, json.dumps({"result": fenced}), ("fail", [finding])),
        (
            "missing verdict is pass",
            0,
            json.dumps({"structured_output": {}}),
            ("pass", []),
        ),
        (
            "null violations become []",
            0,
            json.dumps({"structured_output": {"verdict": "fail", "violations": None}}),
            ("fail", []),
        ),
        ("nonzero exit", 1, verdict_json("fail", [finding]), ("soft-pass", [])),
        ("envelope not JSON", 0, "not json", ("soft-pass", [])),
        ("result not JSON", 0, json.dumps({"result": "not json"}), ("soft-pass", [])),
    ]
    for name, returncode, stdout, expected in cases:
        with sandbox() as fake:
            fake.returncode, fake.stdout = returncode, stdout
            got = rc.run_check("rules", "surface", "payload")
        check(name, got == expected, f"got {got!r}")
    with sandbox() as fake:
        fake.timeout = True
        got = rc.run_check("rules", "surface", "payload")
    check("timeout", got == ("soft-pass", []), f"got {got!r}")


def test_verdict_cache_roundtrip() -> None:
    section("cache: key determinism and save/load roundtrip")
    k1 = rc.cache_key("digest", "surface", "payload")
    k2 = rc.cache_key("digest", "surface", "payload")
    k3 = rc.cache_key("digest", "surface", "payload2")
    check("identical inputs give identical keys", k1 == k2, f"{k1} != {k2}")
    check("payload change gives new key", k1 != k3, "collision")

    original = rc.CACHE_FILE
    with tempfile.TemporaryDirectory() as tmpdir:
        rc.CACHE_FILE = Path(tmpdir) / "cache.json"
        try:
            import time as _time

            check(
                "missing cache file loads empty",
                rc.load_cache() == {},
                "expected {}",
            )
            fresh = {"verdict": "fail", "violations": [], "ts": _time.time()}
            stale = {"verdict": "pass", "violations": [], "ts": 0}
            rc.save_cache({"fresh": fresh, "stale": stale})
            loaded = rc.load_cache()
            check("fresh entry survives", "fresh" in loaded, f"got {loaded!r}")
            check("stale entry pruned by TTL", "stale" not in loaded, f"got {loaded!r}")
            check(
                "verdict preserved",
                loaded.get("fresh", {}).get("verdict") == "fail",
                f"got {loaded!r}",
            )
        finally:
            rc.CACHE_FILE = original


def test_cache_edge_cases() -> None:
    section("cache: key inputs, corrupt files, bad entries, size cap, write failure")
    key = rc.cache_key("digest", "surface", "payload")
    check(
        "digest change gives new key",
        key != rc.cache_key("digest2", "surface", "payload"),
        "collision",
    )
    check(
        "surface change gives new key",
        key != rc.cache_key("digest", "surface2", "payload"),
        "collision",
    )
    with sandbox():
        for raw in ("not json", "[1, 2]"):
            rc.CACHE_FILE.write_text(raw)
            loaded = rc.load_cache()
            check(f"cache file {raw!r} loads empty", loaded == {}, f"got {loaded!r}")
        now = time.time()
        original_max = rc.CACHE_MAX_ENTRIES
        rc.CACHE_MAX_ENTRIES = 2
        try:
            rc.save_cache(
                {
                    "bad": "not a dict",
                    "old": {"verdict": "pass", "ts": now - 3},
                    "mid": {"verdict": "pass", "ts": now - 2},
                    "new": {"verdict": "pass", "ts": now - 1},
                }
            )
        finally:
            rc.CACHE_MAX_ENTRIES = original_max
        loaded = rc.load_cache()
        check(
            "non-dict entry dropped, newest entries kept",
            sorted(loaded) == ["mid", "new"],
            f"got {sorted(loaded)!r}",
        )
        rc.CACHE_FILE = rc.CACHE_FILE.parent / "missing" / "cache.json"
        rc.save_cache({"new": {"verdict": "pass", "ts": now}})
        check("unwritable cache path does not raise", not rc.CACHE_FILE.exists(), "")


def test_log_creates_directory_and_never_raises() -> None:
    section("log: creates its directory and swallows write errors")
    original = rc.LOG_FILE
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            rc.LOG_FILE = Path(tmpdir) / "new" / "rule-check.log"
            rc.log("first entry")
            check(
                "missing directory created",
                rc.LOG_FILE.exists() and "first entry" in rc.LOG_FILE.read_text(),
                "no log written",
            )
            blocker = Path(tmpdir) / "file"
            blocker.write_text("")
            rc.LOG_FILE = blocker / "rule-check.log"
            rc.log("second entry")
            check("unwritable log path does not raise", not rc.LOG_FILE.exists(), "")
        finally:
            rc.LOG_FILE = original


FINDING = {
    "rule_file": "rules/git.md",
    "rule_quote": "Always render Linear issue references as Markdown links",
    "payload_excerpt": "See BYB-1234",
    "suggested_fix": "Link BYB-1234 to its Linear issue.",
}


def comment(body: str) -> dict:
    return {"tool_name": "mcp__linear__save_comment", "tool_input": {"body": body}}


def test_main_verdicts() -> None:
    section("main: exit 2 only for a fail verdict with a real finding")
    smart = dict(FINDING, rule_quote="Never use smart quotes.")
    width = dict(FINDING, suggested_fix="Pad the table to equal column width.")
    cases = [
        ("fail with a finding blocks", "fail", [FINDING], 2),
        ("pass allowed", "pass", [], 0),
        ("pass with stray findings allowed", "pass", [FINDING], 0),
        ("phantom smart-quote finding dropped", "fail", [smart], 0),
        ("width-counting finding dropped", "fail", [width], 0),
    ]
    for name, verdict, violations, expected in cases:
        with sandbox() as fake:
            fake.stdout = verdict_json(verdict, violations)
            code, err = run_main(comment("See BYB-1234 for the retry guard."))
        check(name, code == expected, f"code={code} stderr={err!r}")
        if expected == 2:
            check(
                "stderr names the rule file and the excerpt",
                "rules/git.md" in err and "payload: See BYB-1234" in err,
                err,
            )
    # Singular on purpose: the width filter drops any quote that says "dashes".
    dash = dict(FINDING, rule_quote="Never use an em dash.", payload_excerpt="\u2014")
    body = comment("Will address \u2014 see BYB-1234 for the retry guard.")
    with sandbox() as fake:
        fake.stdout = verdict_json("fail", [dash])
        code, err = run_main(body)
        logged = rc.LOG_FILE.read_text()
    check("finding against a real em dash dropped", code == 0, f"code={code} {err!r}")
    check("the drop is logged", "DASH tool=mcp__linear__save_comment" in logged, logged)
    with sandbox() as fake:
        fake.stdout = verdict_json("fail", [dash, FINDING])
        code, err = run_main(body)
    check(
        "another finding beside it still blocks, alone",
        code == 2 and "rules/git.md" in err and "em dash" not in err,
        f"code={code} stderr={err!r}",
    )


def test_main_fails_open() -> None:
    section("main: allow without a model call when there is nothing to judge")
    body = comment("See BYB-1234 for the retry guard.")
    short = "git commit -F- <<'EOF'\n  Fix.  \nEOF"
    skip = 'See BYB-1234. <!-- rule-check: skip reason="linked below" -->'
    cases = [
        ("bad JSON on stdin", "not json", {}),
        ("tool_input not a dict", {"tool_name": "Bash", "tool_input": ["git"]}, {}),
        ("disabled by env", body, {"CLAUDE_RULE_CHECK_DISABLE": "1"}),
        (
            "payload under 5 chars once stripped",
            {"tool_name": "Bash", "tool_input": {"command": short}},
            {},
        ),
        ("skip marker", comment(skip), {}),
    ]
    for name, payload, env in cases:
        with sandbox() as fake:
            fake.stdout = verdict_json("fail", [FINDING])
            os.environ.update(env)
            code, _ = run_main(payload)
            logged = rc.LOG_FILE.read_text() if rc.LOG_FILE.exists() else ""
        check(name, code == 0 and not fake.calls, f"code={code} calls={fake.calls!r}")
    check("skip logged with its reason", "reason=linked below" in logged, logged)
    with sandbox(rules="") as fake:
        fake.stdout = verdict_json("fail", [FINDING])
        code, _ = run_main(body)
    check("no rule files", code == 0 and not fake.calls, f"code={code}")


def test_main_verdict_cache() -> None:
    section("main: verdict cache reuse, invalidation and NO_CACHE")
    text = "See BYB-1234 for the retry guard."
    with sandbox() as fake:
        run_main(comment(text))
        check("pass verdict cached", len(rc.load_cache()) == 1, f"{rc.load_cache()!r}")
        fake.stdout = verdict_json("fail", [FINDING])
        code, _ = run_main(comment(text))
        check(
            "identical payload served from the cache",
            code == 0 and len(fake.calls) == 1,
            f"code={code} calls={len(fake.calls)}",
        )
        os.environ["CLAUDE_RULE_CHECK_NO_CACHE"] = "1"
        code, _ = run_main(comment(text))
        check(
            "NO_CACHE forces a live check",
            code == 2 and len(fake.calls) == 2,
            f"code={code} calls={len(fake.calls)}",
        )
        verdicts = [entry["verdict"] for entry in rc.load_cache().values()]
        check("NO_CACHE leaves the cache alone", verdicts == ["pass"], f"{verdicts!r}")
        del os.environ["CLAUDE_RULE_CHECK_NO_CACHE"]
        (rc.RULES_DIR / "general.md").write_text("Link every Linear slug.\n")
        code, _ = run_main(comment(text))
        check(
            "a rule edit invalidates the cached verdict",
            code == 2 and len(fake.calls) == 3,
            f"code={code} calls={len(fake.calls)}",
        )
    with sandbox() as fake:
        rules_only = hashlib.sha256(rc.load_rules().encode()).hexdigest()[:16]
        key = rc.cache_key(rules_only, "save_comment body", text)
        rc.save_cache({key: {"verdict": "pass", "violations": [], "ts": time.time()}})
        fake.stdout = verdict_json("fail", [FINDING])
        code, _ = run_main(comment(text))
    check(
        "a verdict keyed without the hook source is not reused",
        code == 2 and len(fake.calls) == 1,
        f"code={code} calls={len(fake.calls)}",
    )
    with sandbox() as fake:
        fake.timeout = True
        code, _ = run_main(comment(text))
        cached = rc.load_cache()
    check("timeout allows", code == 0, f"code={code}")
    check("soft-pass verdict not cached", cached == {}, f"got {cached!r}")


def test_walk_strings_nested() -> None:
    section("walk_strings: yields leaf strings with JSONPath labels")
    items = list(
        rc.walk_strings(
            {
                "a": "alpha",
                "b": {"c": "charlie"},
                "d": ["delta", {"e": "echo"}],
            }
        )
    )
    paths = dict(items)
    check("simple key", paths.get("a") == "alpha", f"got {paths.get('a')!r}")
    check("nested key", paths.get("b.c") == "charlie", f"got {paths.get('b.c')!r}")
    check(
        "array index 0",
        paths.get("d[0]") == "delta",
        f"got {paths.get('d[0]')!r}",
    )
    check(
        "array index 1 with nested key",
        paths.get("d[1].e") == "echo",
        f"got {paths.get('d[1].e')!r}",
    )


def test_short_combined_and_owned_flags() -> None:
    section("extract_bash_payloads: short, combined and owned flags are read")
    with tempfile.TemporaryDirectory() as tmp:
        body = Path(tmp) / "my body.md"
        body.write_text("Adds the gate for members.\n")
        clean = Path(tmp) / "msg.txt"
        clean.write_text("Add the upgrade gate\n")
        text = "Adds the gate for members.\n"
        for cmd, expected in (
            (
                'git commit -am "Fix the lock"',
                [("git commit message arg -am", "Fix the lock")],
            ),
            (
                'git commit -qm "Fix the lock"',
                [("git commit message arg -qm", "Fix the lock")],
            ),
            (
                'git commit -m "Fix the lock" --message "Body paragraph."',
                [
                    ("git commit message arg -m", "Fix the lock"),
                    ("git commit message body arg --message", "Body paragraph."),
                ],
            ),
            (
                'git commit -am "Fix the lock" -m "Body paragraph."',
                [
                    ("git commit message arg -am", "Fix the lock"),
                    ("git commit message body arg -m", "Body paragraph."),
                ],
            ),
            (
                'gh pr create -t "BYB-1: Gate" -b "Adds the gate."',
                [
                    ("GitHub PR arg -t", "BYB-1: Gate"),
                    ("GitHub PR arg -b", "Adds the gate."),
                ],
            ),
            (f"gh pr create -F '{body}'", [(f"GitHub PR -F {body}", text)]),
            (
                f'gh pr create --body-file "{body}"',
                [(f"GitHub PR --body-file {body}", text)],
            ),
            (f"git commit -F '{body}'", [(f"git commit message -F {body}", text)]),
            (f"git commit -aF '{body}'", [(f"git commit message -F {body}", text)]),
            (
                f"git commit -F {clean} && gh pr create -F '{body}'",
                [
                    (f"git commit message -F {clean}", "Add the upgrade gate\n"),
                    (f"GitHub PR -F {body}", text),
                ],
            ),
            (
                'gh -R o/r pr create --body "Adds the gate."',
                [("GitHub PR arg --body", "Adds the gate.")],
            ),
            (
                'gh pr -R o/r comment 1 --body "Fixed, thanks."',
                [("GitHub PR arg --body", "Fixed, thanks.")],
            ),
            (
                f"git commit -m \"$(cat '{body}')\"",
                [("git commit message arg -m", text.strip())],
            ),
            (
                f"gh pr comment 1 --body \"$(< '{body}')\"",
                [("GitHub PR arg --body", text.strip())],
            ),
            (f"git commit --file '{body}'", [(f"git commit message -F {body}", text)]),
            (
                'gh --repo=o/r pr create --body "Adds the gate."',
                [("GitHub PR arg --body", "Adds the gate.")],
            ),
            (
                'gh -R o/r issue create --body "Adds the gate."',
                [("GitHub issue arg --body", "Adds the gate.")],
            ),
            (
                'gh pr comment 1 -b "Fixed, thanks."',
                [("GitHub PR arg -b", "Fixed, thanks.")],
            ),
            (
                'gh pr edit 1 -b "Adds the gate."',
                [("GitHub PR arg -b", "Adds the gate.")],
            ),
            (
                'gh pr merge 1 -t "Merge the gate"',
                [("GitHub PR arg -t", "Merge the gate")],
            ),
            ('gh pr review 1 -b "Looks good."', [("GitHub PR arg -b", "Looks good.")]),
            (
                "gh pr create --title 'Gate; two' -b \"Adds the gate.\"",
                [
                    ("GitHub PR arg --title", "Gate; two"),
                    ("GitHub PR arg -b", "Adds the gate."),
                ],
            ),
            (
                'gh pr create --title "a \\" ; b" -b "Adds the gate."',
                [
                    ("GitHub PR arg --title", 'a \\" ; b'),
                    ("GitHub PR arg -b", "Adds the gate."),
                ],
            ),
            (
                'gh pr create --title "Gate; two" \\\n  -b "Adds the gate."',
                [
                    ("GitHub PR arg --title", "Gate; two"),
                    ("GitHub PR arg -b", "Adds the gate."),
                ],
            ),
            (
                'gh pr create -b "Adds the gate." 2>&1',
                [("GitHub PR arg -b", "Adds the gate.")],
            ),
            (
                'gh pr create --title T 2>&1 -b "Adds the gate."',
                [("GitHub PR arg -b", "Adds the gate.")],
            ),
            ('git commit -Sm "Fix the lock"', []),
            (
                'gh pr create --body "Adds it." | tool -b "not a body"',
                [("GitHub PR arg --body", "Adds it.")],
            ),
            (
                'gh pr create --body "Adds it." & tool -b "not a body"',
                [("GitHub PR arg --body", "Adds it.")],
            ),
            (
                'gh pr create --body "Adds it."; tool -b "not a body"',
                [("GitHub PR arg --body", "Adds it.")],
            ),
            (
                'gh pr create --body "Adds it."\ntool -b "not a body"',
                [("GitHub PR arg --body", "Adds it.")],
            ),
            (f"gh pr view 1; tool -F '{body}'", []),
            (
                f"git commit -q; tool -F '{body}'",
                [(f"git commit message -F {body}", text)],
            ),
            (
                'git commit -t "template.txt" -m "Fix the lock"',
                [("git commit message arg -m", "Fix the lock")],
            ),
            ('gh pr checkout 12 -b "fix-the-lock"', []),
            ('gh api repos/o/r -t "{{.title}} here"', []),
            (
                f"git commit -m 'Fix the lock' && gh api graphql -F '{body}'",
                [("git commit message arg -m", "Fix the lock")],
            ),
            (
                'gh pr create --body "Adds it." && tool -b "not a body"',
                [("GitHub PR arg --body", "Adds it.")],
            ),
            ('gh pr view 1 && tool -am "not a message"', []),
        ):
            out = rc.extract_bash_payloads(cmd)
            check(f"`{cmd[:44]}`", out == expected, f"got {out!r}")
        prefixed = f"See $(cat '{body}')"
        check(
            "$(cat file) inside a longer value stays as written",
            rc.resolve_value(prefixed) == prefixed,
            f"got {rc.resolve_value(prefixed)!r}",
        )
        binary = Path(tmp) / "bin.dat"
        binary.write_bytes(b"\xff\xfe\x00body")
        out = rc.extract_bash_payloads(f"gh pr create --body-file {binary}")
        check("a binary body file is skipped", out == [], f"got {out!r}")
    missing = "$(cat /nonexistent/unit-msg.txt)"
    check(
        "an unreadable $(cat file) stays as written",
        rc.resolve_value(missing) == missing,
        f"got {rc.resolve_value(missing)!r}",
    )


def test_code_and_data_heredocs() -> None:
    section("extract_bash_payloads: code and data heredocs are not messages")
    code = "import sys\nprint(sys.argv)\n"
    for owner in (
        "uv run python -",
        "uv run --frozen python -",
        "python3.12 -",
        "/usr/bin/env python3",
        "/usr/bin/python3 -",
        "time -p python3 -",
        "PYTHONPATH=. python3 -",
        "A=1 B=2 python3 -",
    ):
        out = rc.extract_bash_payloads(
            f"git commit -m 'Add the report' && {owner} <<'PY'\n{code}PY"
        )
        check(
            f"`{owner}`: only the message is sent",
            out == [("git commit message arg -m", "Add the report")],
            f"got {out!r}",
        )
    out = rc.extract_bash_payloads(
        f"git commit -m 'Add the report' && uv pip python3 <<'EOF'\n{code}EOF"
    )
    check("uv without run is not a wrapper", len(out) == 2, f"got {out!r}")

    script = "echo 'step one'\ngit commit -m 'Add the report'\n"
    for owner in ("bash", "sh -s x", "bash > out.log"):
        out = rc.extract_bash_payloads(f"{owner} <<'EOF'\n{script}EOF")
        check(
            f"`{owner}`: the commit in the script is sent, not the script",
            out == [("git commit message arg -m", "Add the report")],
            f"got {out!r}",
        )
    data = "bash run.sh <<'EOF'\nstep one of the run\nEOF\ngit commit -m 'Run it now'"
    out = rc.extract_bash_payloads(data)
    check(
        "bash run.sh: the script's input stays a payload", len(out) == 2, f"got {out!r}"
    )

    loop = (
        "while IFS='|' read -r old new; do git mv \"$old\" \"$new\"; done <<'EOF'\n"
        "notes/2026-11-01.md|notes/2026/11/2026-11-01.md\n"
        "EOF\n"
        'git commit -m "Move the notes into month directories"\n'
    )
    out = rc.extract_bash_payloads(loop)
    check(
        "loop data is not sent",
        out == [("git commit message arg -m", "Move the notes into month directories")],
        f"got {out!r}",
    )

    def heredocs(cmd: str) -> list[str]:
        return [t for label, t in rc.extract_bash_payloads(cmd) if "heredoc" in label]

    tee = "tee -a notes/x.md >/dev/null <<'EOF'\n- Rebased the branch\nEOF\ngit commit -m 'Update notes'"
    check(
        "tee into a file: not the message",
        heredocs(tee) == [],
        f"got {heredocs(tee)!r}",
    )
    bare = "tee -a notes/x.md <<'EOF'\n- Rebased the branch\nEOF\ngit commit -m 'Update notes'"
    check(
        "tee into a file, no redirect: not the message",
        heredocs(bare) == [],
        f"got {heredocs(bare)!r}",
    )
    msg = "<<'MSG'\nAdd the lint workflow\nMSG\n"
    for name, cmd in (
        (
            "its file read back",
            f"tee /tmp/unit-msg.txt {msg}git commit -F /tmp/unit-msg.txt",
        ),
        (
            "one of two files read back",
            f"tee -a a.md /tmp/unit-msg.txt {msg}git commit -F unit-msg.txt",
        ),
        (
            "its stdout file read back",
            f"tee a.md > /tmp/unit-msg.txt {msg}git commit -F unit-msg.txt",
        ),
        ("variable target, a file read back", f"tee $f {msg}git commit -F m.txt"),
        ("no file", f"tee {msg}git commit -m 'Add the lint workflow'"),
    ):
        check(
            f"tee, {name}: stays a payload",
            heredocs(cmd) == ["Add the lint workflow"],
            f"got {heredocs(cmd)!r}",
        )


TESTS = [
    test_extract_bash_payloads_heredoc_commit,
    test_extract_bash_payloads_heredoc_forms,
    test_extract_bash_payloads_inline_m_flag,
    test_extract_bash_payloads_flag_spellings,
    test_extract_bash_payloads_subject_vs_body_m_flags,
    test_extract_bash_payloads_gh_pr_create,
    test_extract_bash_payloads_gh_pr_comment,
    test_extract_bash_payloads_gh_issue_create,
    test_extract_bash_payloads_gh_api,
    test_extract_bash_payloads_gh_api_field_spellings,
    test_extract_bash_payloads_body_file,
    test_extract_bash_payloads_file_path_spellings,
    test_extract_bash_payloads_commit_F_flag,
    test_extract_bash_payloads_commit_long_file_flag,
    test_extract_bash_payloads_gh_api_minus_F_not_treated_as_commit_file,
    test_extract_bash_payloads_unrelated_command,
    test_extract_mcp_payloads_linear,
    test_extract_mcp_payloads_nested_notion,
    test_extract_mcp_payloads_short_values_filtered,
    test_extract_mcp_payloads_length_boundary,
    test_extract_mcp_payloads_non_prose_fields_filtered,
    test_extract_mcp_payloads_every_identifier_field,
    test_field_name_paths,
    test_skip_sentinel_html_comment,
    test_skip_sentinel_hash_comment,
    test_skip_sentinel_slash_comment,
    test_skip_sentinel_case_insensitive,
    test_skip_sentinel_no_match,
    test_gated_mcp_matches,
    test_settings_matcher_gates_outbound_tools,
    test_extract_mcp_payloads_email_and_comments,
    test_extract_bash_payloads_gh_release,
    test_extract_mcp_payloads_email_quoted_history,
    test_extract_payloads_dispatch,
    test_load_rules_smoke,
    test_load_rules_order_and_sources,
    test_prompt_quotes_rules_verbatim,
    test_interpreter_heredoc_skipped,
    test_file_heredoc_is_not_the_message,
    test_file_heredoc_separators_and_quoting,
    test_git_global_options_before_commit,
    test_git_global_options_with_values,
    test_compound_command_per_flag_surfaces,
    test_gh_api_at_file_read,
    test_width_arithmetic_filter,
    test_width_arithmetic_phrases,
    test_phantom_char_filter,
    test_dash_filter,
    test_run_check_invocation,
    test_run_check_truncates_long_payloads,
    test_run_check_verdict_parsing,
    test_verdict_cache_roundtrip,
    test_cache_edge_cases,
    test_log_creates_directory_and_never_raises,
    test_main_verdicts,
    test_main_fails_open,
    test_main_verdict_cache,
    test_walk_strings_nested,
    test_short_combined_and_owned_flags,
    test_code_and_data_heredocs,
]


def main() -> int:
    print(f"Running {len(TESTS)} unit-test groups against {HOOK_PATH}")
    for test in TESTS:
        try:
            test()
        except Exception:  # noqa: BLE001
            _failures.append(f"{test.__name__} raised: {traceback.format_exc()}")
            print(f"  [FAIL] {test.__name__}  RAISED")
            print(traceback.format_exc())

    print()
    if _failures:
        print(f"FAILED: {len(_failures)} assertion(s) failed")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("OK: all assertions passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
