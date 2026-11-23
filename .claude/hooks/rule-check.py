#!/usr/bin/env python3
"""
PreToolUse hook: deep semantic rule check on outbound prose payloads via a
fresh Opus invocation. Reads ~/.claude/rules/*.md and ~/.claude/CLAUDE.md,
asks Opus whether the payload complies with every rule, and exit-2-blocks
the tool call on any violation.

This is the heavier complement to lint-outbound.py: cheap regexes catch the
deterministic typography and leak patterns; this catches the semantic stuff
(paraphrased Linear titles, inline-summarized internal context, drifted TODO
formats, missed conventions).

Gated tools: prose surfaces only.

- Bash: `git commit`, `gh pr create|edit`, `gh pr comment`, `gh issue
  create|edit|comment`, `gh api` with `body`/`title` fields.
- MCP: `mcp__linear__save_*`, `mcp__notion__notion-(create-pages|update-page
  |create-comment)`, `mcp__claude_ai_Slack__slack_(send_message|
  send_message_draft|schedule_message|create_canvas|update_canvas)`,
  `mcp__claude_ai_Gmail__create_draft`.

Source-code Edit/Write is intentionally NOT in this hook; lint-outbound.py's
regex layer handles the deterministic source-code rules at zero latency.

Override: include `<!-- rule-check: skip reason="..." -->` (HTML comment) or
`# rule-check: skip reason="..."` (line comment) anywhere in the payload to
bypass. Logged to ~/.claude/rule-check.log for audit.

Reliability posture:

- Timeouts and subprocess failures fail OPEN (allow, log). A broken or slow
  linter must never block a correct payload.
- Verdicts are cached by (rules, surface, payload) hash in
  ~/.claude/rule-check-cache.json so identical payloads always get identical
  verdicts despite the LLM being non-deterministic.
- Findings that hinge on character arithmetic (table padding, subject length,
  wrap width) are mechanically discarded; lint-outbound.py enforces those
  deterministically on the source text.

Subprocess invocation uses `claude --print --allowed-tools ""` so the
subprocess cannot make tool calls, which means PreToolUse hooks never fire
inside it: no recursion risk. The rules + payload travel inline as the prompt;
the model returns a schema-validated JSON verdict.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

RULES_DIR = Path.home() / ".claude" / "rules"
CLAUDE_MD = Path.home() / ".claude" / "CLAUDE.md"
LOG_FILE = Path.home() / ".claude" / "rule-check.log"
CACHE_FILE = Path.home() / ".claude" / "rule-check-cache.json"

SUBPROCESS_TIMEOUT_SEC = 80
MAX_PAYLOAD_CHARS = 40_000
CACHE_TTL_SEC = 7 * 24 * 3600
CACHE_MAX_ENTRIES = 500

SKIP_RE = re.compile(
    r"(?:<!--|#|//)\s*rule-check:\s*skip(?:\s+reason=\"([^\"]+)\")?",
    re.IGNORECASE,
)

GATED_MCP_RE = re.compile(
    r"^(?:"
    r"mcp__linear__save_.*"
    r"|mcp__notion__notion-(?:create-pages|update-page|create-comment)"
    r"|mcp__claude_ai_Slack__slack_(?:send_message|send_message_draft"
    r"|schedule_message|create_canvas|update_canvas)"
    r"|mcp__claude_ai_Gmail__create_draft"
    r")$"
)

HEREDOC_RE = re.compile(
    r"<<[-]?\s*['\"]?(\w+)['\"]?\s*\n(.*?)\n\s*\1\b",
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
GH_API_FIELD_RE = re.compile(
    r"(?:^|\s)(?:-[fF]|--(?:raw-)?field)\s+(body|title)="
    r"(\"((?:[^\"\\]|\\.)*)\"|'((?:[^'\\]|\\.)*)')",
)
# `-F` reads the commit message under `git commit` and the body under gh's
# text subcommands, but is a field under `gh api` (handled separately by
# GH_API_FIELD_RE), so each `-F` is read by the command that owns it.
PATH_TOKEN = r"(\"[^\"]*\"|'[^']*'|[^\s;|&<>()]+)"
BODY_FILE_RE = re.compile(rf"(?:^|\s)--body-file[=\s]+{PATH_TOKEN}")
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


GH_API_AT_FILE_RE = re.compile(
    r"(?:^|\s)(?:-[fF]|--(?:raw-)?field)\s+(body|title)=@(\S+)"
)

CMD_SUBST_PREFIX_RE = re.compile(r"^\$[\(\{]")

# Git accepts global options between `git` and the subcommand, so
# `git -C <dir> commit` and `git -c k=v commit` are commits too. Every token
# in between must look like a flag or a known flag's value, and `-c`/`-C`
# always take a value, which keeps `git -C <dir> log --grep commit` and
# `git -c commit.gpgsign=false tag` out. `(?![-\w])` keeps `git commit-graph`
# from reading as a commit. Same pattern as lint-outbound.py.
GIT_GLOBAL_OPT = (
    r"-[cC](?:=|\s+)\S+"
    r"|--(?:git-dir|work-tree|namespace|exec-path|config-env|super-prefix)"
    r"(?:=|\s+)\S+"
    r"|--[\w-]+(?:=\S+)?"
    r"|-(?![cC]\s)[A-Za-z]+"
)
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


# Heredocs that are stdin for a code interpreter (`python3 - <<'PY'`)
# carry source code, not outbound prose, and must not be rule-checked.
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
# are found by reading it as a command of its own, not by checking it as prose.
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


def _is_real_prose_value(value: str | None) -> bool:
    """Filter out flag-value extractions that are shell wrappers, not real
    prose. Catches the residue left after HEREDOC_RE substitution wipes a
    `$(cat <<'EOF' ... EOF)` heredoc invocation, which otherwise produces a
    phantom payload like `$(cat \\n)` that wastes an Opus call."""
    if not value or len(value) <= 4:
        return False
    return not CMD_SUBST_PREFIX_RE.match(value.lstrip())


VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "fail"]},
        "violations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rule_file": {"type": "string"},
                    "rule_quote": {"type": "string"},
                    "payload_excerpt": {"type": "string"},
                    "suggested_fix": {"type": "string"},
                },
                "required": [
                    "rule_file",
                    "rule_quote",
                    "payload_excerpt",
                    "suggested_fix",
                ],
            },
        },
    },
    "required": ["verdict", "violations"],
}


def log(msg: str) -> None:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except OSError:
        pass


def extract_bash_payloads(command: str) -> list[tuple[str, str]]:
    """Return (surface_label, text) tuples extracted from a Bash command."""
    is_commit = bool(GIT_COMMIT_RE.search(command))
    if not is_commit and not GH_COMMAND_RE.search(command):
        return []

    is_pr = bool(re.search(rf"{GH_PREFIX}pr\b", command))
    is_issue = bool(re.search(rf"{GH_PREFIX}issue\b", command))
    gh_surface = "GitHub PR" if is_pr else "GitHub issue" if is_issue else "GitHub API"
    surface = "git commit message" if is_commit else gh_surface

    out: list[tuple[str, str]] = []

    for m in HEREDOC_RE.finditer(command):
        if heredoc_feeds_shell(command, m.start()):
            out.extend(extract_bash_payloads(m.group(2)))
            continue
        if heredoc_feeds_interpreter(command, m.start()):
            continue
        if heredoc_feeds_data_consumer(command, m.start()):
            continue
        if heredoc_writes_other_file(command, m.start()):
            continue
        out.append((f"{surface} heredoc<{m.group(1)}>", m.group(2)))

    redacted = HEREDOC_RE.sub("", command)
    owners = command_owners(redacted)
    commit_msg_seen = 0
    for m in FLAG_VALUE_RE.finditer(redacted):
        flag = m.group(1)
        kind = flag_kind(flag, flag_owner(owners, m.start())[1])
        value = resolve_value(m.group(3) if m.group(3) is not None else m.group(4))
        if kind and _is_real_prose_value(value):
            # In a compound command (`git commit ... && gh pr create ...`),
            # label each flag by the command that owns it: -m/--message
            # are commit flags; --body/--title belong to gh. A PR title
            # must never be evaluated under the commit-subject lens.
            if kind == "message":
                if is_commit:
                    # `git commit -m subject -m body`: the first message is the
                    # subject, each subsequent -m is a body paragraph. Body
                    # prose is not governed by the subject's imperative-mood or
                    # no-terminal-period rules, so label it distinctly.
                    flag_surface = (
                        "git commit message"
                        if commit_msg_seen == 0
                        else "git commit message body"
                    )
                    commit_msg_seen += 1
                else:
                    flag_surface = surface
            elif is_pr or is_issue:
                flag_surface = gh_surface
            else:
                flag_surface = surface
            out.append((f"{flag_surface} arg {flag}", value))
    for m in GH_API_FIELD_RE.finditer(redacted):
        flag = f"-f {m.group(1)}"
        value = m.group(3) if m.group(3) is not None else m.group(4)
        if _is_real_prose_value(value):
            out.append((f"{gh_surface} {flag}", value))

    for m in GH_API_AT_FILE_RE.finditer(redacted):
        path = m.group(2).strip("'\"")
        if path == "-":
            continue
        try:
            text = Path(os.path.expanduser(path)).read_text()
            if text:
                out.append((f"{gh_surface} -f {m.group(1)} @{path}", text))
        except OSError:
            pass

    for m in BODY_FILE_RE.finditer(redacted):
        path = m.group(1).strip("'\"")
        text = read_file(path)
        if text:
            out.append((f"{gh_surface} --body-file {path}", text))

    # An `-F` that no command owns is read as the commit message whenever the
    # command commits.
    for m in FILE_FLAG_RE.finditer(redacted):
        path = m.group(1).strip("'\"")
        _, owner = flag_owner(owners, m.start())
        if owner == "gh-text":
            label = f"{gh_surface} -F {path}"
        elif owner == "commit" or (not owner and is_commit):
            label = f"{surface} -F {path}"
        else:
            continue
        text = read_file(path)
        if text:
            out.append((label, text))

    return out


def walk_strings(obj, path: str = ""):
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


# Payload fields holding a scalar identifier or reference rather than prose.
# The checker judges each field independently, so a long-enough identifier gets
# evaluated as though it were a document and the structural rules get applied
# to it: a `team` of "Membership Management" was blocked for not containing `##
# Overview`. Such a field can never pass, because the skip marker has to live
# in the payload being judged and a team name cannot carry an HTML comment.
# Names absent from this set are still checked, so an unanticipated field fails
# closed.
NON_PROSE_FIELDS = frozenset(
    {
        "addreleases",
        "assignee",
        "blockedby",
        "blocks",
        "channel",
        "channelid",
        "cursor",
        "cycle",
        "delegate",
        "duedate",
        "duplicateof",
        "estimate",
        "id",
        "labels",
        "milestone",
        "pageid",
        "parent",
        "parentid",
        "priority",
        "project",
        "query",
        "relatedto",
        "removeblockedby",
        "removeblocks",
        "removereleases",
        "removerelatedto",
        "setreleases",
        "state",
        "team",
        "url",
    }
)


def field_name(path: str) -> str:
    """Return the bare field name from a walk_strings path.

    "links[0].title" -> "title"; "description" -> "description".
    """
    return path.split(".")[-1].split("[")[0].lower()


def extract_mcp_payloads(tool_name: str, tool_input: dict) -> list[tuple[str, str]]:
    surface = tool_name.split("__")[-1]
    out: list[tuple[str, str]] = []
    for label, value in walk_strings(tool_input):
        if not value or len(value) < 20:
            continue
        if field_name(label) in NON_PROSE_FIELDS:
            continue
        out.append((f"{surface} {label}", value))
    return out


def extract_payloads(tool_name: str, tool_input: dict) -> list[tuple[str, str]]:
    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        if isinstance(cmd, str):
            return extract_bash_payloads(cmd)
        return []
    if GATED_MCP_RE.match(tool_name):
        return extract_mcp_payloads(tool_name, tool_input)
    return []


def load_rules() -> str:
    parts: list[str] = []
    if CLAUDE_MD.exists():
        parts.append(f"=== CLAUDE.md ===\n{CLAUDE_MD.read_text()}")
    if RULES_DIR.exists():
        for path in sorted(RULES_DIR.glob("*.md")):
            parts.append(f"=== rules/{path.name} ===\n{path.read_text()}")
    return "\n\n".join(parts)


def build_prompt(rules: str, surface: str, payload: str) -> str:
    return f"""You are a strict rule-compliance checker. Read every rule below carefully, then evaluate the payload that is about to be sent to the surface shown. Block on any actual rule violation. Do not flag stylistic preferences not explicitly written in the rules.

