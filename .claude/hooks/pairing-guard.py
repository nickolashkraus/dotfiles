#!/usr/bin/env python3
"""
PreToolUse hook: the pairing guard. When the user and Claude work in the
same worktree, the user turns the guard on, and Claude can no longer
change the worktree's Git state or write its files from the shell.

The guard is on for a worktree while `<git-dir>/claude-pairing` exists,
where `<git-dir>` is what `git rev-parse --absolute-git-dir` prints there,
so each linked worktree has its own switch. `<Space>cg` in Vim toggles it
for the current buffer's worktree.

While it is on, the hook blocks (exit 2):

- Git commands that change the index, the checked-out branch, the working
  tree, history or a remote (`GIT_WRITES`, plus the write forms of
  `stash`, `worktree`, `submodule` and `branch`).
- `gh` commands that check out, create, merge or sync from it.
- Shell writes into it: redirects, `tee`, `rm`, `mv`, `cp`, `touch`,
  `sed -i`, `perl -i`, `find -delete`, and formatters that fix in place.
- Anything that could switch the guard off: deleting the flag, or writing
  inside the Git directory from the shell or the file tools.

The Edit, Write and NotebookEdit tools stay allowed in the worktree. They
refuse a file that changed on disk since Claude last read it, which is
what keeps the user's saved work from being overwritten.

Detection parses the shell command; it is not a sandbox. A program that
opens files itself (`python3 -c "open(...)"`) is not seen, and a path
built from a variable set in an earlier Bash call cannot be resolved.
"""

from __future__ import annotations

import functools
import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

FLAG_NAME = "claude-pairing"
FLAG_REASON = "deleting or moving the guard flag"

GIT_WRITES = frozenset(
    {
        "add",
        "am",
        "apply",
        "checkout",
        "checkout-index",
        "cherry-pick",
        "clean",
        "commit",
        "filter-branch",
        "filter-repo",
        "merge",
        "mv",
        "pull",
        "push",
        "read-tree",
        "rebase",
        "reset",
        "restore",
        "revert",
        "rm",
        "switch",
        "update-index",
        "update-ref",
    }
)

# Subcommands that write unless their action is one of these. A bare
# `git stash` pushes; the other bare forms only print.
GIT_SAFE_ACTIONS = {
    "bisect": frozenset({"help", "log", "view", "visualize"}),
    "stash": frozenset({"list", "show"}),
    "worktree": frozenset({"add", "list", "prune"}),
    "submodule": frozenset({"status", "summary"}),
    "sparse-checkout": frozenset({"list"}),
}

GIT_BRANCH_WRITE_FLAGS = frozenset("dDmMcCfu")
GIT_BRANCH_WRITE_OPTIONS = (
    "--delete",
    "--move",
    "--copy",
    "--force",
    "--set-upstream-to",
    "--unset-upstream",
    "--edit-description",
)
GIT_OPTIONS_WITH_VALUE = frozenset({"-c", "--git-dir", "--work-tree", "--namespace"})

GH_WRITES = {
    "pr": frozenset({"checkout", "create", "merge"}),
    "repo": frozenset({"sync"}),
}

# Every path argument is written.
FILE_WRITERS = frozenset(
    {"chmod", "chown", "mv", "rm", "rmdir", "shred", "tee", "touch", "truncate", "unlink"}
)
# Only the destination, the last path argument, is written.
DEST_WRITERS = frozenset({"cp", "install", "ln", "rsync"})
VALUE_FLAGS = {
    "truncate": frozenset({"-s", "--size", "-r", "--reference"}),
    "install": frozenset({"-m", "-o", "-g"}),
    "rsync": frozenset({"-e", "--rsh", "--exclude", "--include"}),
}

