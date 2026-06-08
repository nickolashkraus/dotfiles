#!/usr/bin/env python3
"""
Deterministic unit tests for ~/.claude/hooks/rule-check.py.

Covers the parts that don't spawn Sonnet: payload extraction from Bash and
MCP tool inputs, the override sentinel regex, the body-file resolver, and
the load_rules concatenation. These run in milliseconds, cost nothing, and
catch the bugs CI is actually good at catching.

Run: python3 .claude/evals/rule-check/test_unit.py

The end-to-end Sonnet eval lives in eval.py and is not run from here.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import traceback
from pathlib import Path

HOOK_PATH = Path(__file__).resolve().parents[2] / "hooks" / "rule-check.py"

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


def test_extract_bash_payloads_heredoc_commit() -> None:
    section("extract_bash_payloads: heredoc commit body")
    cmd = (
        "git commit -m \"$(cat <<'EOF'\n"
        "Add upgrade gate\n\n"
        "Introduces upgrade_eligible column on members.\n"
        "EOF\n"
        ")\""
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


def test_extract_bash_payloads_commit_F_flag() -> None:
    section("extract_bash_payloads: git commit -F reads file content")
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False
    ) as f:
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
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False
    ) as f:
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
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False
    ) as f:
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


def test_extract_bash_payloads_unrelated_command() -> None:
    section("extract_bash_payloads: unrelated command short-circuits")
    out = rc.extract_bash_payloads("ls -la /tmp")
    check("returns empty list", out == [], f"got {out!r}")


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
    m = rc.SKIP_RE.search("# rule-check: skip reason=\"intentional\"")
    check("matches", m is not None, "no match")


def test_skip_sentinel_slash_comment() -> None:
    section("SKIP_RE: // comment")
    m = rc.SKIP_RE.search("// rule-check: skip")
    check("matches without reason", m is not None, "no match")


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
        ("mcp__claude_ai_Gmail__create_draft", True),
        ("mcp__linear__list_issues", False),
        ("mcp__notion__notion-fetch", False),
        ("mcp__claude_ai_Slack__slack_read_channel", False),
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


def test_load_rules_smoke() -> None:
    section("load_rules: returns non-empty concatenation when rules exist")
    text = rc.load_rules()
    if rc.RULES_DIR.exists() and any(rc.RULES_DIR.glob("*.md")):
        check("includes a rules/ header", "=== rules/" in text, "no header found")
        check("non-trivial length", len(text) > 1000, f"len={len(text)}")
    else:
        check("returns empty when no rules dir", text == "", f"got {len(text)} chars")


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


TESTS = [
    test_extract_bash_payloads_heredoc_commit,
    test_extract_bash_payloads_inline_m_flag,
    test_extract_bash_payloads_gh_pr_create,
    test_extract_bash_payloads_gh_pr_comment,
    test_extract_bash_payloads_gh_issue_create,
    test_extract_bash_payloads_gh_api,
    test_extract_bash_payloads_body_file,
    test_extract_bash_payloads_commit_F_flag,
    test_extract_bash_payloads_commit_long_file_flag,
    test_extract_bash_payloads_gh_api_minus_F_not_treated_as_commit_file,
    test_extract_bash_payloads_unrelated_command,
    test_extract_mcp_payloads_linear,
    test_extract_mcp_payloads_nested_notion,
    test_extract_mcp_payloads_short_values_filtered,
    test_skip_sentinel_html_comment,
    test_skip_sentinel_hash_comment,
    test_skip_sentinel_slash_comment,
    test_skip_sentinel_no_match,
    test_gated_mcp_matches,
    test_extract_payloads_dispatch,
    test_load_rules_smoke,
    test_walk_strings_nested,
]


def main() -> int:
    print(f"Running {len(TESTS)} unit-test groups against {HOOK_PATH}")
    for test in TESTS:
        try:
            test()
        except Exception:
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