Two hard constraints on YOUR findings:

1. NEVER flag anything that depends on counting characters or measuring widths: commit-subject length, PR-title length, line-wrap width, Markdown table column padding, alignment, or separator width. A deterministic linter enforces all of those outside this model. Character arithmetic from you is unreliable (you measure rendered width where source width is what matters) and any such finding will be mechanically discarded.
2. Resolve genuinely borderline judgment calls toward "pass". Only fail on violations you are certain about. If a rule's applicability to a payload is ambiguous (e.g., the bullet terminal-period rule, label-colon vs clause-colon), pass.

Pay particular attention to these common drift modes:

- Linear slugs (pattern `[A-Z]{{2,10}}-\\d+` like `BYB-1234` or `EPD-987`) appearing in source-code comments, docstrings, test names, or any code-evergreen surface. Forbidden by rules/git.md unless absolutely necessary. PR descriptions, commit messages, branch names, and Linear/Notion/Slack content are the right places.
- Internal or local-only paths leaking into external content: `~/nickolashkraus/`, `agent-os/`, `/Users/<name>/`, references to private repos, daily-log paths, scratch notes. Forbidden by rules/general.md. Inline a summary instead.
- Linear issue references in PR `## References` blocks: titles after the colon must be VERBATIM Linear titles, not paraphrases or abbreviations. Rule in rules/git.md.
- Forbidden tokens in commit/PR contexts: smart quotes (rules/typography.md), `Co-Authored-By:` in commits (rules/git.md), `Closes:`/`Fixes:`/`Resolves:` in PR descriptions (rules/git.md).
- Bare Linear-slug references that should be Markdown links (`[BYB-1234](url)`) in rendered Markdown surfaces (PR descriptions, review comments). Rule in rules/git.md. Bare slugs ARE correct in chat replies, commit messages, branch names, and source code.
- Hard line breaks within paragraphs in external content (PR bodies, Linear, Notion, Slack). Forbidden by rules/git.md; Markdown renderers handle wrapping. In-repo Markdown files (docs, CLAUDE.md, etc.) DO wrap at ~80 chars.
- Reference-style link shorthand `[label][]` or bare `[label]`. Forbidden by rules/typography.md.
- Paraphrased section headers or section content that drift from canonical Linear/PR/commit conventions.
- A lowercase word after a colon that ends a label or lead-in: bullets (`**Element**: lowercase`, `**Element** (note): lowercase`), line-initial link lead-ins (`[Link](url): lowercase`), and bold callouts (`**NOTE**: lowercase`). This ALSO applies to a PLAIN-TEXT bullet label with no bold/link/code markup: `- PR titles: when a PR ...` and `- Conventional Commits: the carve-out ...` are labels and MUST capitalize the word after the colon (`When`, `The`). A deterministic linter only catches the bold/link/code and all-Title-Case forms, so plain-text noun-phrase labels like `- PR titles: when` are YOUR responsibility to flag. Distinguish a label (a short noun phrase naming the item, e.g. `PR titles`, `Retry semantics`) from an imperative instruction whose colon introduces elaboration (`- Trace the data lifecycle: creation, updates ...`, `- Check edge cases: empty inputs ...`) and from a clause colon in a flowing sentence (`the entry was also stale: it declared ...`); those keep lowercase. Non-alphabetic starts (paths, code spans, numbers, URLs) are naturally exempt. Rule in rules/typography.md.
- Period rule for bulleted list items (rules/typography.md): the DEFAULT is NO terminal period on a bullet. Only flag a MISSING period when the bullet item contains internal punctuation (e.g., multiple sentences, or a semicolon-joined clause) such that the lack of terminator hurts readability. A short single-clause bullet like `- Retried events are no-ops` is correct as-is; do not demand a period. Conversely, flag a SUPERFLUOUS terminal period only when the bullet is a simple short fragment.
- Smart quotes anywhere in the payload. Look for these EXACT characters: U+2018 (LEFT SINGLE QUOTATION MARK), U+2019 (RIGHT SINGLE QUOTATION MARK), U+201C (LEFT DOUBLE QUOTATION MARK), U+201D (RIGHT DOUBLE QUOTATION MARK). They are visually subtle but always forbidden. Examples of forbidden runs to spot: a curly opening quote followed by a word followed by a curly closing quote anywhere in prose, no matter how short. Flag every occurrence regardless of context. Rule in rules/typography.md.

