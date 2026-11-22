#!/usr/bin/env python3
"""
Deterministic unit tests for ~/.claude/hooks/lint-outbound.py.

Covers the regex layer end to end: table-padding measured on source
width, commit subject/body length rules and their exemptions, payload
extraction from Bash (interpreter heredocs, heredocs written into
Markdown files, compound-command flag ownership, gh `@file` bodies), the
hard-wrap detector, and the
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


def test_file_heredoc_is_not_the_message() -> None:
    section("extract_bash_content: a heredoc written into another file")

    def heredocs(cmd: str) -> list[str]:
        return [f[1] for f in lo.extract_bash_content(cmd) if "heredoc" in f[0]]

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
        "Clear the lint findings" in [f[1] for f in lo.extract_bash_content(cmd)],
        f"got {lo.extract_bash_content(cmd)!r}",
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
            "f=/tmp/m\ncat > $f <<'MSG'\nAdd the lint workflow\nMSG\n"
            "git commit -F ${f}",
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
            "cat > m.txt <<'MSG'\nAdd the lint workflow\nMSG\n"
            "git commit -F `ls -t | head -1`",
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


def test_markdown_heredoc_writes() -> None:
    section("extract_fields: heredocs written into Markdown files are linted")
    bad = "Done — shipped.\n"
    flagged = {
        "cat >> before marker": f"cat >> notes/2026-10-15.md <<'EOF'\n{bad}EOF",
        "redirect after marker": f"cat <<'EOF' >> notes/2026-10-15.md\n{bad}EOF",
        "tee -a": f"tee -a /tmp/pr-body.md <<EOF >/dev/null\n{bad}EOF",
        "after a cd": f"cd ~/x && cat > 'a b/n.md' <<EOF\n{bad}EOF",
    }
    for name, cmd in flagged.items():
        violations = lo.collect_violations("Bash", {"command": cmd})
        check(
            f"{name}: em dash flagged",
            any("em dash" in v for v in violations),
            f"got {violations!r}",
        )
    skipped = {
        "non-Markdown target": f"cat > out.txt <<'EOF'\n{bad}EOF",
        "interpreter heredoc": f"python3 - <<'PY' > out.md\n{bad}PY",
        "variable target": f'cat >> "$f" <<EOF\n{bad}EOF',
        "no redirect": f"cat <<'EOF'\n{bad}EOF",
    }
    for name, cmd in skipped.items():
        violations = lo.collect_violations("Bash", {"command": cmd})
        check(f"{name}: not linted", not violations, f"got {violations!r}")
    clean = "cat >> notes/2026-10-15.md <<'EOF'\n- **Email**: Inbox zero\nEOF"
    check(
        "clean heredoc passes",
        not lo.collect_violations("Bash", {"command": clean}),
    )
    fields = lo.extract_markdown_heredocs(
        "cat >> notes/a.md <<'EOF'\nnew line only\nEOF"
    )
    check(
        "only the heredoc body is linted",
        [f[1] for f in fields] == ["new line only"],
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

    # Bash commit/PR bodies are never auto-fixed.
    check("bash -> None", lo.try_autofix_input("Bash", {"command": "git commit -m 'x'"}) is None)


def test_autofix_identifier_and_heredoc() -> None:
    section("autofix: skips identifiers, rewrites Markdown heredoc bodies")
    for line in ("- **Repo**: ppp-service is live", "- **SHA**: a1b2c3d", "- **CLI**: v2.1"):
        check(f"identifier left unfixed: {line}", lo.autofix_label_colon_line(line) is None)
        violations = lo.lint_text(line + "\n", "f", check_local_paths=False)
        check(
            f"identifier still blocked with backtick hint: {line}",
            any("backticks" in v for v in violations),
            f"got {violations!r}",
        )
    check(
        "plain word with trailing period still fixed",
        lo.autofix_label_colon_line("- **Status**: done.") == "- **Status**: Done.",
    )
    cmd = "cat >> notes/a.md <<'EOF'\n- **Email**: inbox zero\nEOF\necho ok"
    fixed = lo.try_autofix_input("Bash", {"command": cmd, "description": "d"})
    check(
        "heredoc body capitalized, rest of command intact",
        fixed == {
            "command": "cat >> notes/a.md <<'EOF'\n- **Email**: Inbox zero\nEOF\necho ok",
            "description": "d",
        },
        f"got {fixed!r}",
    )
    check("fixed command lints clean", not lo.collect_violations("Bash", fixed or {}))
    check(
        "non-Markdown heredoc not rewritten",
        lo.try_autofix_input("Bash", {"command": "cat > a.txt <<'EOF'\n- **E**: x\nEOF"})
        is None,
    )


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

    cmd = "cat >> notes/a.md <<'EOF'\n- **Email**: inbox zero\nEOF"
    rc3, out3, _ = run({"tool_name": "Bash", "tool_input": {"command": cmd}})
    hso3 = _json.loads(out3).get("hookSpecificOutput", {}) if rc3 == 0 and out3.strip() else {}
    check(
        "bash heredoc: updatedInput capitalized",
        "**Email**: Inbox zero" in hso3.get("updatedInput", {}).get("command", ""),
        f"rc={rc3} out={out3!r}",
    )


def test_tool_attribution_footer() -> None:
    section("lint_text: the tool-attribution footer is blocked everywhere")

    def lint(text: str) -> list[str]:
        return lo.lint_text(text, "f", check_local_paths=False)

    def flagged(text: str) -> bool:
        return any("Generated with Claude Code" in v for v in lint(text))

    robot = chr(0x1F916)
    footer = "Generated with [Claude Code](https://claude.com/claude-code)"

    for label, text in [
        ("emoji + Markdown link", f"{robot} {footer}\n"),
        ("no emoji", f"{footer}\n"),
        ("claude.ai link", f"{robot} Generated with [Claude Code](https://claude.ai/code)\n"),
        ("bare text, lowercase", "generated with claude code\n"),
        ("co-generated variant", "Co-Generated with Claude Code\n"),
        ("generated by variant", "Generated by Claude Code\n"),
        ("indented", "  Generated with Claude Code\n"),
        ("as a body footer", f"Adds a thing.\n\n{robot} {footer}\n"),
    ]:
        check(f"blocked: {label}", flagged(text), "not flagged")

    # Prose that merely names the tool is not the footer. The rule anchors to
    # the line start so a sentence about it stays writable.
    for label, text in [
        ("mid-sentence mention", "The body was generated with Claude Code, oddly.\n"),
        ("unrelated generated", "Adds a generated client for the API.\n"),
        ("other tool", "Generated with Terraform.\n"),
    ]:
        check(f"allowed: {label}", not flagged(text), f"got {lint(text)!r}")


def test_git_global_flags_before_commit() -> None:
    section("extract_bash_content: git global flags before the subcommand")

    # Split so the literal never sits at the start of a line, where the
    # hook's own Co-Authored-By check would match this file's source.
    trailer = "Co-" + "Authored-By: Claude <noreply@anthropic.com>\n"
    body = (
        "Add daily notes and tasks for Oct 1 to 5\n"
        "\n"
        "Record the recurring-task results for the first week of October,\n"
        "including the Slack roster diff and the email triage counts.\n"
    )

    def heredoc(prefix: str, text: str) -> str:
        return f"{prefix} <<'EOF'\n{text}EOF"

    def violations(cmd: str) -> list[str]:
        return lo.collect_violations("Bash", {"command": cmd})

    forms = [
        ("plain", "git commit -q -F -"),
        ("-c k=v", "git -c core.hooksPath=/dev/null commit -q -F -"),
        ("--no-pager -C path", "git --no-pager -C /Users/x/repo commit -F -"),
        ("repeated -c", "git -c a=b -c c=d commit -F -"),
        ("--git-dir= --work-tree=", "git --git-dir=/x/.git --work-tree=/x commit -F -"),
        ("--work-tree separate value", "git --work-tree /srv/app commit -F -"),
    ]
    for label, prefix in forms:
        signed = heredoc(prefix, body + "\n" + trailer)
        fields = lo.extract_bash_content(signed)
        check(
            f"{label}: heredoc owned by the commit",
            any("heredoc" in f[0] and f[2] for f in fields),
            f"got {fields!r}",
        )
        check(
            f"{label}: trailer blocked",
            any("Co-Authored-By" in v for v in violations(signed)),
            f"got {violations(signed)!r}",
        )
        clean = heredoc(prefix, body)
        check(
            f"{label}: body wrapped at 72 is clean",
            violations(clean) == [],
            f"got {violations(clean)!r}",
        )

    # Compound command: `gh` in the same line makes heredoc ownership
    # ambiguous (so the length checks stay off), but the trailer check and
    # the hard-wrap exemption both still follow from `is_commit`.
    compound = (
        heredoc("git -c core.hooksPath=/dev/null commit -q -F -", body + "\n" + trailer)
        + "\ngh pr create --title 'T' --body 'Adds a gate.'"
    )
    check(
        "compound git+gh: trailer blocked",
        any("Co-Authored-By" in v for v in violations(compound)),
        f"got {violations(compound)!r}",
    )
    check(
        "compound git+gh: commit body not hard-wrap flagged",
        not any("hard-wrapped" in v for v in violations(compound)),
        f"got {violations(compound)!r}",
    )

    # Unrelated subcommands must not read as a commit.
    for label, cmd in [
        ("git commit-graph write", "git commit-graph write"),
        ("git commit-tree", "git commit-tree abc123"),
        ("git log ... commit", "git log --format=%s -n1 commit"),
        ("echo commit", "git show HEAD --stat && echo commit"),
        ("git -c commit.x tag", "git -c commit.gpgsign=false tag -a v1 -m 'x'"),
        ("git -C commit log", "git -C commit log -m 'x'"),
    ]:
        check(
            f"not a commit: {label}",
            not lo.GIT_COMMIT_RE.search(cmd),
            f"matched {cmd!r}",
        )

    # A `gh pr create` payload is untouched by the change: the body is
    # still extracted as a PR body, never as a commit field.
    pr = "gh pr create --title 'BYB-1: A Title' --body 'Adds the gate.'"
    by_label = {f[0]: f for f in lo.extract_bash_content(pr)}
    check(
        "gh pr create: body extracted as PR body, not a commit",
        by_label.get("arg --body", (None,) * 5)[2] is False
        and by_label.get("arg --body", (None,) * 5)[3] is True,
        f"got {by_label!r}",
    )
    check(
        "gh pr create: clean body passes",
        violations(pr) == [],
        f"got {violations(pr)!r}",
    )


def test_in_repo_path_prefixes() -> None:
    section("is_in_repo_path: ~/w worktree links are in-repo")
    home = Path.home()
    for label, path, expected in [
        ("~/w worktree link", f"{home}/w/dot/.claude/skills/x/SKILL.md", True),
        ("real repo path", f"{home}/nickolashkraus/dotfiles/README.md", True),
        ("/tmp PR body draft", "/tmp/pr-1-body.md", False),
        ("~/wiki is not ~/w", f"{home}/wiki/page.md", False),
    ]:
        check(
            f"{label}: in_repo={expected}",
            lo.is_in_repo_path(path) is expected,
            f"got {lo.is_in_repo_path(path)!r} for {path}",
        )


def test_linear_mirror_paths_skip_lint() -> None:
    section("extract_fields: verbatim Linear copies are not linted")
    root = lo.LINEAR_ISSUE_ROOT / "function/projects/p"
    for label, path, expected in [
        ("issue copy", f"{root}/linear/P-NAV-1-p/issues/NAV-1-x.md", False),
        ("comment copy", f"{root}/linear/comments/NAV-1.comment-abc.md", False),
        ("linear README", f"{root}/linear/README.md", True),
        ("project note", f"{root}/notes/2026-11-05.01.md", True),
        ("/tmp draft", "/tmp/linear/body.md", True),
    ]:
        ti = {"file_path": path, "new_string": "a — b\n"}
        flagged = lo.collect_violations("Edit", ti) != []
        check(
            f"{label}: flagged={expected}",
            flagged is expected,
            f"got {flagged!r} for {path}",
        )


def test_archive_cleanup_false_positives() -> None:
    section("archive cleanup false positives stay quiet; the rules still fire")

    def slop(text: str) -> bool:
        return any("AI slop" in v for v in lo.lint_text(text, "t", check_local_paths=False))

    check("literal bike ride is legal", not slop("- **Bike**: 40 mile ride at Z2.\n"))
    check("land as a noun is legal", not slop("Arable land value rose 7%.\n"))
    check("figurative land still flagged", slop("The fix lands in the next release.\n"))
    check("figurative ride with code span flagged", slop("The ID rides along in `meta`.\n"))

    check("blockquote slop is legal", not slop("> We leverage robust tooling.\n"))
    check("double-quoted slop is legal", not slop('The epic is "Utilize GitHub secrets".\n'))
    check("plain slop still flagged", slop("We leverage the cache.\n"))

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "note.md"
        path.write_text("We leverage the cache.\n- **Name (9:58 AM)**: lowercase reply\n")
        kept = {"file_path": str(path), "content": path.read_text()}
        check("existing lines keep their wording", lo.collect_violations("Write", kept) == [])
        added = {"file_path": str(path), "content": path.read_text() + "We also leverage it.\n"}
        check("new slop line still flagged", any("AI slop" in v for v in lo.collect_violations("Write", added)))
        path.write_text("Old line — with a dash.\n")
        dash = {"file_path": str(path), "content": path.read_text()}
        check("existing em dash still flagged", any("em dash" in v for v in lo.collect_violations("Write", dash)))
        edit = {"file_path": str(path), "new_string": "Old line, no dash.\n- **Name**: lowercase\n"}
        check("edit with a new lowercase label still flagged", any("colon" in v for v in lo.collect_violations("Edit", edit)))

    def colon(text: str) -> bool:
        return any("colon" in v for v in lo.lint_text(text, "t", check_local_paths=False))

    check("URL after a bold label is legal", not colon("- **Docs**: https://example.com/x\n"))
    check("URL after a link label is legal", not colon("[Docs](https://x): https://example.com\n"))
    check("URL after a plain label is legal", not colon("- Docs: https://example.com/x\n"))
    check("lowercase word after a plain label still flagged", colon("- Docs: example text\n"))
    check("lowercase word after a label still flagged", colon("- **Docs**: example text\n"))

    loop = (
        "while IFS='|' read -r old new; do git mv \"$old\" \"$new\"; done <<'EOF'\n"
        "A very long data line that is not a commit subject at all, by any measure|x\n"
        "EOF\n"
        "git commit -m \"Rename the notes\"\n"
    )
    fields = lo.extract_bash_content(loop)
    check("data heredoc is not linted as a commit", all(not f[0].startswith("heredoc") for f in fields))
    commit = "git commit -F - <<'EOF'\n" + "S" * 71 + "\nEOF\n"
    check(
        "commit heredoc subject length still checked",
        any("subject" in v for v in lo.collect_violations("Bash", {"command": commit})),
    )


def test_wrapped_code_span() -> None:
    section("lint_text: a code span that wraps across lines is still code")

    def british(text: str) -> list[str]:
        return [
            v.split(": ", 1)[1].split(" (")[0]
            for v in lo.lint_text(text, "t", check_local_paths=False)
            if "British" in v
        ]

    inside = "Run the check with `tool --colour\nred --all` before the push.\n"
    check("word inside a wrapped span is legal", british(inside) == [], f"{british(inside)!r}")
    after = "See `git commit\n-F file` and the colour of `behaviour` here.\n"
    found = [v for v in lo.lint_text(after, "t", check_local_paths=False) if "British" in v]
    check(
        "prose after the wrapped span is checked on its own line",
        len(found) == 1 and found[0].startswith("t line 2:") and '"colour"' in found[0],
        f"got {found!r}",
    )
    strays = (
        "Type a single ` to open a span.\n"
        "This prose has the colour red in it.\n"
        "Close it with another ` later.\n"
    )
    found = [v for v in lo.lint_text(strays, "t", check_local_paths=False)]
    check(
        "two backticks more than one line break apart are strays",
        len(found) == 1 and found[0].startswith("t line 2:") and "colour" in found[0],
        f"got {found!r}",
    )
    stray = "A stray ` tick and `code`\nthen the colour of `x` here.\n"
    check(
        "odd backtick count falls back to one line at a time",
        british(stray) == ['British spelling "colour"'],
        f"got {british(stray)!r}",
    )
    for name, text in (
        ("blank line", "one ` stray\n\ntwo colour ` stray\n"),
        ("list item", "- one ` stray\n- two colour ` stray\n"),
        ("heading", "one ` stray\n# Two colour ` stray\n"),
        ("heading end", "# One ` stray\ntwo colour ` stray\n"),
        ("table row", "| one ` stray |\n| two colour ` stray |\n"),
        ("backtick fence", "one ` stray\n```\necho hi\n```\ntwo colour ` stray\n"),
        ("tilde fence", "one ` stray\n~~~\necho hi\n~~~\ntwo colour ` stray\n"),
    ):
        check(
            f"span does not cross a {name}",
            british(text) == ['British spelling "colour"'],
            f"got {british(text)!r}",
        )


EM = "—"


def bash_violations(cmd: str) -> list[str]:
    return lo.collect_violations("Bash", {"command": cmd})


def em_dash_flagged(cmd: str) -> bool:
    return any("em dash" in v for v in bash_violations(cmd))


def test_short_combined_and_owned_flags() -> None:
    section("extract_bash_content: short, combined and owned flags are read")
    with tempfile.TemporaryDirectory() as tmp:
        dashed = Path(tmp) / "my body.md"
        dashed.write_text(f"Adds the gate {EM} finally.\n")
        clean = Path(tmp) / "clean.md"
        clean.write_text("Adds the gate.\n")
        for name, cmd in (
            ("git commit -am", f'git commit -am "Fix the lock {EM} again"'),
            ("git commit -qm", f'git commit -qm "Fix the lock {EM} again"'),
            ("gh pr create -b", f'gh pr create -t T -b "Adds the gate {EM} finally."'),
            ("gh issue create -t", f'gh issue create -t "Gate {EM} two" -b "Adds it."'),
            ("gh pr create -F", f"gh pr create --title T -F '{dashed}'"),
            ("gh issue comment -F", f"gh issue comment 3 -F '{dashed}'"),
            ("git commit -F, quoted path", f"git commit -F '{dashed}'"),
            ("git commit -aF", f"git commit -aF '{dashed}'"),
            ("git commit --file", f"git commit --file '{dashed}'"),
            ("--body-file, quoted path", f'gh pr create --title T --body-file "{dashed}"'),
            ("gh pr comment -b", f'gh pr comment 1 -b "Fixed {EM} it."'),
            ("gh pr edit -b", f'gh pr edit 1 -b "Adds {EM} it."'),
            ("gh pr merge -t", f'gh pr merge 1 -t "Merge {EM} it"'),
            ("gh pr review -b", f'gh pr review 1 -b "Looks {EM} good."'),
            ("-b after a single-quoted `;`", f"gh pr create --title 'a; b' -b \"Adds {EM} it.\""),
            ("-b after an escaped quote", f'gh pr create --title "a \\" ; b" -b "Adds {EM} it."'),
            ("gh -R before pr", f'gh -R o/r pr create --title T --body "Adds {EM} it."'),
            ("gh --repo= before pr", f'gh --repo=o/r pr create --body "Adds {EM} it."'),
            ("gh pr -R before comment", f'gh pr -R o/r comment 12 --body "Fixed {EM} it."'),
            ("-b after a continuation", f'gh pr create --title T \\\n  -b "Adds {EM} it."'),
            ("-b after a quoted `;`", f'gh pr create --title "a; b" -b "Adds {EM} it."'),
            ("-b after 2>&1", f'gh pr create --title T 2>&1 -b "Adds {EM} it."'),
            ("-m $(cat file)", f"git commit -m \"$(cat '{dashed}')\""),
            ("--body $(< file)", f"gh pr comment 1 --body \"$(< '{dashed}')\""),
            ("unowned -F in a commit command", f"git commit -q; tool -F '{dashed}'"),
        ):
            check(f"{name}: em dash flagged", em_dash_flagged(cmd), f"got {bash_violations(cmd)!r}")
        for name, cmd in (
            ("git commit -Sm (a signing key)", f'git commit -Sm "Fix {EM} it"'),
            ("git commit -t (a template)", f'git commit -t "t{EM}.txt" -m "Fix"'),
            ("gh pr checkout -b (a branch)", f'gh pr checkout 12 -b "fix{EM}it"'),
            ("gh api -t (a template)", f"gh api repos/o/r -t '{{{{.x}}}} {EM}'"),
            ("-t of a later command", f'gh pr create --body B && tool -t "x {EM}"'),
            ("-b of a piped command", f'gh pr create --body B | tool -b "x {EM}"'),
            ("-b of a background command", f'gh pr create --body B & tool -b "x {EM}"'),
            ("-b after a `;`", f'gh pr create --body B; tool -b "x {EM}"'),
            ("-b on the next line", f'gh pr create --body B\ntool -b "x {EM}"'),
            ("unowned -F, no commit", f"gh pr view 1; tool -F '{dashed}'"),
            ("-am outside a commit", f'gh pr view 1 && tool -am "x {EM}"'),
            ("gh api -F (a field)", f"git commit -m Fix && gh api graphql -F '{dashed}'"),
            ("gh pr view -F", f"git commit -m Fix && gh pr view 1 -F '{dashed}'"),
            ("-F - (stdin)", "git commit -F - && echo"),
        ):
            check(f"{name}: not read", not em_dash_flagged(cmd), f"got {bash_violations(cmd)!r}")

        fields = lo.extract_bash_content('git commit -am "Fix the lock"')
        check(
            "-am is the whole commit message",
            fields == [("arg -am", "Fix the lock", True, False, True)],
            f"got {fields!r}",
        )
        both = lo.extract_bash_content(
            f"git commit -F {clean} && gh pr create --title T -F '{dashed}'"
        )
        check(
            "-F is the commit message under git, the PR body under gh",
            [(f[0], *f[2:]) for f in both if f[0].startswith("arg -F")]
            == [(f"arg -F {clean}", True, False, True), (f"arg -F {dashed}", False, True, False)],
            f"got {both!r}",
        )
        fields = lo.extract_bash_content(f"gh issue comment 3 -F '{clean}'")
        check(
            "-F under gh issue comment is a body, not a PR body",
            [f[2:] for f in fields] == [(False, False, False)],
            f"got {fields!r}",
        )
        fields = lo.extract_bash_content(f"git commit -m \"$(cat '{dashed}')\"")
        check(
            "$(cat file) is the file's text without the final newline",
            fields == [("arg -m", f"Adds the gate {EM} finally.", True, False, True)],
            f"got {fields!r}",
        )
        prefixed = f"See $(cat '{dashed}')"
        check(
            "$(cat file) inside a longer value stays as written",
            lo.resolve_value(prefixed) == prefixed,
            f"got {lo.resolve_value(prefixed)!r}",
        )
        binary = Path(tmp) / "bin.dat"
        binary.write_bytes(b"\xff\xfe\x00body")
        found = bash_violations(f"gh pr create --title T --body-file {binary}")
        check("a binary body file is skipped", found == [], f"got {found!r}")
    missing = "$(cat /nonexistent/unit-msg.txt)"
    check(
        "an unreadable $(cat file) stays as written",
        lo.resolve_value(missing) == missing,
        f"got {lo.resolve_value(missing)!r}",
    )
    for cmd, expected in (
        ("gh pr create --title T -m 'Q4'", ("arg -m", "Q4", False, False, False)),
        ("gh pr create -b 'Adds it.'", ("arg -b", "Adds it.", False, True, False)),
        ("gh pr comment 1 --body 'Fixed.'", ("arg --body", "Fixed.", False, False, False)),
        ("gh pr create --title 'Gate'", ("arg --title", "Gate", False, False, False)),
        ("git commit -m 'Fix' --body 'Note'", ("arg --body", "Note", False, False, False)),
    ):
        fields = lo.extract_bash_content(cmd)
        check(f"`{cmd}` field", expected in fields, f"got {fields!r}")
    for cmd, closes in (
        ("gh -R o/r pr create --title T --body 'Closes #12'", True),
        ("gh issue create --title T --body 'Closes #12'", False),
        ("gh pr comment 1 --body 'Closes #12'", False),
    ):
        found = bash_violations(cmd)
        check(
            f"`{cmd[:28]}`: autoclose check {'on' if closes else 'off'}",
            any("Closes:" in v for v in found) is closes,
            f"got {found!r}",
        )
    subject = "S" * 60
    signed = f"git commit -F - <<'EOF'\n{subject}\nEOF\ngh -R o/r pr create --title T --body B"
    found = bash_violations(signed)
    check("gh -R in the command keeps the heredoc length checks off", found == [], f"got {found!r}")


def test_code_and_data_heredocs() -> None:
    section("extract_bash_content: code and data heredocs are not messages")
    code = (
        "import json, sys\n"
        f"files = json.load(sys.stdin)  # every changed path {EM} sorted by name\n"
        "print(files)\n"
    )
    for name, owner in (
        ("uv run python -", "uv run python -"),
        ("uv run with a flag", "uv run --frozen python -"),
        ("python3.12 -", "python3.12 -"),
        ("/usr/bin/env python3", "/usr/bin/env python3"),
        ("/usr/bin/python3", "/usr/bin/python3 -"),
        ("an assignment first", "PYTHONPATH=. python3 -"),
        ("two assignments first", "A=1 B=2 python3 -"),
        ("time with a flag", "time -p python3 -"),
    ):
        cmd = f"git commit -m 'Add the report' && {owner} <<'PY'\n{code}PY"
        found = bash_violations(cmd)
        check(f"{name}: code not linted", found == [], f"got {found!r}")
    kept = f"git commit -m 'Add it' && uv pip python3 <<'EOF'\n{code}EOF"
    check("uv without run is not a wrapper", em_dash_flagged(kept), "not flagged")

    script = f"echo 'step {EM} one'\ngit commit -m 'Add the report'\n"
    for name, owner in (
        ("bash", "bash"),
        ("sh -s with an argument", "sh -s x"),
        ("bash with a redirect", "bash > out.log"),
    ):
        cmd = f"{owner} <<'EOF'\n{script}EOF"
        check(f"{name}: script not linted", bash_violations(cmd) == [], f"got {bash_violations(cmd)!r}")
        fields = lo.extract_bash_content(cmd)
        check(
            f"{name}: the commit in the script is read",
            fields == [("arg -m", "Add the report", True, False, True)],
            f"got {fields!r}",
        )
    bad = f"bash <<'EOF'\ngit commit -m 'Fix the lock {EM} again'\nEOF"
    check("bash: a message in the script is still linted", em_dash_flagged(bad), "not flagged")
    data = f"bash run.sh <<'EOF'\nstep {EM} one\nEOF\ngit commit -m 'Run it'"
    check("bash run.sh: the script's input stays a payload", em_dash_flagged(data), "not flagged")

    query = (
        '{"query": "query { repository(owner: \\"o\\", name: \\"r\\") { id } }",\n'
        ' "variables": {"first": 100, "after": null, "states": ["OPEN"]}}\n'
    )
    gql = f"gh api graphql --input - <<'EOF'\n{query}EOF"
    check("gh api --input - JSON: no hard wrap", bash_violations(gql) == [], f"got {bash_violations(gql)!r}")
    comment = (
        "gh api repos/o/r/issues/1/comments --input - <<'EOF'\n"
        f'{{"body": "Fixed {EM} thanks."}}\nEOF'
    )
    found = bash_violations(comment)
    check(
        "gh api --input - JSON: the body is still linted",
        any("em dash" in v and "body" in v for v in found),
        f"got {found!r}",
    )
    one_char = f"gh api graphql --input - <<'EOF'\n[\"{EM}\"]\nEOF"
    check("gh api --input - JSON: a one-character string is linted", em_dash_flagged(one_char), "not flagged")
    numbers = (
        "gh api graphql --input - <<'EOF'\n"
        '{"first": 100, "last": 100, "after": null, "before": null, "count": 12345,\n'
        ' "depth": 1}\nEOF'
    )
    check("gh api --input - JSON without strings: no hard wrap", bash_violations(numbers) == [], f"got {bash_violations(numbers)!r}")
    for name, cmd in (
        ("not JSON", f"gh api graphql --input - <<'EOF'\n[{query}EOF"),
        ("another program's --input -", f"gh pr view 1; curl --input - <<'EOF'\n{query}EOF"),
        ("gh api without --input -", f"gh api graphql -F query=@- <<'EOF'\n{query}EOF"),
        ("gh api --input file", f"gh api graphql --input q.json <<'EOF'\n{query}EOF"),
    ):
        found = bash_violations(cmd)
        check(
            f"{name}: linted as text as before",
            any("hard-wrapped" in v for v in found),
            f"got {found!r}",
        )

    def heredocs(cmd: str) -> list[str]:
        return [f[1] for f in lo.extract_bash_content(cmd) if "heredoc" in f[0]]

    notes = "- Rebased the branch onto main and reran the full suite after the conflict\n"
    tee = f"tee -a notes/x.md >/dev/null <<'EOF'\n{notes}EOF\ngit commit -m 'Update notes'"
    check("tee into a file: not the message", heredocs(tee) == [], f"got {heredocs(tee)!r}")
    bare = f"tee -a notes/x.md <<'EOF'\n{notes}EOF\ngit commit -m 'Update notes'"
    check("tee into a file, no redirect: not the message", heredocs(bare) == [], f"got {heredocs(bare)!r}")
    msg = "<<'MSG'\nAdd the lint workflow\nMSG\n"
    for name, cmd in (
        ("its file read back", f"tee /tmp/unit-msg.txt {msg}git commit -F /tmp/unit-msg.txt"),
        ("one of two files read back", f"tee -a a.md /tmp/unit-msg.txt {msg}git commit -F unit-msg.txt"),
        ("its stdout file read back", f"tee a.md > /tmp/unit-msg.txt {msg}git commit -F unit-msg.txt"),
        ("variable target, a file read back", f"tee $f {msg}git commit -F m.txt"),
        ("no file", f"tee {msg}git commit -m x"),
    ):
        check(f"tee, {name}: stays a payload", heredocs(cmd) == ["Add the lint workflow"], f"got {heredocs(cmd)!r}")


def test_multiple_m_flags() -> None:
    section("extract_bash_content: the -m flags of a commit form one message")
    subject = "Add a really long subject line that keeps going well past fifty"
    found = bash_violations(f'git commit -m "{subject}" -m "Body."')
    check(
        "a long first -m is flagged as the subject",
        any("commit subject is 63 chars" in v for v in found),
        f"got {found!r}",
    )
    paragraph = ("word " * 40).strip()
    found = bash_violations(f'git commit -m "Short subject" -m "{paragraph}"')
    check(
        "a long later -m is flagged as a body line",
        any("commit body line is 199 chars" in v for v in found),
        f"got {found!r}",
    )
    clean = 'git commit -m "Short subject" --message "Body paragraph."'
    check("a clean message passes", bash_violations(clean) == [], f"got {bash_violations(clean)!r}")
    fields = lo.extract_bash_content(clean)
    check(
        "one field, joined the way git joins it",
        fields == [("arg -m", "Short subject\n\nBody paragraph.", True, False, True)],
        f"got {fields!r}",
    )
    two = lo.extract_bash_content('git commit -m "First" && git commit --amend -m "Second"')
    check(
        "each commit is its own message",
        [(f[1], f[4]) for f in two] == [("First", True), ("Second", True)],
        f"got {two!r}",
    )
    mixed = lo.extract_bash_content(
        'git commit -m "Fix the gate" && gh pr create --title T -m "Q4"'
    )
    check(
        "gh's -m (a milestone) is not part of the commit message",
        [(f[1], f[2], f[4]) for f in mixed if f[0] == "arg -m"]
        == [("Fix the gate", True, True), ("Q4", True, False)],
        f"got {mixed!r}",
    )
    found = bash_violations('git commit -m "$subject" -m "Body."')
    check(
        "a variable -m among several is still blocked",
        any("bare shell-variable" in v for v in found),
        f"got {found!r}",
    )
    found = bash_violations('git commit -m "$msg"')
    check("a sole variable -m is blocked once", len(found) == 1, f"got {found!r}")


def test_body_file_path_is_not_the_body() -> None:
    section("extract_bash_content: a --body-file path is not the body")
    for quote in ('"', "'", ""):
        cmd = f"gh pr create --title T --body-file {quote}/Users/nobody/w/pr-1.md{quote}"
        found = bash_violations(cmd)
        check(f"quote {quote or 'none'}: path not linted", found == [], f"got {found!r}")
    found = bash_violations('gh pr create --title T --body-file "$f"')
    check(
        "a quoted variable is still blocked as a bypass",
        any("bare shell-variable" in v for v in found),
        f"got {found!r}",
    )
    found = bash_violations("gh pr create --title T --body-file $f")
    check("an unquoted variable passes as before", found == [], f"got {found!r}")


TESTS = [
    test_table_padding_source_width,
    test_commit_subject_exemptions,
    test_commit_body_rules,
    test_interpreter_heredoc_skipped,
    test_file_heredoc_is_not_the_message,
    test_markdown_heredoc_writes,
    test_compound_command_flag_ownership,
    test_gh_api_at_file_read_not_blocked,
    test_hard_wrap_detector,
    test_cat_heredoc_subst_wrapper_redacted,
    test_label_colon_rules,
    test_plain_label_colon_detector,
    test_autofix_resolves_detected,
    test_try_autofix_input_scope,
    test_autofix_identifier_and_heredoc,
    test_main_autofix_end_to_end,
    test_tool_attribution_footer,
    test_git_global_flags_before_commit,
    test_in_repo_path_prefixes,
    test_linear_mirror_paths_skip_lint,
    test_archive_cleanup_false_positives,
    test_wrapped_code_span,
    test_short_combined_and_owned_flags,
    test_code_and_data_heredocs,
    test_multiple_m_flags,
    test_body_file_path_is_not_the_body,
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
