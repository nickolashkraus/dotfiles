#!/usr/bin/env python3
"""
Deterministic unit tests for ~/.claude/hooks/lint-outbound.py.

Covers the regex layer end to end: table-padding measured on source
width, commit subject/body length rules and their exemptions, payload
extraction from Bash (interpreter heredocs, compound-command flag
ownership, gh `@file` bodies), the hard-wrap detector, and the
label-colon capitalization rules. Most cases are regressions for the
2026-07-06 false-positive batch.

Run: python3 .claude/evals/lint-outbound/test_unit.py
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import traceback
from pathlib import Path

HOOK_PATH = Path(__file__).resolve().parents[2] / "hooks" / "lint-outbound.py"

spec = importlib.util.spec_from_file_location("lint_outbound", HOOK_PATH)
assert spec is not None and spec.loader is not None, f"cannot load {HOOK_PATH}"
lo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lo)


_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  [PASS] {name}")
    else:
        _failures.append(f"{name}: {detail}")
        print(f"  [FAIL] {name}  {detail}")


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def build_padded_table(rows: list[list[str] | None]) -> str:
    """Pad a two-column table to equal SOURCE width, the way an editor
    (and rules/typography.md) aligns it."""
    widths = [
        max(len(r[i]) for r in rows if r is not None) for i in range(2)
    ]
    lines = []
    for r in rows:
        if r is None:
            lines.append(f"| {'-' * widths[0]} | {'-' * widths[1]} |")
        else:
            lines.append(f"| {r[0].ljust(widths[0])} | {r[1].ljust(widths[1])} |")
    return "\n".join(lines) + "\n"


def test_table_padding_source_width() -> None:
    section("detect_table_padding: measures SOURCE width, not rendered")
    good = build_padded_table(
        [
            ["File", "Reason"],
            None,
            ["`app/foo.py`", "[BYB-1](https://linear.app/x/issue/BYB-1)"],
            ["plain", "short"],
        ]
    )
    check(
        "padded table with code spans and links passes",
        lo.detect_table_padding(good) == [],
        f"got {lo.detect_table_padding(good)!r}",
    )
    bad = "| Col A | Col B |\n| --- | --- |\n| x | y |\n"
    check(
        "compact separator flagged",
        len(lo.detect_table_padding(bad)) > 0,
        "not flagged",
    )
    ragged = "| a | b |\n| --- | --- | --- |\n| x | y |\n"
    check(
        "column-count mismatch skipped, not flagged",
        lo.detect_table_padding(ragged) == [],
        f"got {lo.detect_table_padding(ragged)!r}",
    )
    fenced = f"```\n{bad}```\n"
    check(
        "table inside code fence ignored",
        lo.detect_table_padding(fenced) == [],
        f"got {lo.detect_table_padding(fenced)!r}",
    )
    prose = "Either a | b works here.\nOr c | d instead.\n"
    check(
        "prose containing pipes not treated as a table",
        lo.detect_table_padding(prose) == [],
        f"got {lo.detect_table_padding(prose)!r}",
    )


def test_commit_subject_exemptions() -> None:
    section("lint_commit_message: subject-length rule and exemptions")
    slug = (
        "BYB-1345: Membership Upgrade Creates Duplicate Active "
        "Subscriptions in Stripe"
    )
    check(
        "Linear-slug subject (78 chars) exempt",
        lo.lint_commit_message(slug, "f") == [],
        f"got {lo.lint_commit_message(slug, 'f')!r}",
    )
    plain = "Add a really long subject line that keeps going well past fifty"
    check(
        "plain 63-char subject flagged",
        len(lo.lint_commit_message(plain, "f")) == 1,
        f"got {lo.lint_commit_message(plain, 'f')!r}",
    )
    conv = "fix(rules): flag reference-style shorthand links in outbound content"
    check(
        "Conventional Commits subject up to 72 exempt",
        lo.lint_commit_message(conv, "f") == [],
        f"got {lo.lint_commit_message(conv, 'f')!r}",
    )
    merge = "Merge branch 'byb-1337' into some-longer-feature-branch-name-here"
    check(
        "Merge subject exempt",
        lo.lint_commit_message(merge, "f") == [],
        f"got {lo.lint_commit_message(merge, 'f')!r}",
    )


def test_commit_body_rules() -> None:
    section("lint_commit_message: body wrap and blank-line rules")
    ok = "Short subject\n\nBody line under seventy-two characters.\n"
    check("clean message passes", lo.lint_commit_message(ok, "f") == [], "")
    long_body = "Short subject\n\n" + ("word " * 20).strip() + "\n"
    check(
        "body line >72 flagged",
        len(lo.lint_commit_message(long_body, "f")) == 1,
        f"got {lo.lint_commit_message(long_body, 'f')!r}",
    )
    url_body = "Short subject\n\nSee https://example.com/" + "a" * 80 + "\n"
    check(
        "long line due to URL exempt",
        lo.lint_commit_message(url_body, "f") == [],
        f"got {lo.lint_commit_message(url_body, 'f')!r}",
    )
    fenced = "Short subject\n\n```\n" + "x" * 100 + "\n```\n"
    check(
        "long line inside code fence exempt",
        lo.lint_commit_message(fenced, "f") == [],
        f"got {lo.lint_commit_message(fenced, 'f')!r}",
    )
    no_blank = "Short subject\nBody immediately follows.\n"
    check(
        "missing blank line after subject flagged",
        any("blank line" in v for v in lo.lint_commit_message(no_blank, "f")),
        f"got {lo.lint_commit_message(no_blank, 'f')!r}",
    )


def test_interpreter_heredoc_skipped() -> None:
    section("extract_bash_content: interpreter heredocs are not prose")
    py = (
        "gh api graphql -f query='...' && python3 - <<'PY'\n"
        "import sys\n"
        "print('source code, not outbound prose')\n"
        "PY"
    )
    check(
        "python3 heredoc not extracted",
        not any("heredoc" in f[0] for f in lo.extract_bash_content(py)),
        f"got {lo.extract_bash_content(py)!r}",
    )
    git = "git commit -F- <<'EOF'\nSubject line\n\nBody.\nEOF"
    fields = lo.extract_bash_content(git)
    check(
        "git-owned heredoc still extracted",
        any("heredoc" in f[0] for f in fields),
        f"got {fields!r}",
    )
    check(
        "commit-only heredoc marked full commit message",
        any("heredoc" in f[0] and f[4] for f in fields),
        f"got {fields!r}",
    )


def test_cat_heredoc_subst_wrapper_redacted() -> None:
    section(
        "extract_bash_content: $(cat <<'EOF') wrapper leaves no -m residue"
    )
    cmd = (
        'git commit -m "$(cat <<\'EOF\'\n'
        "Subject line\n"
        "\n"
        "Body wrapped well under seventy-two characters.\n"
        "EOF\n"
        ')" && git push'
    )
    fields = lo.extract_bash_content(cmd)
    check(
        "heredoc extracted as full commit message",
        any("heredoc" in f[0] and f[4] for f in fields),
        f"got {fields!r}",
    )
    check(
        "no arg -m residue payload",
        not any(f[0] == "arg -m" for f in fields),
        f"got {fields!r}",
    )


def test_compound_command_flag_ownership() -> None:
    section(
        "extract_bash_content: compound `git commit && gh pr create` "
        "labels flags by owning command"
    )
    cmd = (
        "git commit -m 'Short subject' && "
        "gh pr create --title 'BYB-9: A Rather Long PR Title Past Fifty "
        "Characters Easily' --body 'Adds the gate.'"
    )
    by_label = {f[0]: f for f in lo.extract_bash_content(cmd)}
    m_field = by_label.get("arg -m")
    title_field = by_label.get("arg --title")
    check("-m present", m_field is not None, f"labels={list(by_label)!r}")
    check("--title present", title_field is not None, f"labels={list(by_label)!r}")
    if m_field and title_field:
        check(
            "-m is commit-owned and full message",
            m_field[2] is True and m_field[4] is True,
            f"got {m_field!r}",
        )
        check(
            "--title not commit-owned, never length-checked",
            title_field[2] is False and title_field[4] is False,
            f"got {title_field!r}",
        )


def test_gh_api_at_file_read_not_blocked() -> None:
    section("extract_bash_content: gh api -F body=@file reads file content")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("Clean body loaded from disk.\n")
        path = f.name
    try:
        fields = lo.extract_bash_content(f"gh api repos/x/y/issues -F body=@{path}")
        check(
            "@file content read and extracted",
            len(fields) == 1 and "Clean body" in fields[0][1],
            f"got {fields!r}",
        )
    finally:
        Path(path).unlink()
    check(
        "@file value is no longer a bypass block",
        lo.is_bypass_value("@/tmp/foo.md") is None,
        "still blocked",
    )
    check(
        "bare $var expansion still a bypass block",
        lo.is_bypass_value("$BODY") is not None,
        "not blocked",
    )


def test_hard_wrap_detector() -> None:
    section("detect_hard_wraps: wraps only, not adjacent short lines")
    header = (
        "## Section Header\n"
        "A single unwrapped paragraph that is quite long and runs on and "
        "on happily.\n"
    )
    check(
        "header + paragraph not a wrap",
        lo.detect_hard_wraps(header) == [],
        f"got {lo.detect_hard_wraps(header)!r}",
    )
    short_pair = "Title line\nSecond short line\n"
    check(
        "two short lines not a wrap",
        lo.detect_hard_wraps(short_pair) == [],
        f"got {lo.detect_hard_wraps(short_pair)!r}",
    )
    para_bullets = (
        "A one-line paragraph introducing a list:\n"
        "- **First**: Item\n"
        "- **Second**: Item\n"
    )
    check(
        "paragraph + bullet list not a wrap",
        lo.detect_hard_wraps(para_bullets) == [],
        f"got {lo.detect_hard_wraps(para_bullets)!r}",
    )
    real = (
        "This paragraph was hard-wrapped at eighty characters by an editor "
        "and so it\n"
        "continues on a second line, which external content must never do.\n"
    )
    check(
        "real hard wrap still flagged",
        len(lo.detect_hard_wraps(real)) == 1,
        f"got {lo.detect_hard_wraps(real)!r}",
    )


def test_label_colon_rules() -> None:
    section("lint_text: label colons flagged, clause colons left alone")

    def lint(text: str) -> list[str]:
        return lo.lint_text(text, "f", check_local_paths=False)

    check(
        "bold label + lowercase flagged",
        any("colon" in v for v in lint("- **Element**: description here\n")),
        "not flagged",
    )
    check(
        "bold label + parenthetical + lowercase flagged",
        any("colon" in v for v in lint("- **Element** (note): description\n")),
        "not flagged",
    )
    check(
        "link label + lowercase flagged",
        any("colon" in v for v in lint("[EPD-1](https://x): lowercase title\n")),
        "not flagged",
    )
    check(
        "code-span label + lowercase flagged",
        any("colon" in v for v in lint("- `GET /foo`: does something\n")),
        "not flagged",
    )
    clause = "- Note the entry was stale: it declared a missing field\n"
    check(
        "mid-sentence clause colon not flagged",
        lint(clause) == [],
        f"got {lint(clause)!r}",
    )
    check(
        "capitalized label passes",
        lint("- **Element**: Description here\n") == [],
        f"got {lint('- **Element**: Description here')!r}",
    )


def test_plain_label_colon_detector() -> None:
    section("plain_label_colon_violation: Title-Case plain labels only")

    def flagged(line: str) -> bool:
        return lo.plain_label_colon_violation(line)

    # Title-Case / acronym plain-text labels with a lowercase word after the
    # colon are flagged.
    check("multiword Title-Case label", flagged("- Conventional Commits: the carve-out\n"))
    check("single-word label", flagged("- Overview: the summary here\n"))
    check("acronym + connector label", flagged("- Terms of Service: some text\n"))
    check("numbered Title-Case label", flagged("1. Rollback Plan: revert the migration\n"))

    # Not flagged: lowercase word after a capitalized label IS correct.
    check("capitalized value passes", not flagged("- Overview: The summary here\n"))
    # Not flagged: imperative instruction bullets (lowercase content words).
    check(
        "imperative instruction not flagged",
        not flagged("2. Trace the data lifecycle: creation and updates\n"),
    )
    check("imperative check not flagged", not flagged("- Check edge cases: empty inputs\n"))
    # Not flagged: lowercase-tail label is indistinguishable from a clause here
    # and is deferred to the semantic check.
    check("lowercase-tail label deferred", not flagged("- PR titles: when a PR resolves\n"))
    # Not flagged: bold/link/code labels are handled by the dedicated regexes.
    check("bold label deferred to bold regex", not flagged("- **Element**: description\n"))
    # Not flagged: clause colon in flowing prose.
    check(
        "clause colon not flagged",
        not flagged("- Note the entry was stale: it declared a field\n"),
    )


def test_autofix_resolves_detected() -> None:
    section("autofix_label_colons: fixes exactly what the detectors flag")

    def lint(text: str) -> list[str]:
        return lo.lint_text(text, "f", check_local_paths=False)

    flagged = [
        "- **Element**: description here\n",
        "- **Element** (note): description\n",
        "- `GET /foo`: does something\n",
        "[EPD-1](https://x): lowercase title\n",
        "- Conventional Commits: the carve-out\n",
        "1. Rollback Plan: revert the migration\n",
    ]
    for line in flagged:
        fixed = lo.autofix_label_colons(line)
        check(f"changed: {line.strip()[:32]}", fixed != line, f"unchanged: {fixed!r}")
        check(f"resolves: {line.strip()[:32]}", lint(fixed) == [], f"still: {lint(fixed)!r}")

    # Leaves correct lines and non-label cases untouched.
    for line in [
        "- **Element**: Description here\n",
        "- PR titles: when a PR resolves\n",
        "2. Trace the data lifecycle: creation and updates\n",
        "- Note the entry was stale: it declared a field\n",
    ]:
        check(f"untouched: {line.strip()[:32]}", lo.autofix_label_colons(line) == line)

    # Never touches a colon inside a fenced code block.
    fenced = "```\n- foo: bar baz\n```\n"
    check("fenced code untouched", lo.autofix_label_colons(fenced) == fenced)


def test_try_autofix_input_scope() -> None:
    section("try_autofix_input: Edit/Write Markdown only, pure label-colon")

    md = "/Users/x/repo/doc.md"
    # Pure label-colon Edit is fixed and re-lints clean.
    ti = {"file_path": md, "new_string": "- **Element**: description\n"}
    fixed = lo.try_autofix_input("Edit", ti)
    check("edit returns modified input", fixed is not None and fixed["new_string"].startswith("- **Element**: D"))
    check("fixed edit re-lints clean", lo.collect_violations("Edit", fixed) == [])

    # Mixed violation: label-colon fix applied but an em dash remains, so main
    # must still block (collect_violations on the fix is non-empty).
    ti2 = {"file_path": md, "new_string": "- **Element**: description — x\n"}
    fixed2 = lo.try_autofix_input("Edit", ti2)
    check("mixed still has violations", fixed2 is not None and lo.collect_violations("Edit", fixed2) != [])

    # Non-label content: nothing to fix.
    ti3 = {"file_path": md, "new_string": "- **Element**: Description\n"}
    check("clean content -> None", lo.try_autofix_input("Edit", ti3) is None)

    # Bash is never auto-fixed.
    check("bash -> None", lo.try_autofix_input("Bash", {"command": "git commit -m 'x'"}) is None)


def test_main_autofix_end_to_end() -> None:
    section("main: emits updatedInput for pure label-colon, blocks on mixed")
    import json as _json
    import subprocess as _sub

    def run(payload: dict) -> tuple[int, str, str]:
        p = _sub.run(
            [sys.executable, str(HOOK_PATH)],
            input=_json.dumps(payload),
            capture_output=True,
            text=True,
        )
        return p.returncode, p.stdout, p.stderr

    md = "/Users/x/repo/doc.md"
    rc, out, _ = run({"tool_name": "Edit", "tool_input": {"file_path": md, "new_string": "- **Element**: description\n"}})
    ok = rc == 0 and out.strip() != ""
    parsed = _json.loads(out) if ok else {}
    hso = parsed.get("hookSpecificOutput", {})
    check("exit 0 with JSON", ok, f"rc={rc} out={out!r}")
    check("permissionDecision allow", hso.get("permissionDecision") == "allow", f"{hso!r}")
    check(
        "updatedInput capitalized",
        hso.get("updatedInput", {}).get("new_string", "").startswith("- **Element**: D"),
        f"{hso.get('updatedInput')!r}",
    )

    rc2, _, err2 = run({"tool_name": "Edit", "tool_input": {"file_path": md, "new_string": "- **Element**: description — x\n"}})
    check("mixed blocks (exit 2)", rc2 == 2, f"rc={rc2}")
    check("mixed reports em dash", "em dash" in err2, err2)


TESTS = [
    test_table_padding_source_width,
    test_commit_subject_exemptions,
    test_commit_body_rules,
    test_interpreter_heredoc_skipped,
    test_compound_command_flag_ownership,
    test_gh_api_at_file_read_not_blocked,
    test_hard_wrap_detector,
    test_cat_heredoc_subst_wrapper_redacted,
    test_label_colon_rules,
    test_plain_label_colon_detector,
    test_autofix_resolves_detected,
    test_try_autofix_input_scope,
    test_main_autofix_end_to_end,
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