Surface-specific lens:

- `git commit message`: The imperative-mood and no-terminal-period rules apply ONLY to the subject, which is the FIRST line of the payload. Everything after the first blank line is the commit body: it is ordinary prose, so declarative verbs (`Adds`, `Fixes`, `Covers`) and terminal periods are CORRECT there and must NOT be flagged. Subject rules: imperative subject, no terminal period, no Co-Authored-By; bare Linear slug in subject is correct. Subject length and body wrap width are enforced deterministically elsewhere; do NOT count characters. When the subject matches `SLUG: Exact Issue Title` (e.g., `BYB-1345: Membership Upgrade Creates Duplicate Active Subscriptions in Stripe`), that rule supersedes the generic subject rules; it has NO length cap and keeps the issue title's capitalization. Conventional Commits carve-out (rules/git.md): when the subject matches `type(scope): description` with a lowercase type (feat, fix, docs, test, chore, refactor, etc.), the repo convention wins. The lowercase type, lowercase description, and lowercase-after-colon form are all CORRECT; do not flag any of them and do not demand `Fix(...)` capitalization.
- `git commit message body`: This payload is a commit-message BODY paragraph (a later `-m` value), never the subject. The subject-only rules do NOT apply: declarative verbs (`Adds`, `Fixes`, `Covers`) and terminal periods are CORRECT here; do NOT flag imperative mood or a trailing period. Only typography and content rules apply to the body: no smart quotes, backtick code identifiers, capitalize the first word after a label-ending colon, and no Co-Authored-By / internal paths.
- `GitHub PR` body or comment: single line per paragraph (no hard wraps), Markdown links for Linear refs, verbatim Linear titles in References, no Closes/Fixes/Resolves, no internal paths. A PR title (`--title`) is NOT a commit subject: it has no length limit and no imperative-mood requirement beyond rules/git.md's own PR-title rules. Never flag Markdown table padding or column alignment (deterministic linter territory).
- Trivial PR bodies are allowed to be a single declarative sentence (rules/git.md explicitly permits "Service should not be publicly available." or "Determines document upload status from Google Cloud Storage." as valid trivial bodies). Do NOT demand a leading verb on these. Only flag the "lead with a declarative verb" rule for longer PR bodies and for openers like `This PR adds...` or `In this PR, I...`.
- `Linear issue` (`save_issue`): standard sections (Overview, Acceptance Criteria, Implementation Details, References), Title Case for issue titles, no extra newlines for human readability.
- `Notion page`: same prose conventions; references via real links.
- `Slack message`: typography rules; a table pasted as plain-text TSV does not render (rules/slack.md).