# In a perl or ruby bundle, a switch that takes a value (`-M`, `-r`, `-e`) ends it.
IN_PLACE_FLAG = {
    "sed": re.compile(r"^(-[a-zA-Z]*i|--in-place)"),
    "perl": re.compile(r"^-(?:(?![CEFIMemrx])[a-zA-Z])*i"),
    "ruby": re.compile(r"^-(?:(?![CEFIMemrx])[a-zA-Z])*i"),
}

SHELLS = frozenset({"bash", "dash", "sh", "zsh"})
FIX_SCRIPT_RE = re.compile(r"fmt|format|fix")
CHECK_FLAGS = frozenset({"--check", "--diff", "--check-only", "-check", "-diff", "-write=false"})

DELETE_COMMANDS = frozenset({"mv", "rm", "rmdir", "shred", "unlink"})
INTERPRETER_RE = re.compile(r"(?:python|pypy)[\d.]*|perl|ruby|node|php|osascript")
# A delete command in command position, or a delete call, inside interpreter code.
INTERP_DELETE_RE = re.compile(
    r"(?:^|[\n;{(\[,'\"`])\s*(?:rm|mv|unlink|rmdir|shred|rename)\b(?![-./])"
    r"|\b(?:os\.(?:remove|replace)|shutil\.move|File\.delete|FileUtils\.(?:rm|mv|remove)\w*)\s*\("
    r"|\.(?:unlink|rename|rmdir|rm)\w*\s*\("
)
# A delete command whose flag path comes from a command substitution.
SUBST_FLAG_DELETE_RE = re.compile(
    r"(?:^|[\n;&|(])\s*(?:\S*/)?(?:rm|mv|unlink|rmdir|shred)\s[^\n;&|]*?(?:\$\(|`)[^\n;&|]*?/"
    + re.escape(FLAG_NAME)
    + r"(?![\w.-])"
)

PUNCTUATION = "();<>|&\n"
HEREDOC_RE = re.compile(
    r"<<-?[ \t]*(['\"]?)([A-Za-z_]\w*)\1([^\n]*)\n(.*?)\n[ \t]*\2[ \t]*(?=\n|$)",
    re.DOTALL,
)
ASSIGN_RE = re.compile(r"[A-Za-z_]\w*=.*", re.DOTALL)
VAR_RE = re.compile(r"\$(?:\{(\w+)\}|(\w+))")

Intent = tuple[str, "Path | None"]


@dataclass
class State:
    cur: Path
    env: dict[str, str | None] = field(default_factory=dict)

    def fork(self) -> State:
        return State(self.cur, dict(self.env))


