#!/usr/bin/env python3
"""
Deterministic unit tests for ~/.claude/hooks/lint-outbound.py.

Covers the regex layer end to end: table-padding measured on source width,
commit subject/body length rules and their exemptions, payload extraction from
Bash (interpreter heredocs, heredocs written into Markdown files,
compound-command flag ownership, gh `@file` bodies), the hard-wrap detector,
and the label-colon capitalization rules. Most cases are regressions for the
2026-07-06 false-positive batch.

Run: python3 .claude/evals/lint-outbound/test_unit.py
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
import traceback
from pathlib import Path

HOOK_PATH = Path(__file__).resolve().parents[2] / "hooks" / "lint-outbound.py"
SETTINGS_PATH = HOOK_PATH.parents[1] / "settings.json"

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
    """Pad a two-column table to equal SOURCE width, the way an editor (and
    rules/typography.md) aligns it."""
    widths = [max(len(r[i]) for r in rows if r is not None) for i in range(2)]
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
    aligned = "| Col A | Col B |\n| :--- | ---: |\n| x | y |\n"
    check(
        "alignment colons still mark the separator row",
        len(lo.detect_table_padding(aligned)) > 0,
        "not flagged",
    )
    aligned_ok = "| Col A | Col B |\n| :---- | ----: |\n| x     | y     |\n"
    check(
        "padded table with alignment colons passes",
        lo.detect_table_padding(aligned_ok) == [],
        f"got {lo.detect_table_padding(aligned_ok)!r}",
    )
    no_separator = "| a | b |\n| long cell | x |\n"
    check(
        "pipe rows without a separator row are not a table",
        lo.detect_table_padding(no_separator) == [],
        f"got {lo.detect_table_padding(no_separator)!r}",
    )
    tilde = f"~~~\n{bad}~~~\n"
    check(
        "table inside tilde fence ignored",
        lo.detect_table_padding(tilde) == [],
        f"got {lo.detect_table_padding(tilde)!r}",
    )
    for row, cells in [
        ("| x \\| y | z |", [" x \\| y ", " z "]),
        ("| a | b \\|", [" a ", " b \\|"]),
    ]:
        check(
            f"escaped pipe stays in its cell: {row}",
            lo.split_table_row(row) == cells,
            f"got {lo.split_table_row(row)!r}",
        )
    check(
        "lint_text reports the padding",
        any("padded" in v for v in lo.lint_text(bad, "f", check_local_paths=False)),
        "not reported",
    )


def test_commit_subject_exemptions() -> None:
    section("lint_commit_message: subject-length rule and exemptions")
    slug = (
        "BYB-1345: Membership Upgrade Creates Duplicate Active Subscriptions in Stripe"
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
    for label, subject, expected in [
        ("50-char subject passes", "A" * 50, 0),
        ("51-char subject flagged", "A" * 51, 1),
        ("trailing spaces not counted", "A" * 50 + "  ", 0),
        ("Revert subject exempt", f'Revert "{plain}"', 0),
        (
            "breaking-change subject exempt",
            "feat!: drop the legacy flag from the outbound linter",
            0,
        ),
        ("Conventional subject of exactly 72 exempt", conv + " too", 0),
        ("Conventional subject past 72 flagged", conv + " also", 1),
    ]:
        got = lo.lint_commit_message(subject, "f")
        check(label, len(got) == expected, f"got {got!r}")


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
    code = (
        "result = compute(alpha, beta, gamma, delta, epsilon, zeta, eta, theta, iota)"
    )
    for fence in ("```", "~~~"):
        msg = f"Short subject\n\n{fence}\n{code}\n{fence}\n"
        check(
            f"long code line with spaces inside {fence} fence exempt",
            lo.lint_commit_message(msg, "f") == [],
            f"got {lo.lint_commit_message(msg, 'f')!r}",
        )
    token = "Short subject\n\n" + "a" * 80 + "\n"
    check(
        "long single token exempt",
        lo.lint_commit_message(token, "f") == [],
        f"got {lo.lint_commit_message(token, 'f')!r}",
    )
    for width, expected in [(72, 0), (73, 1)]:
        msg = "Short subject\n\n" + ("word " * 15)[:width] + "\n"
        check(
            f"{width}-char body line: {expected} violation(s)",
            len(lo.lint_commit_message(msg, "f")) == expected,
            f"got {lo.lint_commit_message(msg, 'f')!r}",
        )
    check("empty message passes", lo.lint_commit_message("", "f") == [])


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

    def heredocs(cmd: str) -> list[str]:
        return [f[0] for f in lo.extract_bash_content(cmd) if "heredoc" in f[0]]

    owners = [
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
    ]
    extracted = [
        name
        for name in owners
        if heredocs(f"gh api repos/o/r && {name} <<'EOF'\nnot prose\nEOF")
    ]
    check("code and data heredocs not extracted", extracted == [], f"got {extracted!r}")
    for name in ("python3", "sort"):
        for label, cmd in [
            ("after a pipe", f"gh api repos/o/r | {name} <<'EOF'\nx\nEOF"),
            ("after a semicolon", f"gh api repos/o/r; {name} <<'EOF'\nx\nEOF"),
            ("on the next line", f"gh api repos/o/r\n{name} <<'EOF'\nx\nEOF"),
            (
                "in a substitution",
                f"gh api repos/o/r && x=\"$({name} <<'EOF'\nx\nEOF\n)\"",
            ),
            ("by full path", f"gh api repos/o/r && /usr/bin/{name} <<'EOF'\nx\nEOF"),
        ]:
            check(
                f"{name} {label} not extracted",
                heredocs(cmd) == [],
                f"got {heredocs(cmd)!r}",
            )
    for marker in ("-EOF", '"EOF"'):
        cmd = (
            f"gh pr create --title T --body-file - <<{marker}\n"
            "Adds a \u201cgate\u201d finally.\nEOF"
        )
        violations = lo.collect_violations("Bash", {"command": cmd})
        check(
            f"<<{marker} heredoc still linted",
            any("left double quote" in v for v in violations),
            f"got {violations!r}",
        )
    flag_text = (
        "gh pr create --title T --body-file - <<'EOF'\n"
        'Scripts pass --body "$BODY" to gh.\nEOF'
    )
    check(
        "flag text inside a heredoc body is not a flag",
        lo.collect_violations("Bash", {"command": flag_text}) == [],
        f"got {lo.collect_violations('Bash', {'command': flag_text})!r}",
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


def test_markdown_heredoc_writes() -> None:
    section("extract_fields: heredocs written into Markdown files are linted")
    bad = "Done \u201cshipped\u201d.\n"
    flagged = {
        "cat >> before marker": f"cat >> notes/2026-10-15.md <<'EOF'\n{bad}EOF",
        "redirect after marker": f"cat <<'EOF' >> notes/2026-10-15.md\n{bad}EOF",
        "tee -a": f"tee -a /tmp/pr-body.md <<EOF >/dev/null\n{bad}EOF",
        "after a cd": f"cd ~/x && cat > 'a b/n.md' <<EOF\n{bad}EOF",
        "double-quoted target": f'cat > "a b/n.md" <<EOF\n{bad}EOF',
        ".markdown target": f"cat > notes/n.markdown <<'EOF'\n{bad}EOF",
        "tee without -a": f"tee /tmp/pr-body.md <<'EOF' >/dev/null\n{bad}EOF",
    }
    for name, cmd in flagged.items():
        violations = lo.collect_violations("Bash", {"command": cmd})
        check(
            f"{name}: smart quote flagged",
            any("left double quote" in v for v in violations),
            f"got {violations!r}",
        )
    skipped = {
        "non-Markdown target": f"cat > out.txt <<'EOF'\n{bad}EOF",
        "interpreter heredoc": f"python3 - <<'PY' > out.md\n{bad}PY",
        "variable target": f'cat >> "$f" <<EOF\n{bad}EOF',
        "no redirect": f"cat <<'EOF'\n{bad}EOF",
        "variable in a bare target": f"cat >> $dir/n.md <<EOF\n{bad}EOF",
        "Markdown backup target": f"cat > n.md.bak <<'EOF'\n{bad}EOF",
        "earlier command after ;": f"echo x > 'a.md'; cat <<'EOF'\n{bad}EOF",
        "earlier command after &&": f"echo x > a.md && cat <<'EOF'\n{bad}EOF",
        "earlier command on its own line": f"echo x > a.md\ncat <<'EOF'\n{bad}EOF",
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
    note = "See ~/.claude/rules/git.md for the rule.\n"
    in_repo = f"cat >> ~/nickolashkraus/notes/n.md <<'EOF'\n{note}EOF"
    check(
        "in-repo target may name local paths",
        not lo.collect_violations("Bash", {"command": in_repo}),
        f"got {lo.collect_violations('Bash', {'command': in_repo})!r}",
    )
    external = f"cat >> /tmp/pr-body.md <<'EOF'\n{note}EOF"
    check(
        "external target may not name local paths",
        any(
            "local-only path" in v
            for v in lo.collect_violations("Bash", {"command": external})
        ),
        "not flagged",
    )


def test_cat_heredoc_subst_wrapper_redacted() -> None:
    section("extract_bash_content: $(cat <<'EOF') wrapper leaves no -m residue")
    cmd = (
        "git commit -m \"$(cat <<'EOF'\n"
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

    def violations(cmd: str) -> list[str]:
        return lo.collect_violations("Bash", {"command": cmd})

    trailer = "Co-" + "Authored-By: Claude <noreply@anthropic.com>"
    long_form = f"git commit --message 'Short subject' --message '{trailer}'"
    check(
        "--message is commit-owned",
        any("Co-Authored-By" in v for v in violations(long_form)),
        f"got {violations(long_form)!r}",
    )
    paragraphs = (
        "git commit -m 'Short subject' "
        "-m 'A body paragraph that runs well past the fifty-character limit.'"
    )
    check(
        "a second -m is a body paragraph, not a subject",
        not any("subject" in v for v in violations(paragraphs)),
        f"got {violations(paragraphs)!r}",
    )
    curly = "Adds a \u201cgate\u201d finally."
    for label, cmd in [
        ("double-quoted --body", f'gh pr create --title "T" --body "{curly}"'),
        ("gh issue create", f"gh issue create --title T --body '{curly}'"),
    ]:
        check(
            f"{label}: smart quote flagged",
            any("left double quote" in v for v in violations(cmd)),
            f"got {violations(cmd)!r}",
        )
    edit = "gh pr edit 12 --body 'Fixes #12'"
    check(
        "gh pr edit --body is a PR body",
        any("Closes:" in v for v in violations(edit)),
        f"got {violations(edit)!r}",
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
    check(
        "text that starts with a $var is not a bypass",
        lo.is_bypass_value("$PATH is unchanged") is None,
        "blocked",
    )

    def violations(cmd: str) -> list[str]:
        return lo.collect_violations("Bash", {"command": cmd})

    for label, cmd in [
        ("bare $var", 'gh pr create --title T --body "$BODY"'),
        ("braced ${var}", 'gh pr create --title T --body "${BODY}"'),
    ]:
        check(
            f"{label} body blocked",
            any("bare shell-variable" in v for v in violations(cmd)),
            f"got {violations(cmd)!r}",
        )

    curly = "Adds a \u201cgate\u201d finally."
    for flag in ("-f", "-F", "--field", "--raw-field"):
        for name in ("body", "title"):
            cmd = f"gh api repos/x/y/issues {flag} {name}='{curly}'"
            check(
                f"gh api {flag} {name}= linted",
                any("left double quote" in v for v in violations(cmd)),
                f"got {violations(cmd)!r}",
            )

    with tempfile.TemporaryDirectory() as tmp:
        body = Path(tmp) / "body.md"
        body.write_text("Adds the gate.\n\nCloses: BYB-1\n")
        curly_file = Path(tmp) / "curly_file.md"
        curly_file.write_text(curly + "\n")
        msg = Path(tmp) / "msg.txt"
        msg.write_text(
            "Add a really long subject line that keeps going well past fifty\n"
        )
        signed = Path(tmp) / "signed.txt"
        signed.write_text(
            "Short subject\n\nCo-" + "Authored-By: Claude <noreply@anthropic.com>\n"
        )
        for label, cmd, needle in [
            ("--body-file", f"gh pr create --title T --body-file {body}", "Closes:"),
            (
                "quoted --body-file",
                f"gh pr create --title T --body-file '{body}'",
                "Closes:",
            ),
            (
                "quoted @file",
                f"gh api repos/x/y/issues -F body=@'{curly_file}'",
                "left double quote",
            ),
            ("git commit -F", f"git commit -F {msg}", "commit subject"),
            ("git commit --file=", f"git commit --file={msg}", "commit subject"),
            ("quoted git commit -F", f"git commit -F '{msg}'", "commit subject"),
            ("git commit -F trailer", f"git commit -F {signed}", "Co-Authored-By"),
        ]:
            check(
                f"{label}: file read and linted",
                any(needle in v for v in violations(cmd)),
                f"got {violations(cmd)!r}",
            )
        gh_short = f"gh pr create --title T -F {msg}"
        check(
            "gh -F is not read as a commit message",
            not any("commit subject" in v for v in violations(gh_short)),
            f"got {violations(gh_short)!r}",
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
    long = "A" * 64
    cases = [
        ("64-char line then a wrap", f"{long}\nmore\n", [2]),
        ("63-char line then a short line", f"{long[:-1]}\nmore\n", []),
        ("only the line after the long one", f"{long}\nshort\nthird\n", [2]),
        ("list item after a wrapped line", f"{long}\n{long}\n- item\n", [2]),
        ("header after a long line", f"{long}\n## Header\n", []),
        ("blank line after a long line", f"{long}\n\nNext paragraph.\n", []),
        ("fence after a long line", f"{long}\n```\ncode\n```\nNext\n", []),
        ("reference definition", f"{long}\n[a]: https://example.com/a\n", []),
        ("Notion XML line", f"{long}\n<callout>\n", []),
        ("table rows", f"| {long} |\n| --- |\n", []),
        ("blockquote", f"> {long}\n> more\n", []),
        ("backtick fence", f"```\n{long}\nmore\n```\n", []),
        ("tilde fence", f"~~~\n{long}\nmore\n~~~\n", []),
    ]
    for marker in ("-", "*", "+", "1.", "2)"):
        cases.append((f"`{marker}` list item", f"{long}\n{marker} item\n", []))
    for label, text, expected in cases:
        got = lo.detect_hard_wraps(text)
        check(label, got == expected, f"got {got!r}")

    wrapped = f"{long}\nmore\n"
    with tempfile.TemporaryDirectory() as tmp:
        draft = {"file_path": f"{tmp}/pr-body.md", "content": wrapped}
        check(
            "external Markdown draft: hard wrap flagged",
            any("hard-wrapped" in v for v in lo.collect_violations("Write", draft)),
            f"got {lo.collect_violations('Write', draft)!r}",
        )
    doc = f"{Path.home()}/nickolashkraus/lint-outbound-test/README.md"
    in_repo = {"file_path": doc, "content": wrapped}
    check(
        "in-repo Markdown: hard wrap allowed",
        lo.collect_violations("Write", in_repo) == [],
        f"got {lo.collect_violations('Write', in_repo)!r}",
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
    for line in (
        "* **Element**: description\n",
        "+ **Element**: description\n",
        "1. **Element**: description\n",
        "1) **Element**: description\n",
        "- [Docs](https://x): description\n",
    ):
        check(
            f"flagged: {line.strip()}",
            any("colon" in v for v in lint(line)),
            "not flagged",
        )
    for line in (
        "- **Element** - description\n",
        "* **Element** - description\n",
        "1. **Element** - description\n",
        "- **Element** \u2014 description\n",
        "- **Element** \u2013 description\n",
    ):
        check(
            f"dash lead-in flagged: {line.strip()}",
            any("`**X** -`" in v for v in lint(line)),
            f"got {lint(line)!r}",
        )
    for dash in ("-", "\u2014", "\u2013"):
        later = f"- **Element**: Description {dash} with a dash\n"
        check(
            f"U+{ord(dash):04X} later in the item is legal",
            lint(later) == [],
            f"got {lint(later)!r}",
        )
    check(
        "reference shorthand flagged",
        any("shorthand" in v for v in lint("See [docs][] here.\n")),
        "not flagged",
    )
    for text in ("See [docs][ref] here.\n", "Avoid `[docs][]` here.\n"):
        check(f"legal: {text.strip()}", lint(text) == [], f"got {lint(text)!r}")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "note.md"
        path.write_text("[Docs](https://x): lowercase title\n- Overview: the summary\n")
        kept = {"file_path": str(path), "content": path.read_text()}
        check(
            "existing link and plain label lines keep their wording",
            lo.collect_violations("Write", kept) == [],
            f"got {lo.collect_violations('Write', kept)!r}",
        )


def test_plain_label_colon_detector() -> None:
    section("plain_label_colon_violation: Title-Case plain labels only")

    def flagged(line: str) -> bool:
        return lo.plain_label_colon_violation(line)

    # Title-Case / acronym plain-text labels with a lowercase word after the
    # colon are flagged.
    check(
        "multiword Title-Case label", flagged("- Conventional Commits: the carve-out\n")
    )
    check("single-word label", flagged("- Overview: the summary here\n"))
    check("acronym + connector label", flagged("- Terms of Service: some text\n"))
    check(
        "numbered Title-Case label", flagged("1. Rollback Plan: revert the migration\n")
    )

    # Not flagged: lowercase word after a capitalized label IS correct.
    check("capitalized value passes", not flagged("- Overview: The summary here\n"))
    # Not flagged: imperative instruction bullets (lowercase content words).
    check(
        "imperative instruction not flagged",
        not flagged("2. Trace the data lifecycle: creation and updates\n"),
    )
    check(
        "imperative check not flagged",
        not flagged("- Check edge cases: empty inputs\n"),
    )
    # Not flagged: lowercase-tail label is indistinguishable from a clause here
    # and is deferred to the semantic check.
    check(
        "lowercase-tail label deferred",
        not flagged("- PR titles: when a PR resolves\n"),
    )
    # Not flagged: bold/link/code labels are handled by the dedicated regexes.
    check(
        "bold label deferred to bold regex", not flagged("- **Element**: description\n")
    )
    # Not flagged: clause colon in flowing prose.
    check(
        "clause colon not flagged",
        not flagged("- Note the entry was stale: it declared a field\n"),
    )
    for word in ("and", "to", "for", "the", "a", "an", "in", "on", "with", "or"):
        check(
            f"connector {word!r} inside a label",
            flagged(f"- Alpha {word} Beta: some text\n"),
        )
    check("four-word label", flagged("- One Two Three Four: some text\n"))
    check(
        "five-word label not flagged",
        not flagged("- One Two Three Four Five: some text\n"),
    )
    check(
        "lowercase connector cannot start a label",
        not flagged("- the Plan: some text\n"),
    )
    check("empty label not flagged", not flagged("-  : some text\n"))
    check("star bullet label", flagged("* Overview: the summary here\n"))


def test_punctuation_outside_code() -> None:
    section("lint_text: smart quotes flagged outside code, dashes legal")

    def lint(text: str) -> list[str]:
        return lo.lint_text(text, "f", check_local_paths=False)

    for ch in ("\u201c", "\u201d", "\u2018", "\u2019"):
        check(
            f"smart quote U+{ord(ch):04X} flagged",
            any("quote" in v for v in lint(f"Say {ch}hi now.\n")),
            "not flagged",
        )
    pair = lint("Say \u201chi\u201d now.\n")
    check("one smart-quote report per line", len(pair) == 1, f"got {pair!r}")
    for name, text in (
        ("em dash", "Wait \u2014 no.\n"),
        ("en dash", "Pages 1\u20132.\n"),
        ("both dashes on one line", "Wait \u2014 see pages 1\u20132.\n"),
    ):
        check(f"{name} is legal", lint(text) == [], f"got {lint(text)!r}")
    span = "Run `a \u201cb\u201d` now.\n"
    check(
        "smart quote in a code span is legal", lint(span) == [], f"got {lint(span)!r}"
    )
    for fence in ("```", "~~~"):
        text = f"{fence}\na \u201cb\u201d\n{fence}\n"
        check(
            f"smart quotes in a {fence} fence are legal",
            lint(text) == [],
            f"got {lint(text)!r}",
        )


def test_dashes_pass_on_every_surface() -> None:
    section("collect_violations: dashes pass; smart quotes and dash lead-ins fail")

    def surfaces(text: str, tmp: str) -> list[tuple[str, str, dict]]:
        sentence = f"It closes {text}."
        doc = f"{tmp}/doc.md"
        return [
            (
                "commit subject",
                "Bash",
                {"command": f'git commit -m "Close the gate {text}"'},
            ),
            (
                "commit body",
                "Bash",
                {
                    "command": f"git commit -F - <<'EOF'\nClose the gate\n\n{sentence}\nEOF"
                },
            ),
            (
                "PR title",
                "Bash",
                {"command": f'gh pr create --title "Close the gate {text}" --body B'},
            ),
            (
                "PR body",
                "Bash",
                {"command": f'gh pr create --title T --body "{sentence}"'},
            ),
            (
                "PR comment",
                "Bash",
                {"command": f"gh pr comment 12 --body '{sentence}'"},
            ),
            (
                "Markdown edit",
                "Edit",
                {"file_path": doc, "new_string": f"{sentence}\n"},
            ),
            ("Markdown write", "Write", {"file_path": doc, "content": f"{sentence}\n"}),
            (
                "Markdown heredoc",
                "Bash",
                {"command": f"cat >> notes/a.md <<'EOF'\n{sentence}\nEOF"},
            ),
            ("MCP payload", "mcp__linear__save_comment", {"body": sentence}),
        ]

    with tempfile.TemporaryDirectory() as tmp:
        for dash_name, text in (
            ("em dash", "\u2014 at noon"),
            ("en dash", "\u2013 pages 1\u20132"),
        ):
            for name, tool, tool_input in surfaces(text, tmp):
                found = lo.collect_violations(tool, tool_input)
                check(f"{name}: {dash_name} passes", found == [], f"got {found!r}")
        for name, tool, tool_input in surfaces("\u201cat noon\u201d", tmp):
            found = lo.collect_violations(tool, tool_input)
            check(
                f"{name}: smart quote still fails",
                any("left double quote" in v for v in found),
                f"got {found!r}",
            )
        for dash in ("-", "\u2014", "\u2013"):
            item = f"- **Gate** {dash} closes at noon"
            for name, tool, tool_input in (
                (
                    "PR body",
                    "Bash",
                    {"command": f"gh pr create --title T --body '{item}'"},
                ),
                (
                    "Markdown edit",
                    "Edit",
                    {"file_path": f"{tmp}/doc.md", "new_string": item},
                ),
                ("MCP payload", "mcp__linear__save_comment", {"body": item}),
            ):
                found = lo.collect_violations(tool, tool_input)
                check(
                    f"{name}: U+{ord(dash):04X} list lead-in still fails",
                    any("`**X** -`" in v for v in found),
                    f"got {found!r}",
                )


def test_british_spellings() -> None:
    section("lint_text: British spellings flagged, American ones left alone")

    def british(text: str) -> list[str]:
        return [
            v
            for v in lo.lint_text(text, "f", check_local_paths=False)
            if "British" in v
        ]

    words = [
        "amongst",
        "behaviour",
        "behavioural",
        "behaviours",
        "cancelled",
        "cancelling",
        "canonicalise",
        "canonicalised",
        "canonicalises",
        "canonicalising",
        "centre",
        "centred",
        "centres",
        "centring",
        "colour",
        "coloured",
        "colourful",
        "colours",
        "defence",
        "defences",
        "fulfil",
        "fulfils",
        "initialise",
        "initialised",
        "initialises",
        "initialising",
        "labelled",
        "labelling",
        "learnt",
        "licence",
        "licences",
        "modelled",
        "modelling",
        "normalise",
        "normalised",
        "normalises",
        "normalising",
        "optimise",
        "optimised",
        "optimises",
        "optimising",
        "organisation",
        "organisations",
        "organise",
        "organised",
        "organises",
        "organising",
        "prioritise",
        "prioritised",
        "prioritises",
        "prioritising",
        "recognisable",
        "recognise",
        "recognised",
        "recognises",
        "recognising",
        "serialise",
        "serialised",
        "serialises",
        "serialising",
        "summarise",
        "summarised",
        "summarises",
        "summarising",
        "travelled",
        "travelling",
        "whilst",
    ]
    missed = [w for w in words if len(british(f"The {w} here.\n")) != 1]
    check("every British form flagged", missed == [], f"missed {missed!r}")
    wrong = [w for w in lo.BRITISH_SPELLINGS.values() if british(f"The {w} here.\n")]
    check("every American replacement legal", wrong == [], f"flagged {wrong!r}")
    found = british("Behaviour changed.\n")
    check(
        "capitalized form flagged with a capitalized fix",
        len(found) == 1 and '"Behavior"' in found[0],
        f"got {found!r}",
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "note.md"
        path.write_text("The colour stays.\n")
        kept = {"file_path": str(path), "content": path.read_text()}
        check(
            "existing line keeps its spelling",
            lo.collect_violations("Write", kept) == [],
            f"got {lo.collect_violations('Write', kept)!r}",
        )


def test_ai_slop_catalog() -> None:
    section("lint_text: every AI-slop phrase and context noun is caught")

    def slop(text: str) -> list[str]:
        return [
            v
            for v in lo.lint_text(text, "f", check_local_paths=False)
            if "AI slop" in v
        ]

    phrases = [
        "It's not just a cache.",
        "That's not merely cosmetic.",
        "The fix is not only faster.",
        "They are not just labels.",
        "Not only faster but also safer.",
        "Great question!",
        "You're absolutely right.",
        "Good catch!",
        "Let me help you with that.",
        "I'd be happy to.",
        "As an AI, I can.",
        "Based on my analysis, yes.",
        "It's worth noting that.",
        "It seems like a bug.",
        "In my opinion, yes.",
        "In summary, yes.",
        "To wrap up, yes.",
        "Let me know if you have any questions.",
        "Feel free to ping me.",
        "We delved into it.",
        "We are leveraging it.",
        "We utilized it.",
        "A robust fix.",
        "A seamless move.",
        "A comprehensive list.",
        "A crucial step.",
        "A load-bearing check.",
        "A load bearing check.",
        "There are pros and cons.",
        "The data lands in BigQuery.",
        "The ID rides along.",
        "The ID is riding along.",
        "It stamps the UUID.",
        "It rides along in `meta`.",
    ]
    missed = [p for p in phrases if len(slop(p + "\n")) != 1]
    check("every phrase flagged once", missed == [], f"missed {missed!r}")
    found = slop("Not only faster but also safer.\n")
    check(
        "antithesis report quotes the whole phrase",
        len(found) == 1 and "`Not only faster but also`" in found[0],
        f"got {found!r}",
    )
    nouns = [
        "data",
        "event",
        "commit",
        "PR",
        "request",
        "response",
        "message",
        "metadata",
        "identifier",
        "ID",
        "UUID",
        "field",
        "payload",
        "change",
        "deploy",
        "release",
        "branch",
        "master",
        "main",
        "queue",
        "log",
        "record",
        "row",
        "column",
        "token",
        "header",
        "ticket",
        "issue",
        "merge",
        "migration",
        "fix",
        "patch",
        "build",
        "pipeline",
        "job",
        "webhook",
        "API",
        "endpoint",
        "service",
        "stack",
        "database",
        "table",
        "object",
        "file",
        "bucket",
        "version",
        "tag",
        "SHA",
        "hash",
        "worker",
        "subscriber",
        "topic",
        "callback",
        "parameter",
        "argument",
        "variable",
        "config",
        "cache",
        "CI",
        "Prod",
        "Staging",
    ]
    missed = [n for n in nouns if not slop(f"The {n} lands today.\n")]
    check(
        "every context noun makes the verb figurative",
        missed == [],
        f"missed {missed!r}",
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
        check(
            f"resolves: {line.strip()[:32]}",
            lint(fixed) == [],
            f"still: {lint(fixed)!r}",
        )

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
    for fence in ("```", "~~~"):
        block = f"{fence}\n- **Element**: description\n{fence}\n"
        check(
            f"label inside {fence} fence untouched",
            lo.autofix_label_colons(block) == block,
        )


def test_try_autofix_input_scope() -> None:
    section("try_autofix_input: Edit/Write Markdown only, pure label-colon")

    md = "/Users/x/repo/doc.md"
    # Pure label-colon Edit is fixed and re-lints clean.
    ti = {"file_path": md, "new_string": "- **Element**: description\n"}
    fixed = lo.try_autofix_input("Edit", ti)
    check(
        "edit returns modified input",
        fixed is not None and fixed["new_string"].startswith("- **Element**: D"),
    )
    check("fixed edit re-lints clean", lo.collect_violations("Edit", fixed) == [])

    # Mixed violation: label-colon fix applied but a smart quote remains, so
    # main must still block (collect_violations on the fix is non-empty).
    ti2 = {"file_path": md, "new_string": "- **Element**: description \u201cx\u201d\n"}
    fixed2 = lo.try_autofix_input("Edit", ti2)
    check(
        "mixed still has violations",
        fixed2 is not None and lo.collect_violations("Edit", fixed2) != [],
    )

    # Non-label content: nothing to fix.
    ti3 = {"file_path": md, "new_string": "- **Element**: Description\n"}
    check("clean content -> None", lo.try_autofix_input("Edit", ti3) is None)

    # Bash commit/PR bodies are never auto-fixed.
    check(
        "bash -> None",
        lo.try_autofix_input("Bash", {"command": "git commit -m 'x'"}) is None,
    )

    # MCP payloads are never auto-fixed.
    notion = {"content": "- **Element**: description\n"}
    check(
        "MCP -> None",
        lo.try_autofix_input("mcp__notion__notion-update-page", notion) is None,
    )

    # Lines already in the file keep their wording; only new ones are fixed.
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "note.md"
        path.write_text("- **Name**: lowercase reply\n")
        ti4 = {
            "file_path": str(path),
            "content": path.read_text() + "- **New**: description\n",
        }
        fixed4 = lo.try_autofix_input("Write", ti4)
        check(
            "existing line kept, new line fixed",
            fixed4 is not None
            and fixed4["content"]
            == "- **Name**: lowercase reply\n- **New**: Description\n",
            f"got {fixed4!r}",
        )


def test_autofix_identifier_and_heredoc() -> None:
    section("autofix: skips identifiers, rewrites Markdown heredoc bodies")
    for line in (
        "- **Repo**: ppp-service is live",
        "- **SHA**: a1b2c3d",
        "- **CLI**: v2.1",
        "- **Column**: user_id is unique",
        "- **Path**: src/app is new",
        "- **Site**: example.com is live",
    ):
        check(
            f"identifier left unfixed: {line}",
            lo.autofix_label_colon_line(line) is None,
        )
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
    check(
        "identifier after a plain label left unfixed",
        lo.autofix_label_colon_line("- Repo Name: ppp-service is live") is None,
    )
    cmd = "cat >> notes/a.md <<'EOF'\n- **Email**: inbox zero\nEOF\necho ok"
    fixed = lo.try_autofix_input("Bash", {"command": cmd, "description": "d"})
    check(
        "heredoc body capitalized, rest of command intact",
        fixed
        == {
            "command": "cat >> notes/a.md <<'EOF'\n- **Email**: Inbox zero\nEOF\necho ok",
            "description": "d",
        },
        f"got {fixed!r}",
    )
    check("fixed command lints clean", not lo.collect_violations("Bash", fixed or {}))
    check(
        "non-Markdown heredoc not rewritten",
        lo.try_autofix_input(
            "Bash", {"command": "cat > a.txt <<'EOF'\n- **E**: x\nEOF"}
        )
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
            check=False,
        )
        return p.returncode, p.stdout, p.stderr

    md = "/Users/x/repo/doc.md"
    rc, out, _ = run(
        {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": md,
                "new_string": "- **Element**: description\n",
            },
        }
    )
    ok = rc == 0 and out.strip() != ""
    parsed = _json.loads(out) if ok else {}
    hso = parsed.get("hookSpecificOutput", {})
    check("exit 0 with JSON", ok, f"rc={rc} out={out!r}")
    check(
        "permissionDecision allow", hso.get("permissionDecision") == "allow", f"{hso!r}"
    )
    check(
        "updatedInput capitalized",
        hso.get("updatedInput", {})
        .get("new_string", "")
        .startswith("- **Element**: D"),
        f"{hso.get('updatedInput')!r}",
    )

    rc2, _, err2 = run(
        {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": md,
                "new_string": "- **Element**: description \u201cx\u201d\n",
            },
        }
    )
    check("mixed blocks (exit 2)", rc2 == 2, f"rc={rc2}")
    check("mixed reports the smart quote", "left double quote" in err2, err2)

    cmd = "cat >> notes/a.md <<'EOF'\n- **Email**: inbox zero\nEOF"
    rc3, out3, _ = run({"tool_name": "Bash", "tool_input": {"command": cmd}})
    hso3 = (
        _json.loads(out3).get("hookSpecificOutput", {})
        if rc3 == 0 and out3.strip()
        else {}
    )
    check(
        "bash heredoc: updatedInput capitalized",
        "**Email**: Inbox zero" in hso3.get("updatedInput", {}).get("command", ""),
        f"rc={rc3} out={out3!r}",
    )


def test_main_fails_open() -> None:
    section("main: unreadable or unexpected payloads are allowed")
    import json as _json
    import subprocess as _sub

    def run(stdin: str) -> int:
        p = _sub.run(
            [sys.executable, str(HOOK_PATH)],
            input=stdin,
            capture_output=True,
            text=True,
            check=False,
        )
        return p.returncode

    check("invalid JSON allowed", run("not json") == 0)
    payload = {
        "tool_name": "mcp__x__y",
        "tool_input": ["Adds a \u201cgate\u201d finally."],
    }
    check("non-dict tool_input allowed", run(_json.dumps(payload)) == 0)


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
        (
            "claude.ai link",
            f"{robot} Generated with [Claude Code](https://claude.ai/code)\n",
        ),
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


def test_commit_trailer_and_autoclose() -> None:
    section("lint_text: Co-Authored-By in commits, Closes: in PR bodies")
    trailer = "Co-" + "Authored-By: Claude <noreply@anthropic.com>\n"

    def coauthor(text: str, allow_coauthor: bool) -> bool:
        violations = lo.lint_text(
            text, "f", allow_coauthor=allow_coauthor, check_local_paths=False
        )
        return any("Co-Authored-By" in v for v in violations)

    check("commit trailer blocked", coauthor(trailer, False))
    check("lowercase commit trailer blocked", coauthor(trailer.lower(), False))
    check(
        "trailer named mid-line is legal", not coauthor("Never add a " + trailer, False)
    )
    check("trailer outside a commit is legal", not coauthor(trailer, True))
    mcp = lo.collect_violations("mcp__linear__save_comment", {"body": trailer})
    check(
        "trailer in a Linear comment is legal",
        not any("Co-Authored-By" in v for v in mcp),
        f"got {mcp!r}",
    )

    def autoclose(text: str, is_pr_body: bool = True) -> bool:
        violations = lo.lint_text(
            text, "f", is_pr_body=is_pr_body, check_local_paths=False
        )
        return any("Closes:" in v for v in violations)

    for text in (
        "Closes: BYB-1\n",
        "Fixes #12\n",
        "Resolves: BYB-1\n",
        "closes: BYB-1\n",
        "Adds the gate.\n\nCloses: BYB-1\n",
    ):
        check(f"PR body blocked: {text.splitlines()[-1]}", autoclose(text))
    check(
        "clause colon after resolves is legal",
        not autoclose("The query never resolves: it times out.\n"),
    )
    check("keyword outside a PR body is legal", not autoclose("Closes: BYB-1\n", False))
    mcp = lo.collect_violations("mcp__linear__save_comment", {"body": "Closes: BYB-1"})
    check(
        "keyword in a Linear comment is legal",
        not any("Closes:" in v for v in mcp),
        f"got {mcp!r}",
    )


def test_local_paths_in_external_content() -> None:
    section("lint_text: local-only paths are blocked in external content")

    def local(text: str, external: bool = True) -> bool:
        violations = lo.lint_text(text, "f", check_local_paths=external)
        return any("local-only path" in v for v in violations)

    for path in (
        "agent-os/master/notes/x.md",
        "~/nickolashkraus/agent-os",
        "~/.claude/rules/git.md",
        "~/dotfiles/README.md",
        "/Users/x/notes.md",
    ):
        text = f"See {path} for details.\n"
        check(f"blocked: {path}", local(text))
        check(f"allowed in-repo: {path}", not local(text, external=False))
    note = "See ~/.claude/rules/git.md for details."
    for tool, tool_input in [
        ("Bash", {"command": f"gh pr create --title T --body '{note}'"}),
        ("mcp__linear__save_comment", {"body": note}),
    ]:
        violations = lo.collect_violations(tool, tool_input)
        check(
            f"blocked in a {tool} payload",
            any("local-only path" in v for v in violations),
            f"got {violations!r}",
        )


def test_private_repo_references() -> None:
    section("lint_text: the private notes repo is blocked by URL and by name")

    def reported(text: str, external: bool = True) -> list[str]:
        violations = lo.lint_text(text, "f", check_local_paths=external)
        return [v for v in violations if "local-only path" in v]

    for ref in (
        "https://github.com/nickolashkraus/agent-os/blob/master/x.md",
        "github.com/nickolashkraus/agent-os",
        "nickolashkraus/agent-os#12",
        "git@github.com:nickolashkraus/agent-os.git",
        "[notes](https://github.com/nickolashkraus/agent-os/pull/3)",
        "github.com/NickolasHKraus/Agent-OS/issues",
        "api.github.com/repos/nickolashkraus/agent-os/issues/3",
        "$HOME/nickolashkraus/agent-os/master/notes/x.md",
        "(nickolashkraus/agent-os)",
    ):
        text = f"See {ref} for details.\n"
        check(f"blocked: {ref}", len(reported(text)) == 1, f"got {reported(text)!r}")
        check(f"allowed in-repo: {ref}", reported(text, external=False) == [])
    for ref in (
        "github.com/nickolashkraus/dotfiles",
        "nickolashkraus/agent-os-archive",
        "nickolashkraus/agent-osx#4",
        "nickolashkraus/agent-os_v2",
        "nickolashkraus/agent-os9",
        "xnickolashkraus/agent-os",
        "9nickolashkraus/agent-os",
        "_nickolashkraus/agent-os",
        "other-nickolashkraus/agent-os",
        "github.com/other/agent-os",
        "github.com/nickolashkraus/agent",
        "github.com/nickolashkraus/agent-o",
        "`nickolashkraus/agent-os#12`",
    ):
        text = f"See {ref} for details.\n"
        check(f"not flagged: {ref}", reported(text) == [], f"got {reported(text)!r}")
    for path in (
        "~/nickolashkraus/agent-os/master/notes/x.md",
        "/Users/x/nickolashkraus/agent-os/master/x.md",
    ):
        got = reported(f"See {path} for details.\n")
        check(f"reported once: {path}", len(got) == 1, f"got {got!r}")
    for text in (
        "nickolashkraus/agent-os\n",
        "nickolashkraus/agent-os",
        "Moved to nickolashkraus/agent-os.\n",
    ):
        check(f"blocked at a line edge: {text!r}", len(reported(text)) == 1)
    got = reported("See nickolashkraus/agent-os#1 and NICKOLASHKRAUS/AGENT-OS#2.\n")
    check("two references on one line are two reports", len(got) == 2, f"got {got!r}")
    url = "https://github.com/nickolashkraus/agent-os/blob/master/x.md"
    got = reported(f"See {url} for details.\n")
    check(
        "the report names the path inside the repo",
        "`nickolashkraus/agent-os/blob/master/x.md`" in "".join(got),
        f"got {got!r}",
    )
    for name, tool, tool_input in [
        ("PR body", "Bash", {"command": f"gh pr create --title T --body 'See {url}.'"}),
        ("commit body", "Bash", {"command": f"git commit -m Fix -m 'See {url}.'"}),
        ("Slack message", "mcp__x__y", {"message": f"See {url}."}),
    ]:
        violations = lo.collect_violations(tool, tool_input)
        check(
            f"blocked in a {name}",
            any("local-only path" in v for v in violations),
            f"got {violations!r}",
        )


def test_short_links_and_home_spellings() -> None:
    section("lint_text: short links and other spellings of home are local paths")

    def reported(text: str, external: bool = True) -> list[str]:
        violations = lo.lint_text(text, "f", check_local_paths=external)
        return [v for v in violations if "local-only path" in v]

    for path in (
        "~/w/agent-os/notes/x.md",
        "~/w/agent-os",
        "~/w/mam-5531-debit/app/x.py",
        "$HOME/w/agent-os/notes/x.md",
        "${HOME}/w/agent-os",
        "$HOME/nickolashkraus/dotfiles/master",
        "${HOME}/nickolashkraus",
        "$HOME/.claude/rules/git.md",
        "${HOME}/.claude/rules/git.md",
        "$HOME/dotfiles/README.md",
        "${HOME}/dotfiles",
        "../agent-os/master/notes/x.md",
        "../../agent-os/master",
        "w/agent-os/master/notes/x.md",
        "(~/w/agent-os)",
    ):
        got = reported(f"See {path} for details.\n")
        check(f"blocked once: {path}", len(got) == 1, f"got {got!r}")
        check(f"allowed in-repo: {path}", reported(f"See {path}.\n", False) == [])
    for path in (
        "~/work/x.md",
        "~/www",
        "~/w-old/x.md",
        "~/w_x/x.md",
        "~/w9",
        "$HOMER/w/x",
        "$HOME/work/x",
        "$HOME/bin/x",
        "${HOMES}/dotfiles",
        "x/agent-os/masters/x.md",
        "x/agent-os/master-plan",
        "x/agent-os/master_x",
        "x/agent-os/main/x.md",
        "x/reagent-os/master/x.md",
        "x/re_agent-os/master/x.md",
        "`~/w/agent-os`",
    ):
        got = reported(f"See {path} for details.\n")
        check(f"not flagged: {path}", got == [], f"got {got!r}")
    got = reported("Moved to ~/w.\n")
    check("the link directory itself is blocked", len(got) == 1, f"got {got!r}")
    got = reported("See ~/w/agent-os/notes/x.md for details.\n")
    check(
        "the report names the whole short link",
        "`~/w/agent-os/notes/x.md`" in "".join(got),
        f"got {got!r}",
    )
    got = reported("See ../agent-os/master/notes/x.md for details.\n")
    check(
        "the report names the path from the repo on",
        "`agent-os/master/notes/x.md`" in "".join(got),
        f"got {got!r}",
    )


def test_pr_body_copied_from_linear() -> None:
    section("lint_text: a PR body may not repeat its Linear issue")
    copied = "The checkout monitor pages on every client error, so on-call ignores it."
    twelve = "The retry budget resets every hour, so a burst cannot page twice."
    eleven = "The alert fires only when five requests fail in a row."
    third = "The new threshold counts only server errors, so a client bug stays quiet."
    fourth = "The runbook now names the dashboard that shows which status codes fired."
    hidden = "The frontmatter summary repeats a sentence that the body happens to use."
    sibling = (
        "The sibling issue explains the paging policy that this change keeps as is."
    )
    issue = (
        f"---\nsummary: Short. {hidden}\n---\n\n## Overview\n\n"
        f"{copied} {twelve} {eleven} {third} {fourth}\n"
    )

    def copies(text: str, is_pr_body: bool = True) -> list[str]:
        violations = lo.lint_text(
            text, "f", is_pr_body=is_pr_body, check_local_paths=False
        )
        return [v for v in violations if "copied verbatim" in v]

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for project, name, text in [
            ("a", "BYB-9-retune-the-monitor.md", issue),
            ("a", "BYB-12-paging-policy.md", f"{sibling}\n"),
            ("b", "BYB-9-copy.md", issue),
        ]:
            issues = root / project / "linear" / "issues"
            issues.mkdir(parents=True, exist_ok=True)
            (issues / name).write_text(text)
        saved = lo.LINEAR_ISSUE_ROOT
        lo.LINEAR_ISSUE_ROOT = root
        try:
            for label, body, expected in [
                ("copied sentence", f"BYB-9\n\n{copied}\n", 1),
                ("12-word sentence", f"BYB-9\n\n{twelve}\n", 1),
                ("11-word sentence", f"BYB-9\n\n{eleven}\n", 0),
                ("after an exclamation", f"BYB-9 matters! {copied}\n", 1),
                ("under a heading", f"## Context\n\n{copied}\n\nSee BYB-9.\n", 1),
                ("frontmatter only", f"BYB-9\n\n{hidden}\n", 0),
                ("another issue's file", f"BYB-1\n\n{sibling}\n", 0),
                ("slug named twice", f"BYB-9 and BYB-9 again.\n\n{copied}\n", 1),
            ]:
                got = copies(body)
                check(
                    f"{label}: {expected} report(s)",
                    len(got) == expected,
                    f"got {got!r}",
                )
            check(
                "only PR bodies are compared",
                copies(f"BYB-9\n\n{copied}\n", is_pr_body=False) == [],
            )
            four = copies(f"BYB-9\n\n{copied} {twelve} {third} {fourth}\n")
            check(
                "report shows three sentences and counts the rest",
                len(four) == 1 and "(and 1 more)" in four[0],
                f"got {four!r}",
            )
        finally:
            lo.LINEAR_ISSUE_ROOT = saved


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
    for opt in (
        "--git-dir /srv/repo",
        "--namespace ns",
        "--exec-path /x",
        "--config-env k=ENV",
        "--super-prefix sub/",
        "-p",
    ):
        cmd = f"git {opt} commit -m 'Subject'"
        check(f"commit after `{opt}`", lo.GIT_COMMIT_RE.search(cmd) is not None)

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
        ("Claude state", f"{home}/.claude/projects/p/memory/x.md", True),
        ("second Claude config", f"{home}/.claude-fh/projects/p/x.md", True),
        ("Function-Health repo", f"{home}/Function-Health/svc/README.md", True),
        ("modules repo", f"{home}/Function-Health-Terraform-Modules/m/README.md", True),
        ("infrable-io repo", f"{home}/infrable-io/x/README.md", True),
        ("grind-rip repo", f"{home}/grind-rip/x/README.md", True),
    ]:
        check(
            f"{label}: in_repo={expected}",
            lo.is_in_repo_path(path) is expected,
            f"got {lo.is_in_repo_path(path)!r} for {path}",
        )


def test_extract_fields_scope() -> None:
    section("extract_fields: which tools, files and values are linted")
    curly = "Adds a \u201cgate\u201d finally."

    def flagged(tool: str, tool_input: dict) -> bool:
        return any(
            "left double quote" in v for v in lo.collect_violations(tool, tool_input)
        )

    with tempfile.TemporaryDirectory() as tmp:
        check(
            "Edit on a .py file not linted",
            not flagged("Edit", {"file_path": f"{tmp}/x.py", "new_string": curly}),
        )
        check(
            "Write to a .markdown file linted",
            flagged("Write", {"file_path": f"{tmp}/x.markdown", "content": curly}),
        )
        binary = Path(tmp) / "binary.md"
        binary.write_bytes(b"\xff\xfe not utf-8\n")
        check(
            "undecodable target file still linted",
            flagged("Write", {"file_path": str(binary), "content": curly}),
        )
        note = Path(tmp) / "note.md"
        note.write_text("  - We leverage the cache.\nWe leverage the cache.\n")
        kept = {"file_path": str(note), "content": note.read_text()}
        check(
            "indented existing line keeps its wording",
            lo.collect_violations("Write", kept) == [],
            f"got {lo.collect_violations('Write', kept)!r}",
        )
        mcp = {"file_path": str(note), "text": "We leverage the cache."}
        check(
            "existing lines exempt only Edit and Write",
            any("AI slop" in v for v in lo.collect_violations("mcp__x__y", mcp)),
        )
    check(
        "non-string file_path ignored",
        lo.collect_violations("Edit", {"file_path": None, "new_string": curly}) == [],
    )
    check(
        "non-string command ignored",
        lo.collect_violations("Bash", {"command": ["git", "commit"]}) == [],
    )
    nested = {"pages": [{"properties": {"title": "T"}, "content": curly}]}
    violations = lo.collect_violations("mcp__notion__notion-create-pages", nested)
    check(
        "nested MCP payload linted with its path",
        any(
            v.startswith("pages[0].content") and "left double quote" in v
            for v in violations
        ),
        f"got {violations!r}",
    )
    check("one-character MCP value skipped", not flagged("mcp__x__y", {"v": "\u201c"}))
    check("two-character MCP value linted", flagged("mcp__x__y", {"v": "\u201c."}))


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
        ti = {"file_path": path, "new_string": "a \u201cb\u201d\n"}
        flagged = lo.collect_violations("Edit", ti) != []
        check(
            f"{label}: flagged={expected}",
            flagged is expected,
            f"got {flagged!r} for {path}",
        )


def test_archive_cleanup_false_positives() -> None:
    section("archive cleanup false positives stay quiet; the rules still fire")

    def slop(text: str) -> bool:
        return any(
            "AI slop" in v for v in lo.lint_text(text, "t", check_local_paths=False)
        )

    check("literal bike ride is legal", not slop("- **Bike**: 40 mile ride at Z2.\n"))
    check("land as a noun is legal", not slop("Arable land value rose 7%.\n"))
    check("figurative land still flagged", slop("The fix lands in the next release.\n"))
    check(
        "figurative ride with code span flagged",
        slop("The ID rides along in `meta`.\n"),
    )

    check("blockquote slop is legal", not slop("> We leverage robust tooling.\n"))
    check(
        "double-quoted slop is legal",
        not slop('The epic is "Utilize GitHub secrets".\n'),
    )
    check("plain slop still flagged", slop("We leverage the cache.\n"))

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "note.md"
        path.write_text(
            "We leverage the cache.\n- **Name (9:58 AM)**: lowercase reply\n"
        )
        kept = {"file_path": str(path), "content": path.read_text()}
        check(
            "existing lines keep their wording",
            lo.collect_violations("Write", kept) == [],
        )
        added = {
            "file_path": str(path),
            "content": path.read_text() + "We also leverage it.\n",
        }
        check(
            "new slop line still flagged",
            any("AI slop" in v for v in lo.collect_violations("Write", added)),
        )
        path.write_text("Old line \u201cwith\u201d a quote.\n")
        curly = {"file_path": str(path), "content": path.read_text()}
        check(
            "existing smart quote still flagged",
            any(
                "left double quote" in v for v in lo.collect_violations("Write", curly)
            ),
        )
        edit = {
            "file_path": str(path),
            "new_string": "Old line, no quote.\n- **Name**: lowercase\n",
        }
        check(
            "edit with a new lowercase label still flagged",
            any("colon" in v for v in lo.collect_violations("Edit", edit)),
        )

    def colon(text: str) -> bool:
        return any(
            "colon" in v for v in lo.lint_text(text, "t", check_local_paths=False)
        )

    check(
        "URL after a bold label is legal",
        not colon("- **Docs**: https://example.com/x\n"),
    )
    check(
        "URL after a link label is legal",
        not colon("[Docs](https://x): https://example.com\n"),
    )
    check(
        "URL after a plain label is legal", not colon("- Docs: https://example.com/x\n")
    )
    check(
        "lowercase word after a plain label still flagged",
        colon("- Docs: example text\n"),
    )
    check(
        "lowercase word after a label still flagged",
        colon("- **Docs**: example text\n"),
    )

    loop = (
        "while IFS='|' read -r old new; do git mv \"$old\" \"$new\"; done <<'EOF'\n"
        "A very long data line that is not a commit subject at all, by any measure|x\n"
        "EOF\n"
        'git commit -m "Rename the notes"\n'
    )
    fields = lo.extract_bash_content(loop)
    check(
        "data heredoc is not linted as a commit",
        all(not f[0].startswith("heredoc") for f in fields),
    )
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
    check(
        "word inside a wrapped span is legal",
        british(inside) == [],
        f"{british(inside)!r}",
    )
    after = "See `git commit\n-F file` and the colour of `behaviour` here.\n"
    found = [
        v for v in lo.lint_text(after, "t", check_local_paths=False) if "British" in v
    ]
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


CURLY = "\u201c"


def bash_violations(cmd: str) -> list[str]:
    return lo.collect_violations("Bash", {"command": cmd})


def curly_flagged(cmd: str) -> bool:
    return any("left double quote" in v for v in bash_violations(cmd))


def test_short_combined_and_owned_flags() -> None:
    section("extract_bash_content: short, combined and owned flags are read")
    with tempfile.TemporaryDirectory() as tmp:
        curly_file = Path(tmp) / "my body.md"
        curly_file.write_text(f"Adds the gate {CURLY} finally.\n")
        clean = Path(tmp) / "clean.md"
        clean.write_text("Adds the gate.\n")
        for name, cmd in (
            ("git commit -am", f'git commit -am "Fix the lock {CURLY} again"'),
            ("git commit -qm", f'git commit -qm "Fix the lock {CURLY} again"'),
            (
                "gh pr create -b",
                f'gh pr create -t T -b "Adds the gate {CURLY} finally."',
            ),
            (
                "gh issue create -t",
                f'gh issue create -t "Gate {CURLY} two" -b "Adds it."',
            ),
            ("gh pr create -F", f"gh pr create --title T -F '{curly_file}'"),
            ("gh issue comment -F", f"gh issue comment 3 -F '{curly_file}'"),
            ("git commit -F, quoted path", f"git commit -F '{curly_file}'"),
            ("git commit -aF", f"git commit -aF '{curly_file}'"),
            ("git commit --file", f"git commit --file '{curly_file}'"),
            (
                "--body-file, quoted path",
                f'gh pr create --title T --body-file "{curly_file}"',
            ),
            ("gh pr comment -b", f'gh pr comment 1 -b "Fixed {CURLY} it."'),
            ("gh pr edit -b", f'gh pr edit 1 -b "Adds {CURLY} it."'),
            ("gh pr merge -t", f'gh pr merge 1 -t "Merge {CURLY} it"'),
            ("gh pr review -b", f'gh pr review 1 -b "Looks {CURLY} good."'),
            (
                "-b after a single-quoted `;`",
                f"gh pr create --title 'a; b' -b \"Adds {CURLY} it.\"",
            ),
            (
                "-b after an escaped quote",
                f'gh pr create --title "a \\" ; b" -b "Adds {CURLY} it."',
            ),
            (
                "gh -R before pr",
                f'gh -R o/r pr create --title T --body "Adds {CURLY} it."',
            ),
            (
                "gh --repo= before pr",
                f'gh --repo=o/r pr create --body "Adds {CURLY} it."',
            ),
            (
                "gh pr -R before comment",
                f'gh pr -R o/r comment 12 --body "Fixed {CURLY} it."',
            ),
            (
                "-b after a continuation",
                f'gh pr create --title T \\\n  -b "Adds {CURLY} it."',
            ),
            (
                "-b after a quoted `;`",
                f'gh pr create --title "a; b" -b "Adds {CURLY} it."',
            ),
            ("-b after 2>&1", f'gh pr create --title T 2>&1 -b "Adds {CURLY} it."'),
            ("-m $(cat file)", f"git commit -m \"$(cat '{curly_file}')\""),
            ("--body $(< file)", f"gh pr comment 1 --body \"$(< '{curly_file}')\""),
            (
                "unowned -F in a commit command",
                f"git commit -q; tool -F '{curly_file}'",
            ),
        ):
            check(
                f"{name}: smart quote flagged",
                curly_flagged(cmd),
                f"got {bash_violations(cmd)!r}",
            )
        for name, cmd in (
            ("git commit -Sm (a signing key)", f'git commit -Sm "Fix {CURLY} it"'),
            ("git commit -t (a template)", f'git commit -t "t{CURLY}.txt" -m "Fix"'),
            ("gh pr checkout -b (a branch)", f'gh pr checkout 12 -b "fix{CURLY}it"'),
            ("gh api -t (a template)", f"gh api repos/o/r -t '{{{{.x}}}} {CURLY}'"),
            ("-t of a later command", f'gh pr create --body B && tool -t "x {CURLY}"'),
            ("-b of a piped command", f'gh pr create --body B | tool -b "x {CURLY}"'),
            (
                "-b of a background command",
                f'gh pr create --body B & tool -b "x {CURLY}"',
            ),
            ("-b after a `;`", f'gh pr create --body B; tool -b "x {CURLY}"'),
            ("-b on the next line", f'gh pr create --body B\ntool -b "x {CURLY}"'),
            ("unowned -F, no commit", f"gh pr view 1; tool -F '{curly_file}'"),
            ("-am outside a commit", f'gh pr view 1 && tool -am "x {CURLY}"'),
            (
                "gh api -F (a field)",
                f"git commit -m Fix && gh api graphql -F '{curly_file}'",
            ),
            ("gh pr view -F", f"git commit -m Fix && gh pr view 1 -F '{curly_file}'"),
            ("-F - (stdin)", "git commit -F - && echo"),
        ):
            check(
                f"{name}: not read",
                not curly_flagged(cmd),
                f"got {bash_violations(cmd)!r}",
            )

        fields = lo.extract_bash_content('git commit -am "Fix the lock"')
        check(
            "-am is the whole commit message",
            fields == [("arg -am", "Fix the lock", True, False, True)],
            f"got {fields!r}",
        )
        both = lo.extract_bash_content(
            f"git commit -F {clean} && gh pr create --title T -F '{curly_file}'"
        )
        check(
            "-F is the commit message under git, the PR body under gh",
            [(f[0], *f[2:]) for f in both if f[0].startswith("arg -F")]
            == [
                (f"arg -F {clean}", True, False, True),
                (f"arg -F {curly_file}", False, True, False),
            ],
            f"got {both!r}",
        )
        fields = lo.extract_bash_content(f"gh issue comment 3 -F '{clean}'")
        check(
            "-F under gh issue comment is a body, not a PR body",
            [f[2:] for f in fields] == [(False, False, False)],
            f"got {fields!r}",
        )
        fields = lo.extract_bash_content(f"git commit -m \"$(cat '{curly_file}')\"")
        check(
            "$(cat file) is the file's text without the final newline",
            fields
            == [("arg -m", f"Adds the gate {CURLY} finally.", True, False, True)],
            f"got {fields!r}",
        )
        prefixed = f"See $(cat '{curly_file}')"
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
        (
            "gh pr comment 1 --body 'Fixed.'",
            ("arg --body", "Fixed.", False, False, False),
        ),
        ("gh pr create --title 'Gate'", ("arg --title", "Gate", False, False, False)),
        (
            "git commit -m 'Fix' --body 'Note'",
            ("arg --body", "Note", False, False, False),
        ),
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
    check(
        "gh -R in the command keeps the heredoc length checks off",
        found == [],
        f"got {found!r}",
    )


def test_code_and_data_heredocs() -> None:
    section("extract_bash_content: code and data heredocs are not messages")
    code = (
        "import json, sys\n"
        f"files = json.load(sys.stdin)  # every changed path {CURLY} sorted by name\n"
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
    check("uv without run is not a wrapper", curly_flagged(kept), "not flagged")

    script = f"echo 'step {CURLY} one'\ngit commit -m 'Add the report'\n"
    for name, owner in (
        ("bash", "bash"),
        ("sh -s with an argument", "sh -s x"),
        ("bash with a redirect", "bash > out.log"),
    ):
        cmd = f"{owner} <<'EOF'\n{script}EOF"
        check(
            f"{name}: script not linted",
            bash_violations(cmd) == [],
            f"got {bash_violations(cmd)!r}",
        )
        fields = lo.extract_bash_content(cmd)
        check(
            f"{name}: the commit in the script is read",
            fields == [("arg -m", "Add the report", True, False, True)],
            f"got {fields!r}",
        )
    bad = f"bash <<'EOF'\ngit commit -m 'Fix the lock {CURLY} again'\nEOF"
    check(
        "bash: a message in the script is still linted",
        curly_flagged(bad),
        "not flagged",
    )
    data = f"bash run.sh <<'EOF'\nstep {CURLY} one\nEOF\ngit commit -m 'Run it'"
    check(
        "bash run.sh: the script's input stays a payload",
        curly_flagged(data),
        "not flagged",
    )

    query = (
        '{"query": "query { repository(owner: \\"o\\", name: \\"r\\") { id } }",\n'
        ' "variables": {"first": 100, "after": null, "states": ["OPEN"]}}\n'
    )
    gql = f"gh api graphql --input - <<'EOF'\n{query}EOF"
    check(
        "gh api --input - JSON: no hard wrap",
        bash_violations(gql) == [],
        f"got {bash_violations(gql)!r}",
    )
    comment = (
        "gh api repos/o/r/issues/1/comments --input - <<'EOF'\n"
        f'{{"body": "Fixed {CURLY} thanks."}}\nEOF'
    )
    found = bash_violations(comment)
    check(
        "gh api --input - JSON: the body is still linted",
        any("left double quote" in v and "body" in v for v in found),
        f"got {found!r}",
    )
    one_char = f"gh api graphql --input - <<'EOF'\n[\"{CURLY}\"]\nEOF"
    check(
        "gh api --input - JSON: a one-character string is linted",
        curly_flagged(one_char),
        "not flagged",
    )
    numbers = (
        "gh api graphql --input - <<'EOF'\n"
        '{"first": 100, "last": 100, "after": null, "before": null, "count": 12345,\n'
        ' "depth": 1}\nEOF'
    )
    check(
        "gh api --input - JSON without strings: no hard wrap",
        bash_violations(numbers) == [],
        f"got {bash_violations(numbers)!r}",
    )
    for name, cmd in (
        ("not JSON", f"gh api graphql --input - <<'EOF'\n[{query}EOF"),
        (
            "another program's --input -",
            f"gh pr view 1; curl --input - <<'EOF'\n{query}EOF",
        ),
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

    notes = (
        "- Rebased the branch onto main and reran the full suite after the conflict\n"
    )
    tee = f"tee -a notes/x.md >/dev/null <<'EOF'\n{notes}EOF\ngit commit -m 'Update notes'"
    check(
        "tee into a file: not the message",
        heredocs(tee) == [],
        f"got {heredocs(tee)!r}",
    )
    bare = f"tee -a notes/x.md <<'EOF'\n{notes}EOF\ngit commit -m 'Update notes'"
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
        ("no file", f"tee {msg}git commit -m x"),
    ):
        check(
            f"tee, {name}: stays a payload",
            heredocs(cmd) == ["Add the lint workflow"],
            f"got {heredocs(cmd)!r}",
        )


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
    check(
        "a clean message passes",
        bash_violations(clean) == [],
        f"got {bash_violations(clean)!r}",
    )
    fields = lo.extract_bash_content(clean)
    check(
        "one field, joined the way git joins it",
        fields == [("arg -m", "Short subject\n\nBody paragraph.", True, False, True)],
        f"got {fields!r}",
    )
    two = lo.extract_bash_content(
        'git commit -m "First" && git commit --amend -m "Second"'
    )
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
        cmd = (
            f"gh pr create --title T --body-file {quote}/Users/nobody/w/pr-1.md{quote}"
        )
        found = bash_violations(cmd)
        check(
            f"quote {quote or 'none'}: path not linted", found == [], f"got {found!r}"
        )
    found = bash_violations('gh pr create --title T --body-file "$f"')
    check(
        "a quoted variable is still blocked as a bypass",
        any("bare shell-variable" in v for v in found),
        f"got {found!r}",
    )
    found = bash_violations("gh pr create --title T --body-file $f")
    check("an unquoted variable passes as before", found == [], f"got {found!r}")


def test_gh_release_text() -> None:
    section("extract_bash_content: gh release notes and titles are read")
    with tempfile.TemporaryDirectory() as tmp:
        notes = Path(tmp) / "notes.txt"
        notes.write_text(f"Adds the gate {CURLY} finally.\n")
        for name, cmd in (
            ("create --notes", f'gh release create v1.2.3 --notes "Adds {CURLY} it."'),
            ("create --notes=", f'gh release create v1.2.3 --notes="Adds {CURLY} it."'),
            ("create -n", f'gh release create v1.2.3 -n "Adds {CURLY} it."'),
            ("create --title", f'gh release create v1 --title "v1 {CURLY}" -n N'),
            ("create -t", f'gh release create v1 -t "v1 {CURLY}" -n N'),
            ("edit --notes", f"gh release edit v1 --notes 'Adds {CURLY} it.'"),
            ("edit -n", f'gh release edit v1 -n "Adds {CURLY} it."'),
            ("edit -t", f'gh release edit v1 -t "v1 {CURLY}"'),
            ("new (alias of create) -n", f'gh release new v1 -n "Adds {CURLY} it."'),
            ("create -F", f"gh release create v1 -F '{notes}'"),
            ("edit -F", f"gh release edit v1 -F {notes}"),
            ("create --notes-file", f"gh release create v1 --notes-file {notes}"),
            ("edit --notes-file=", f"gh release edit v1 --notes-file='{notes}'"),
            (
                "create -F - with a heredoc",
                f"gh release create v1 -F - <<'EOF'\nAdds {CURLY} it.\nEOF",
            ),
            (
                "edit --notes-file - with a heredoc",
                f"gh release edit v1 --notes-file - <<'EOF'\nAdds {CURLY} it.\nEOF",
            ),
            (
                "a .txt notes file written by the same command",
                (
                    f"cat > notes.txt <<'EOF'\nAdds {CURLY} it.\nEOF\n"
                    "gh release create v1 --notes-file notes.txt"
                ),
            ),
            ("gh -R before release", f'gh -R o/r release create v1 -n "{CURLY}x"'),
            ("gh release -R before edit", f'gh release -R o/r edit v1 -n "{CURLY}x"'),
        ):
            check(
                f"gh release {name}: smart quote flagged",
                curly_flagged(cmd),
                f"got {bash_violations(cmd)!r}",
            )
        clean = (
            "gh release create v1.2.3 --title 'v1.2.3' "
            "--notes 'Adds the upgrade gate.' --target main"
        )
        check(
            "clean release notes pass",
            bash_violations(clean) == [],
            f"got {bash_violations(clean)!r}",
        )
        for name, cmd in (
            ("view -t (a template)", f"gh release view v1 -t '{{{{.body}}}} {CURLY}'"),
            ("list -t (a template)", f"gh release list -t '{{{{.tagName}}}} {CURLY}'"),
            ("verify -t (a template)", f"gh release verify v1 -t '{CURLY}x'"),
            ("view -q", f"gh release view v1 --json body -q '.body {CURLY}'"),
            ("download -p", f"gh release download v1 -p '*{CURLY}.tgz'"),
            ("download -O", f"gh release download v1 -O 'out{CURLY}.tgz'"),
            ("download -D", f"gh release download v1 -D 'dir{CURLY}'"),
            ("view -F", f"git commit -m Fix && gh release view v1 -F '{notes}'"),
            ("download -n", f"gh release download v1 -n '{CURLY}x'"),
            (
                "an asset display label",
                f"gh release create v1 -n N 'dist/a.zip#Label {CURLY}'",
            ),
            (
                "--notes-from-tag is not --notes",
                f"gh release create v1 --notes-from-tag 'a{CURLY}.zip'",
            ),
            ("-n of a later command", f'gh release create v1 -n N; tool -n "{CURLY}x"'),
            (
                "--notes of a later command",
                f'gh release create v1 -n N && tool --notes "{CURLY}x"',
            ),
            ("git commit -n (no verify)", f'git commit -m Fix -n "{CURLY}x"'),
        ):
            check(
                f"gh release {name}: not read",
                not curly_flagged(cmd),
                f"got {bash_violations(cmd)!r}",
            )
        fields = lo.extract_bash_content(f"gh release edit v1 --notes-file {notes}")
        check(
            "--notes-file is labeled with its own flag",
            [f[0] for f in fields] == [f"arg --notes-file {notes}"],
            f"got {fields!r}",
        )
    for cmd, expected in (
        (
            "gh release create v1 -n 'Adds it.'",
            [("arg -n", "Adds it.", False, False, False)],
        ),
        (
            "gh release edit v1 --notes 'Adds it.' -t 'v1'",
            [
                ("arg --notes", "Adds it.", False, False, False),
                ("arg -t", "v1", False, False, False),
            ],
        ),
        ("gh release view v1 -t '{{.body}}'", []),
        ("gh release list -L 5 -t '{{.tagName}}'", []),
        ("gh release download v1 -p '*.tgz' -O out.tgz", []),
    ):
        fields = lo.extract_bash_content(cmd)
        check(f"`{cmd[:40]}` fields", fields == expected, f"got {fields!r}")
    found = bash_violations("gh release create v1 --notes 'Closes #12'")
    check(
        "release notes are not a PR body",
        not any("Closes:" in v for v in found),
        f"got {found!r}",
    )
    subject = "S" * 60
    found = bash_violations(
        f"git commit -F - <<'EOF'\n{subject}\nEOF\ngh release create v1 --notes N"
    )
    check(
        "gh release in the command keeps the heredoc length checks off",
        found == [],
        f"got {found!r}",
    )
    found = bash_violations('gh release create v1 --notes-file "$f"')
    check(
        "a quoted variable --notes-file is blocked as a bypass",
        any(v.startswith("arg --notes-file:") for v in found),
        f"got {found!r}",
    )


def hook_matcher(script: str) -> str:
    """The PreToolUse matcher of the settings.json entry that runs `script`."""
    settings = json.loads(SETTINGS_PATH.read_text())
    for entry in settings["hooks"]["PreToolUse"]:
        if any(h.get("command", "").endswith(script) for h in entry["hooks"]):
            return entry["matcher"]
    raise AssertionError(f"no PreToolUse entry runs {script}")


OUTBOUND_MCP_TOOLS = (
    "mcp__claude_ai_Gmail__create_draft",
    "mcp__claude_ai_Gmail__send_message",
    "mcp__claude_ai_Gmail__reply",
    "mcp__claude_ai_Gmail__forward",
    "mcp__claude_ai_Gmail__update_draft",
    "mcp__notion__notion-update-comment",
    "mcp__notion__notion-create-meeting-note",
)
READ_ONLY_NEIGHBORS = (
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
)
FILE_REFERENCE = "sha256:" + "0" * 64 + ":/Users/nobody/Downloads/menu.pdf"


def test_outbound_mcp_surfaces() -> None:
    section("settings.json matcher and payloads: email and Notion comment tools")
    # Claude Code tests a matcher that is not a plain list of names as an
    # unanchored JavaScript regex, which `re.search` mirrors.
    matcher = hook_matcher("lint-outbound.py")
    for tool in OUTBOUND_MCP_TOOLS:
        check(f"{tool} gated", re.search(matcher, tool) is not None)
    for tool in READ_ONLY_NEIGHBORS:
        check(f"{tool} not gated", re.search(matcher, tool) is None)

    attachment = {"content": FILE_REFERENCE, "filename": "menu.pdf"}
    for tool, tool_input, field in (
        (
            "mcp__claude_ai_Gmail__send_message",
            {"to": ["a@example.com"], "subject": "Lunch", "body": "Noon works."},
            "body",
        ),
        (
            "mcp__claude_ai_Gmail__send_message",
            {"to": ["a@example.com"], "subject": "Lunch at noon", "body": "Yes."},
            "subject",
        ),
        (
            "mcp__claude_ai_Gmail__reply",
            {"messageId": "18c2f0a1b2c3d4e5", "htmlBody": "<p>Noon works.</p>"},
            "htmlBody",
        ),
        (
            "mcp__claude_ai_Gmail__forward",
            {"messageId": "18c2f0a1b2c3d4e5", "forwardText": "See below."},
            "forwardText",
        ),
        (
            "mcp__claude_ai_Gmail__update_draft",
            {"draftId": "r-123", "body": "Noon works."},
            "body",
        ),
        (
            "mcp__notion__notion-update-comment",
            {"comment_id": "1f2e3d4c", "markdown": "Fixed in the new draft."},
            "markdown",
        ),
        (
            "mcp__notion__notion-create-meeting-note",
            {"title": "Weekly sync", "content": "## Notes\n\nShipped the gate."},
            "content",
        ),
    ):
        clean = {**tool_input, "attachments": [attachment]}
        found = lo.collect_violations(tool, clean)
        check(f"{tool.split('__')[-1]}: clean payload passes", found == [], f"{found}")
        curly = {**tool_input, field: f"{CURLY}{tool_input[field]}"}
        found = lo.collect_violations(tool, curly)
        check(
            f"{tool.split('__')[-1]} {field}: smart quote flagged",
            any(v.startswith(f"{field} line 1: left double quote") for v in found),
            f"got {found!r}",
        )
    bare = lo.collect_violations("mcp__x__y", {"content": FILE_REFERENCE})
    check(
        "a file reference outside `attachments` is still linted",
        any("local-only path" in v for v in bare),
        f"got {bare!r}",
    )


EMAIL_BODIES = (
    ("mcp__claude_ai_Gmail__create_draft", {"to": ["a@example.com"]}, "body"),
    ("mcp__claude_ai_Gmail__send_message", {"to": ["a@example.com"]}, "body"),
    ("mcp__claude_ai_Gmail__reply", {"messageId": "18c2f0a1b2c3d4e5"}, "body"),
    ("mcp__claude_ai_Gmail__forward", {"messageId": "18c2f0a1"}, "forwardText"),
    ("mcp__claude_ai_Gmail__update_draft", {"draftId": "r-123"}, "body"),
)
QUOTED_HISTORY = (
    f"> Is noon {CURLY}ok{CURLY}? The [notes][] are attached.\n"
    f">> Earlier {CURLY}draft{CURLY}.\n"
    f"  > Indented {CURLY}quote{CURLY}.\n"
    f"> > Spaced {CURLY}nesting{CURLY}."
)


def test_email_quoted_history() -> None:
    section("collect_violations: quoted history in an email body")
    for tool, ids, field in EMAIL_BODIES:
        name = tool.split("__")[-1]

        def lint(text: str, tool: str = tool, ids: dict = ids, field: str = field):
            return lo.collect_violations(tool, {**ids, field: text})

        found = lint(f"Noon works.\n\nOn Monday someone wrote:\n{QUOTED_HISTORY}")
        check(f"{name}: quoted lines are not linted", found == [], f"got {found!r}")
        found = lint(f"Noon {CURLY}works{CURLY}.\n\n{QUOTED_HISTORY}")
        check(
            f"{name}: a smart quote in its own line blocks",
            found == [f"{field} line 1: left double quote (use straight quote)"],
            f"got {found!r}",
        )
        found = lint(QUOTED_HISTORY)
        check(f"{name}: only quoted lines passes", found == [], f"got {found!r}")
        found = lint("Noon works.\n\n> The notes are in /Users/nobody/notes.md")
        check(
            f"{name}: a local path in a quoted line still blocks",
            [v.split(":")[0] for v in found] == [f"{field} line 3"]
            and "local-only path" in found[0],
            f"got {found!r}",
        )
        found = lint("Noon works.\n\n> Generated with Claude Code")
        check(
            f"{name}: the tool footer in a quoted line still blocks",
            any("Generated with Claude Code" in v for v in found),
            f"got {found!r}",
        )
    line = f"> Is noon {CURLY}ok{CURLY}?"
    for tool, field, text in (
        ("mcp__claude_ai_Gmail__reply", "htmlBody", f"<p>Yes.</p>\n{line}"),
        ("mcp__claude_ai_Gmail__send_message", "subject", line),
        ("mcp__claude_ai_Slack__slack_send_message", "message", line),
        ("mcp__notion__notion-update-comment", "markdown", line),
        ("mcp__notion__notion-create-meeting-note", "content", line),
        ("mcp__linear__save_comment", "body", line),
    ):
        found = lo.collect_violations(tool, {field: text})
        check(
            f"{tool.split('__')[-1]} {field}: a quoted line is still linted",
            any("left double quote" in v for v in found),
            f"got {found!r}",
        )
    check(
        "a quoted line in a Bash --body is still linted",
        curly_flagged(f'gh pr comment 1 --body "{line}"'),
    )


def test_mcp_identifier_fields_skipped() -> None:
    section("extract_fields: addresses, identifiers and metadata are not linted")
    value = "colour-team@example.com"
    for name in (
        "bcc",
        "cc",
        "comment_id",
        "draftId",
        "instructions_version",
        "messageId",
        "replyThreadId",
        "replyToMessageId",
        "skill",
        "to",
    ):
        for shape in (value, [value]):
            found = lo.collect_violations(
                "mcp__claude_ai_Gmail__send_message", {name: shape}
            )
            check(
                f"{name} ({type(shape).__name__}) not linted",
                found == [],
                f"got {found!r}",
            )
    for name in ("to", "cc", "bcc", "skill", "comment_id", "draftId"):
        for tool, shape in (
            ("mcp__notion__notion-update-page", {"properties": {name: value}}),
            (
                "mcp__notion__notion-create-pages",
                {"pages": [{"properties": {name: value}}]},
            ),
        ):
            found = lo.collect_violations(tool, shape)
            check(
                f"a page property named {name} is linted ({tool.rsplit('-', 1)[-1]})",
                any("British spelling" in v for v in found),
                f"got {found!r}",
            )
    found = lo.collect_violations("mcp__claude_ai_Gmail__send_message", {"body": value})
    check(
        "the same value in a text field is linted",
        any("British spelling" in v for v in found),
        f"got {found!r}",
    )
    for subtree in (
        {"parent": {"type": "page", "url": f"https://example.com/{value}"}},
        {
            "calendarEvent": {
                "calendar": {"accountId": value, "calendarId": value},
                "eventId": value,
            }
        },
    ):
        found = lo.collect_violations(
            "mcp__notion__notion-create-meeting-note", subtree
        )
        check(
            f"{next(iter(subtree))} subtree not linted", found == [], f"got {found!r}"
        )


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
    test_punctuation_outside_code,
    test_dashes_pass_on_every_surface,
    test_british_spellings,
    test_ai_slop_catalog,
    test_autofix_resolves_detected,
    test_try_autofix_input_scope,
    test_autofix_identifier_and_heredoc,
    test_main_autofix_end_to_end,
    test_main_fails_open,
    test_tool_attribution_footer,
    test_commit_trailer_and_autoclose,
    test_local_paths_in_external_content,
    test_private_repo_references,
    test_short_links_and_home_spellings,
    test_pr_body_copied_from_linear,
    test_git_global_flags_before_commit,
    test_in_repo_path_prefixes,
    test_extract_fields_scope,
    test_linear_mirror_paths_skip_lint,
    test_archive_cleanup_false_positives,
    test_wrapped_code_span,
    test_short_combined_and_owned_flags,
    test_code_and_data_heredocs,
    test_multiple_m_flags,
    test_body_file_path_is_not_the_body,
    test_gh_release_text,
    test_outbound_mcp_surfaces,
    test_email_quoted_history,
    test_mcp_identifier_fields_skipped,
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