Return ONLY a JSON object matching this exact shape:

{{"verdict": "pass" or "fail", "violations": [{{"rule_file": "rules/X.md", "rule_quote": "exact quote from the rule", "payload_excerpt": "the offending substring from the payload", "suggested_fix": "concrete fix instruction"}}]}}

If the payload is compliant, return `{{"verdict": "pass", "violations": []}}`. Only set verdict to "fail" when there is at least one real violation. Do not invent rules; quote only from the rule files below.

=== RULES ===

{rules}

=== PAYLOAD (destined for: {surface}) ===

{payload}
"""


def run_check(rules: str, surface: str, payload: str) -> tuple[str, list[dict]]:
    """Spawn `claude --print` to evaluate payload. Returns (verdict, violations)."""
    if len(payload) > MAX_PAYLOAD_CHARS:
        payload = payload[:MAX_PAYLOAD_CHARS] + "\n\n[... truncated ...]"

    prompt = build_prompt(rules, surface, payload)
    try:
        result = subprocess.run(
            [
                "claude",
                "--print",
                "--no-session-persistence",
                "--model",
                "opus",
                "--allowed-tools",
                "",
                "--output-format",
                "json",
                "--json-schema",
                json.dumps(VERDICT_SCHEMA),
            ],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SEC,
            check=False,
        )
    except subprocess.TimeoutExpired:
        # Fail OPEN. A linter timing out must never block a correct
        # payload; the log preserves the event for audit. "soft-pass"
        # (vs "pass") keeps the verdict out of the cache so a later
        # identical payload still gets a real check.
        log(f"TIMEOUT_FAIL_OPEN surface={surface}")
        return ("soft-pass", [])

    if result.returncode != 0:
        log(f"NONZERO_EXIT rc={result.returncode} stderr={result.stderr[:500]}")
        return ("soft-pass", [])

    raw = result.stdout.strip()
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        log(f"BAD_ENVELOPE_JSON raw={raw[:500]}")
        return ("soft-pass", [])

    structured = envelope.get("structured_output")
    if isinstance(structured, dict):
        verdict_obj = structured
    else:
        result_text = envelope.get("result", "")
        if isinstance(result_text, str) and result_text.strip():
            text = result_text.strip()
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            try:
                verdict_obj = json.loads(text)
            except json.JSONDecodeError:
                log(f"BAD_RESULT_JSON text={text[:500]}")
                return ("soft-pass", [])
        else:
            log("EMPTY_VERDICT envelope had no structured_output or result")
            return ("soft-pass", [])

    verdict = verdict_obj.get("verdict", "pass")
    violations = verdict_obj.get("violations", []) or []
    return (verdict, violations)


SMART_QUOTE_KEYWORDS = ("smart quote", "curly", "quotation mark")
FORBIDDEN_CHAR_CLASSES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("‘’“”", SMART_QUOTE_KEYWORDS),
)

DASHES = "—–"
DASH_RULE_RE = re.compile(r"\be[mn][ -]?dash", re.IGNORECASE)


def _is_dash_violation(v: dict, payload: str) -> bool:
    """Drop model findings against em or en dashes. No rule forbids them, but
    the model flags them from habit and from any stale mention in a rule file.
    A finding counts when its `rule_quote` names the dash, or when it mentions
    a dash the payload does not contain. A list lead-in finding whose fix
    mentions a real dash is kept, and a quote that also names smart quotes is
    left to `_is_phantom_char_violation`."""
    quote = str(v.get("rule_quote", "")).lower()
    if any(kw in quote for kw in SMART_QUOTE_KEYWORDS):
        return False
    if DASH_RULE_RE.search(quote):
        return True
    excerpt = str(v.get("payload_excerpt", ""))
    blob = f"{v.get('suggested_fix', '')} {excerpt}"
    mentioned = DASH_RULE_RE.search(blob) or any(c in excerpt for c in DASHES)
    return bool(mentioned) and not any(c in payload for c in DASHES)


WIDTH_ARITHMETIC_RE = re.compile(
    r"separator row|extra dash|\bdashes\b"
    r"|column[^.\n]{0,30}width|width[^.\n]{0,30}column"
    r"|\bpadded\b|\bpadding\b|chars? wide|characters wide"
    r"|\b\d+\s+(?:vs\.?|versus)\s+\d+"
    r"|50 characters|72 characters|exceeds? \d+ char"
    r"|subject[^.\n]{0,30}\b\d+ char",
    re.IGNORECASE,
)


def _is_width_arithmetic_violation(v: dict) -> bool:
    """Drop model findings that hinge on character counting (table column
    padding, subject length, wrap width). lint-outbound.py enforces those
    deterministically on the raw source text; the model's arithmetic is
    unreliable (it measures rendered width, miscounts by one, and gives
    different answers for the same payload) and was the dominant false-positive
    class. Only the model's own prose is inspected, not payload_excerpt, so
    a finding ABOUT a table (e.g., a bare slug in a cell) is not swallowed by
    the table's dashes."""
    blob = " ".join(str(v.get(k, "")) for k in ("rule_quote", "suggested_fix"))
    return bool(WIDTH_ARITHMETIC_RE.search(blob))