@functools.lru_cache(maxsize=None)
def paired_gitdir(directory: str) -> str | None:
    """Return the Git directory for `directory` when the guard is on there."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        result = subprocess.run(
            ["git", "-C", directory, "rev-parse", "--absolute-git-dir"],
            capture_output=True,
            text=True,
            timeout=3,
            env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    gitdir = result.stdout.strip()
    if result.returncode or not gitdir:
        return None
    return gitdir if os.path.exists(os.path.join(gitdir, FLAG_NAME)) else None


def paired_gitdir_for(path: Path | None) -> str | None:
    """Like `paired_gitdir`, for a path that may not exist yet."""
    if path is None:
        return None
    d = Path(os.path.realpath(path))
    while not d.is_dir():
        if d.parent == d:
            return None
        d = d.parent
    return paired_gitdir(str(d))


def worktree_of(gitdir: str) -> str:
    g = Path(gitdir)
    if (g / "gitdir").is_file():
        return str(Path((g / "gitdir").read_text().strip()).parent)
    return str(g.parent) if g.name == ".git" else gitdir


def expand(token: str, state: State) -> str | None:
    """Expand `~` and known variables, or return None if any is unknown."""
    if token == "~" or token.startswith("~/"):
        token = str(Path.home()) + token[1:]
    unknown = False

    def substitute(m: re.Match[str]) -> str:
        nonlocal unknown
        name = m.group(1) or m.group(2)
        if name in state.env:
            value = state.env[name]
        elif name == "PWD":
            value = str(state.cur)
        else:
            value = os.environ.get(name)
        if value is None:
            unknown = True
            return ""
        return value

    out = VAR_RE.sub(substitute, token)
    return None if unknown or "$" in out else out


def resolve(token: str, state: State, base: Path | None = None) -> Path | None:
    expanded = expand(token, state)
    if not expanded:
        return None
    return Path(os.path.normpath((base or state.cur) / expanded))


def drop_flags(words: list[str], value_flags: frozenset[str] = frozenset()) -> list[str]:
    i = 0
    while i < len(words) and words[i].startswith("-") and words[i] != "-":
        i += 2 if words[i] in value_flags else 1
    return words[i:]


def unwrap(words: list[str]) -> list[str]:
    """Strip launchers (`sudo`, `timeout`, `uv run`, `xargs`) off a command."""
    while words:
        name = os.path.basename(words[0])
        nxt = words[1:2]
        if name in ("builtin", "caffeinate", "command", "exec", "nice", "nohup", "time"):
            words = drop_flags(words[1:])
        elif name == "sudo":
            words = drop_flags(words[1:], frozenset({"-u", "-g"}))
        elif name == "env":
            words = drop_flags(words[1:], frozenset({"-u", "-C"}))
            while words and ASSIGN_RE.fullmatch(words[0]):
                words = words[1:]
        elif name == "timeout":
            words = drop_flags(words[1:], frozenset({"-s", "-k"}))[1:]
        elif name == "xargs":
            words = drop_flags(
                words[1:], frozenset({"-I", "-J", "-L", "-n", "-P", "-R", "-d", "-E", "-s"})
            )
        elif name in ("hatch", "pdm", "pipenv", "poetry", "rye", "uv") and nxt == ["run"]:
            words = drop_flags(
                words[2:], frozenset({"--with", "--python", "-p", "--env-file", "--group"})
            )
        elif name in ("bunx", "npx", "uvx"):
            words = drop_flags(words[1:], frozenset({"--from", "--with", "--package", "-p"}))
        elif name == "pipx" and nxt == ["run"]:
            words = drop_flags(words[2:])
        elif name in ("pnpm", "yarn") and nxt in (["exec"], ["dlx"]):
            words = words[2:]
        elif re.fullmatch(r"python[\d.]*", name) and nxt == ["-m"]:
            words = words[2:]
        else:
            break
    return words


def flag_intents(targets: list[str], state: State) -> list[Intent]:
    """Return a flag intent for each target named like the flag, resolved or not."""
    return [
        (FLAG_REASON, resolve(t, state))
        for t in targets
        if os.path.basename(t.rstrip("/")) == FLAG_NAME
    ]


def strip_gh_repo(args: list[str]) -> list[str]:
    """Drop `-R`/`--repo` and its value, which may precede the subcommand."""
    out: list[str] = []
    i = 0
    while i < len(args):
        if args[i] in ("-R", "--repo"):
            i += 1
        elif not args[i].startswith(("-R", "--repo=")):
            out.append(args[i])
        i += 1
    return out


def path_args(name: str, args: list[str]) -> list[str]:
    value_flags = VALUE_FLAGS.get(name, frozenset())
    out: list[str] = []
    i, flags_done = 0, False
    while i < len(args):
        a = args[i]
        if not flags_done and a == "--":
            flags_done = True
        elif not flags_done and a.startswith("-") and a != "-":
            i += 1 if a in value_flags else 0
        else:
            out.append(a)
        i += 1
    return out


def is_git_write(sub: str, rest: list[str]) -> bool:
    if sub in GIT_WRITES:
        return True
    if sub in GIT_SAFE_ACTIONS:
        action = next((a for a in rest if not a.startswith("-")), "")
        if not action:
            return sub == "stash"
        return action not in GIT_SAFE_ACTIONS[sub]
    if sub == "branch":
        return any(
            a.startswith(GIT_BRANCH_WRITE_OPTIONS)
            or (re.fullmatch(r"-[a-zA-Z]+", a) is not None and bool(set(a[1:]) & GIT_BRANCH_WRITE_FLAGS))
            for a in rest
        )
    if sub == "symbolic-ref":
        names = [a for a in rest if not a.startswith("-")]
        return len(names) > 1 or bool({"-d", "--delete"} & set(rest))
    return False


def scan_git(args: list[str], state: State) -> list[Intent]:
    target = state.cur
    i = 0
    while i < len(args) and args[i].startswith("-"):
        opt = args[i]
        if opt == "-C" and i + 1 < len(args):
            target = resolve(args[i + 1], state, base=target) or target
            i += 2
        elif opt in GIT_OPTIONS_WITH_VALUE:
            i += 2
        elif opt.startswith(("--work-tree=", "--git-dir=")):
            target = resolve(opt.split("=", 1)[1], state, base=target) or target
            i += 1
        else:
            i += 1
    if i >= len(args) or not is_git_write(args[i], args[i + 1 :]):
        return []
    return [(f"`git {args[i]}`", target)]


def formatter(name: str, args: list[str]) -> str | None:
    """Name the command if it rewrites files in place, else None."""
    flags = set(args)
    sub = args[0] if args else ""
    if name == "ruff":
        if sub == "format" and not flags & CHECK_FLAGS:
            return "`ruff format`"
        if sub == "check" and flags & {"--fix", "--fix-only"}:
            return "`ruff check --fix`"
        return None
    if name in ("black", "mdformat", "rustfmt", "stylua") and not flags & CHECK_FLAGS:
        return f"`{name}`"
    if name == "isort" and not flags & (CHECK_FLAGS | {"-c"}):
        return "`isort`"
    if name in ("cargo", "terraform", "tofu") and sub == "fmt" and not flags & CHECK_FLAGS:
        return f"`{name} fmt`"
    if name == "prettier" and flags & {"--write", "-w"}:
        return "`prettier --write`"
    if name == "eslint" and "--fix" in flags:
        return "`eslint --fix`"
    if name == "rubocop" and flags & {"-a", "-A", "--autocorrect", "--autocorrect-all"}:
        return "`rubocop --autocorrect`"
    if name in ("gofmt", "goimports", "shfmt") and "-w" in flags:
        return f"`{name} -w`"
    if name in ("autopep8", "clang-format") and flags & {"-i", "--in-place"}:
        return f"`{name} -i`"
    if name == "pre-commit" and sub in ("", "run"):
        return "`pre-commit run`"
    if name in ("bun", "npm", "pnpm", "yarn"):
        script = args[1] if sub in ("run", "run-script") and len(args) > 1 else sub
        if FIX_SCRIPT_RE.search(script) and "check" not in script:
            return f"`{name} {script}`"
    if name == "make":
        targets = [t for t in args if not t.startswith("-") and FIX_SCRIPT_RE.search(t)]
        if targets:
            return f"`make {targets[0]}`"
    return None


def scan_words(
    words: list[str], state: State, stdin_body: str | None, depth: int
) -> list[Intent]:
    words = unwrap(words)
    if not words:
        return []
    name, args = os.path.basename(words[0]), words[1:]

    if name in ("cd", "pushd"):
        dest = next((a for a in args if not a.startswith("-")), "~")
        state.cur = resolve(dest, state) or state.cur
        return []
    if name == "export":
        for a in args:
            if ASSIGN_RE.fullmatch(a):
                key, _, value = a.partition("=")
                state.env[key] = expand(value, state)
        return []
    if name in SHELLS:
        c = next((i for i, a in enumerate(args) if re.fullmatch(r"-[a-zA-Z]*c", a)), None)
        if c is not None and c + 1 < len(args):
            return scan_command(args[c + 1], state.fork(), depth + 1)
        if stdin_body is not None:
            return scan_command(stdin_body, state.fork(), depth + 1)
        return []
    if name == "eval":
        return scan_command(" ".join(args), state.fork(), depth + 1)
    if name == "git":
        return scan_git(args, state)
    if name == "gh":
        args = strip_gh_repo(args)
        if len(args) >= 2 and args[1] in GH_WRITES.get(args[0], ()):
            return [(f"`gh {args[0]} {args[1]}`", state.cur)]
        return []
    if name == "find":
        starts: list[str] = []
        for a in args:
            if a.startswith(("-", "(", "!")):
                break
            starts.append(a)
        roots = [p for s in (starts or ["."]) if (p := resolve(s, state))]
        selects_flag = any(os.path.basename(a.rstrip("/")) == FLAG_NAME for a in args)
        intents: list[Intent] = []
        if "-delete" in args:
            intents += [("`find -delete`", r) for r in roots]
            intents += [(FLAG_REASON, None)] if selects_flag else []
        for flag in ("-exec", "-execdir", "-ok", "-okdir"):
            if flag in args:
                inner = args[args.index(flag) + 1 :]
                if "+" in inner:
                    inner = inner[: inner.index("+")]
                if selects_flag and os.path.basename((unwrap(inner) or [""])[0]) in DELETE_COMMANDS:
                    intents.append((FLAG_REASON, None))
                start = starts[0] if starts else "."
                inner = [start if w == "{}" else w for w in inner]
                intents += scan_words(inner, state.fork(), None, depth + 1)
        return intents
    if name in FILE_WRITERS:
        targets = path_args(name, args)
        if name in ("chmod", "chown"):
            targets = targets[1:]
        flag = flag_intents(targets, state) if name in DELETE_COMMANDS else []
        return flag + [(f"`{name}` on {t}", p) for t in targets if (p := resolve(t, state))]
    if name in DEST_WRITERS:
        targets = path_args(name, args)[-1:]
        return [(f"`{name}` into {t}", p) for t in targets if (p := resolve(t, state))]
    if name == "dd":
        outs = [a[3:] for a in args if a.startswith("of=")]
        return [(f"`dd` into {t}", p) for t in outs if (p := resolve(t, state))]
    if INTERPRETER_RE.fullmatch(name):
        code = [*args, stdin_body or ""]
        if any(FLAG_NAME in c for c in code) and any(INTERP_DELETE_RE.search(c) for c in code):
            return [(FLAG_REASON, None)]
    if name in IN_PLACE_FLAG and any(IN_PLACE_FLAG[name].match(a) for a in args):
        files = [p for a in args if (p := resolve(a, state)) and p.is_file()]
        return [(f"`{name} -i` on {p.name}", p) for p in files]
    reason = formatter(name, args)
    if reason:
        paths = [p for a in args if not a.startswith("-") and (p := resolve(a, state)) and p.exists()]
        return [(reason, p) for p in paths or [state.cur]]
    return []


def scan_segment(
    segment: list[str], state: State, heredocs: dict[str, str], depth: int
) -> list[Intent]:
    words: list[str] = []
    redirects: list[str] = []
    stdin_body: str | None = None
    i = 0
    while i < len(segment):
        tok = segment[i]
        if tok and set(tok) <= set(PUNCTUATION):
            if words and re.fullmatch(r"[0-9]+", words[-1]):
                words.pop()
            nxt = segment[i + 1] if i + 1 < len(segment) else ""
            if ">" in tok and not (tok.endswith("&") and re.fullmatch(r"\d+|-", nxt)):
                redirects.append(nxt)
            elif tok.startswith("<<") and nxt in heredocs:
                stdin_body = heredocs[nxt]
            i += 2
            continue
        words.append(tok)
        i += 1

    intents: list[Intent] = []
    for target in redirects:
        p = resolve(target, state)
        if p and not str(p).startswith("/dev/"):
            intents.append((f"redirect into {target}", p))

    if words and all(ASSIGN_RE.fullmatch(w) for w in words):
        for w in words:
            key, _, value = w.partition("=")
            state.env[key] = expand(value, state)
        return intents
    while words and ASSIGN_RE.fullmatch(words[0]):
        words = words[1:]
    return intents + scan_words(words, state, stdin_body, depth)


def scan_command(cmd: str, state: State, depth: int = 0) -> list[Intent]:
    """Return every (reason, path) the command would write. Raises ValueError."""
    if depth > 3:
        return []
    heredocs: dict[str, str] = {}

    def set_aside(m: re.Match[str]) -> str:
        key = f"__heredoc_{len(heredocs)}__"
        heredocs[key] = m.group(4)
        return f"<< {key}{m.group(3)}\n"

    cmd = HEREDOC_RE.sub(set_aside, cmd)
    intents: list[Intent] = [(FLAG_REASON, None)] if SUBST_FLAG_DELETE_RE.search(cmd) else []
    cmd = cmd.replace("\\\n", " ").replace("`", " ( ")
    lexer = shlex.shlex(cmd, posix=True, punctuation_chars=PUNCTUATION)
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True

    segment: list[str] = []
    for tok in [*lexer, "\n"]:
        if tok and set(tok) <= set(PUNCTUATION) and not set(tok) & {"<", ">"}:
            if segment:
                intents += scan_segment(segment, state, heredocs, depth)
            segment = []
        else:
            segment.append(tok)
    return intents


def bash_blocks(cmd: str, cwd: Path) -> list[tuple[str, str]]:
    try:
        intents = scan_command(cmd, State(cwd))
    except ValueError:
        gitdir = paired_gitdir_for(cwd)
        return [("a command the guard could not parse", gitdir)] if gitdir else []
    blocks = []
    for reason, path in intents:
        gitdir = paired_gitdir_for(path)
        if gitdir or reason == FLAG_REASON:
            blocks.append((reason, gitdir or ""))
    return blocks


def file_tool_blocks(file_path: str, cwd: Path) -> list[tuple[str, str]]:
    path = Path(file_path) if os.path.isabs(file_path) else cwd / file_path
    if path.name == FLAG_NAME:
        return [("writing the guard flag", "")]
    gitdir = paired_gitdir_for(path)
    real = Path(os.path.realpath(path))
    if gitdir and real.is_relative_to(os.path.realpath(gitdir)):
        return [(f"writing {path.name} inside the Git directory", gitdir)]
    return []


def message(blocks: list[tuple[str, str]]) -> str:
    worktrees = sorted({worktree_of(g) for _, g in blocks if g})
    where = ", ".join(worktrees) or "a paired worktree"
    reasons = "; ".join(dict.fromkeys(reason for reason, _ in blocks))
    return (
        f"BLOCKED by the pairing guard: the user is working in {where} with "
        "you, so you may not change its Git state or write its files from "
        f"the shell.\nBlocked: {reasons}.\n\n"
        "Make file changes there with the Edit or Write tool, which refuse a "
        "file that changed since your last Read. Leave staging, commits, "
        "pushes and branch changes to the user. Do not retry this in another "
        "form or work around the guard; tell the user what you need instead. "
        "Only the user turns the guard off, with <Space>cg in Vim.\n"
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    cwd = Path(payload.get("cwd") or os.getcwd())

    if tool == "Bash":
        cmd = tool_input.get("command", "")
        blocks = bash_blocks(cmd, cwd) if isinstance(cmd, str) and cmd else []
    elif tool in ("Edit", "MultiEdit", "NotebookEdit", "Write"):
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        blocks = file_tool_blocks(path, cwd) if isinstance(path, str) and path else []
    else:
        return 0

    if not blocks:
        return 0
    sys.stderr.write(message(blocks))
    return 2


if __name__ == "__main__":
    sys.exit(main())