def load_cache() -> dict:
    try:
        data = json.loads(CACHE_FILE.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(cache: dict) -> None:
    now = time.time()
    entries = {
        k: v
        for k, v in cache.items()
        if isinstance(v, dict) and now - v.get("ts", 0) < CACHE_TTL_SEC
    }
    if len(entries) > CACHE_MAX_ENTRIES:
        oldest_first = sorted(entries.items(), key=lambda kv: kv[1].get("ts", 0))
        entries = dict(oldest_first[-CACHE_MAX_ENTRIES:])
    try:
        tmp = CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(entries))
        tmp.replace(CACHE_FILE)
    except OSError:
        pass


def cache_key(rules_digest: str, surface: str, payload: str) -> str:
    return hashlib.sha256(f"{rules_digest}\0{surface}\0{payload}".encode()).hexdigest()


def _is_phantom_char_violation(v: dict, payload: str) -> bool:
    """Drop model findings about forbidden characters that the payload does not
    actually contain. The deep-check prompt primes the model to hunt for smart
    quotes, and it occasionally hallucinates them in straight-quoted text,
    re-rendering the excerpt with the curly characters it imagined. Character
    presence is mechanically checkable, so the model's claim is only accepted
    when the codepoints exist in the raw payload."""
    blob = " ".join(
        str(v.get(k, "")) for k in ("rule_quote", "payload_excerpt", "suggested_fix")
    ).lower()
    excerpt = v.get("payload_excerpt", "")
    for chars, keywords in FORBIDDEN_CHAR_CLASSES:
        about_class = any(kw in blob for kw in keywords) or any(
            c in excerpt for c in chars
        )
        if about_class and not any(c in payload for c in chars):
            return True
    return False


def main() -> int:
    if os.environ.get("CLAUDE_RULE_CHECK_DISABLE") == "1":
        return 0

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    if not isinstance(tool_input, dict):
        return 0

    items = extract_payloads(tool_name, tool_input)
    if not items:
        return 0

    rules = load_rules()
    if not rules:
        return 0

    # CLAUDE_RULE_CHECK_NO_CACHE=1 forces live checks (used by eval.py so
    # it measures the model, not the cache).
    use_cache = os.environ.get("CLAUDE_RULE_CHECK_NO_CACHE") != "1"
    cache = load_cache() if use_cache else {}
    cache_dirty = False
    # The digest covers the rule files AND this hook's own source: the
    # prompt template lives in the source, so a prompt edit must
    # invalidate cached verdicts just like a rule edit does.
    try:
        hook_source = Path(__file__).read_text()
    except OSError:
        hook_source = ""
    rules_digest = hashlib.sha256((rules + hook_source).encode()).hexdigest()[:16]

    all_violations: list[tuple[str, dict]] = []
    for surface, text in items:
        if not isinstance(text, str) or len(text.strip()) < 5:
            continue
        skip_match = SKIP_RE.search(text)
        if skip_match:
            reason = skip_match.group(1) or "no reason given"
            log(f"SKIP tool={tool_name} surface={surface} reason={reason}")
            continue
        # Identical payloads get identical verdicts: the deep check is
        # LLM-backed and non-deterministic, so a payload that passed once
        # must not fail on a later identical invocation (and vice versa).
        key = cache_key(rules_digest, surface, text)
        cached = cache.get(key)
        if isinstance(cached, dict):
            verdict = cached.get("verdict", "pass")
            violations = cached.get("violations", []) or []
            cached_note = " (cached)"
        else:
            verdict, violations = run_check(rules, surface, text)
            cached_note = ""
            if use_cache and verdict in ("pass", "fail"):
                cache[key] = {
                    "verdict": verdict,
                    "violations": violations,
                    "ts": time.time(),
                }
                cache_dirty = True
        if verdict == "fail":
            for v in violations:
                if _is_dash_violation(v, text):
                    log(
                        f"DASH tool={tool_name} surface={surface} "
                        f"dropped dash finding: {v.get('rule_quote', '')[:80]}"
                    )
                    continue
                if _is_phantom_char_violation(v, text):
                    log(
                        f"PHANTOM tool={tool_name} surface={surface} "
                        f"dropped char finding: {v.get('rule_quote', '')[:80]}"
                    )
                    continue
                if _is_width_arithmetic_violation(v):
                    log(
                        f"ARITHMETIC tool={tool_name} surface={surface} "
                        f"dropped width finding: {v.get('rule_quote', '')[:80]}"
                    )
                    continue
                all_violations.append((surface, v))
        log(
            f"CHECK tool={tool_name} surface={surface} verdict={verdict} "
            f"violations={len(violations)}{cached_note}"
        )

    if cache_dirty:
        save_cache(cache)

    if not all_violations:
        return 0

    sys.stderr.write(
        "Deep rule-check violations. Fix the payload and retry. For a genuine "
        'false positive, add `<!-- rule-check: skip reason="..." -->` to the '
        "payload (logged for audit).\n\n"
    )
    for surface, v in all_violations:
        rule_file = v.get("rule_file", "?")
        rule_quote = v.get("rule_quote", "")
        excerpt = v.get("payload_excerpt", "")[:300]
        fix = v.get("suggested_fix", "")
        sys.stderr.write(f"  [{surface}] {rule_file}\n")
        sys.stderr.write(f"    rule:    {rule_quote}\n")
        sys.stderr.write(f"    payload: {excerpt}\n")
        sys.stderr.write(f"    fix:     {fix}\n\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
