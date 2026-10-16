#!/usr/bin/env python3
"""
Unit tests for ~/.claude/hooks/pairing-guard.py.

Builds throwaway Git repositories (a paired one, a free one, and a repo
whose linked worktree is paired while its main worktree is not), then
feeds the hook PreToolUse payloads and checks which ones it blocks.

Run: python3 .claude/evals/pairing-guard/test_unit.py [HOOK_PATH]

HOOK_PATH defaults to the hook in this repo. Pass a deliberately broken
copy to confirm the tests catch the break.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_PATH = (
    Path(sys.argv[1])
    if len(sys.argv) > 1
    else Path(__file__).resolve().parents[2] / "hooks" / "pairing-guard.py"
)
FLAG = "claude-pairing"

_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  [PASS] {name}")
    else:
        _failures.append(f"{name}: {detail}")
        print(f"  [FAIL] {name}  {detail}")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def run_hook(tool: str, tool_input: dict, cwd: Path) -> subprocess.CompletedProcess[str]:
    payload = {"tool_name": tool, "tool_input": tool_input, "cwd": str(cwd)}
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )


def run(root: Path) -> int:
    paired, free, main_wt, linked = (root / n for n in ("paired", "free", "main", "linked"))
    for repo in (paired, free, main_wt):
        git("init", "-q", str(repo))
        (repo / "file.txt").write_text("a\n")
    git("-C", str(main_wt), "-c", "user.name=t", "-c", "user.email=t@t",
        "commit", "-q", "--allow-empty", "-m", "init")
    git("-C", str(main_wt), "worktree", "add", "-q", str(linked), "-b", "linked")
    (root / "link").symlink_to(paired)

    (paired / ".git" / FLAG).touch()
    Path(git("-C", str(linked), "rev-parse", "--absolute-git-dir"), FLAG).touch()

    P, F, O = paired, free, root
    bash_cases = [
        ("git commit in a paired cwd", "git commit -m x", P, True),
        ("read-only git in a paired cwd", "git status && git diff && git log -1", P, False),
        ("git -C paired push from a free cwd", f"git -C {P} push", F, True),
        ("git -C free commit from a paired cwd", f"git -C {F} commit -m x", P, False),
        ("cd into paired, then add", f"cd {P} && git add -A", F, True),
        ("symlink to a paired worktree", f"git -C {root}/link reset --hard", F, True),
        ("paired linked worktree", f"git -C {linked} checkout -b x", F, True),
        ("its unpaired main worktree", f"git -C {main_wt} commit -m x", F, False),
        ("git stash list", "git stash list", P, False),
        ("bare git stash", "git stash", P, True),
        ("git branch listing", "git branch -vv", P, False),
        ("git branch -D", "git branch -D old", P, True),
        ("git worktree add", "git worktree add ../mine -b mine", P, False),
        ("timeout wrapper", "timeout 30 git push", P, True),
        ("xargs wrapper", "git ls-files | xargs git rm", P, True),
        ("bash -c", "bash -c 'git push origin HEAD'", P, True),
        ("bash -lc", "bash -lc 'git push origin HEAD'", P, True),
        ("bash heredoc", "bash <<'EOF'\ngit push\nEOF", P, True),
        ("command substitution", "echo $(git commit -m x)", P, True),
        ("redirect into paired", "echo x > notes.md", P, True),
        ("redirects to /dev/null", "git status 2>/dev/null >/dev/null 2>&1", P, False),
        ("redirect into free from paired cwd", f"echo x > {F}/out.txt", P, False),
        ("variable pointing at free", f"S={F}; echo x > $S/out.txt", P, False),
        ("variable pointing at paired", f"S={P}; echo x >> $S/out.txt", F, True),
        ("unknown variable", "echo x > $UNSET_PAIRING_VAR/out.txt", F, False),
        ("heredoc into paired", "cat > notes.md <<'EOF'\nit's here\nEOF", P, True),
        ("heredoc body is data", f"cat > {F}/x.md <<'EOF'\ngit commit\nEOF", P, False),
        ("sed -i on a paired file", f"sed -i '' 's/a/b/' {P}/file.txt", F, True),
        ("sed -i on a free file from paired cwd", f"sed -i '' 's/a/b/' {F}/file.txt", P, False),
        ("sed without -i", f"sed 's/a/b/' {P}/file.txt", F, False),
        ("perl -pi", f"perl -pi -e 's/a/b/' {P}/file.txt", F, True),
        ("ruff format", "uv run ruff format .", P, True),
        ("ruff format --check", "uv run ruff format --check .", P, False),
        ("npm run format", "npm run format", P, True),
        ("rm in paired", f"rm -f {P}/file.txt", F, True),
        ("cp out of paired", f"cp {P}/file.txt {F}/copy.txt", F, False),
        ("cp into paired", f"cp {F}/file.txt {P}/copy.txt", F, True),
        ("tee into paired", "echo x | tee -a log.txt", P, True),
        ("find -delete", "find . -name '*.pyc' -delete", P, True),
        ("find -exec rm elsewhere", f"find {F} -name x -exec rm {{}} \\;", P, False),
        ("find -exec rm in paired", f"find {P} -name x -exec rm {{}} \\;", F, True),
        ("gh pr create", "gh pr create --fill", P, True),
        ("gh pr view", "gh pr view 12", P, False),
        ("deleting the flag", f"rm {P}/.git/{FLAG}", F, True),
        ("deleting the flag via substitution", f'rm "$(git rev-parse --git-dir)/{FLAG}"', F, True),
        ("deleting the Git directory", f"rm -rf {P}/.git", F, True),
        ("free repo unaffected", "git commit -m x && git push && echo x > f", F, False),
        ("search naming the flag", f"grep -rn {FLAG} ~/.vimrc; ls ~/rm-notes", O, False),
        ("rg alternation naming the flag", f"rg -n '{FLAG}|unlink' {P}/.git", O, False),
        ("rg alternation in a paired cwd", f"rg -n '{FLAG}|unlink' .git", P, False),
        ("find naming the flag without deleting", f"find {P}/.git -name {FLAG}", F, False),
        ("find deleting the flag", f"find {O} -name {FLAG} -delete", O, True),
        ("find -exec deleting the flag", f"find {O} -name {FLAG} -exec rm {{}} \\;", O, True),
        ("deleting the flag via cd", f'cd "$(git -C {P} rev-parse --git-dir)" && rm {FLAG}', O, True),
        ("deleting the flag via unquoted substitution", f"rm $(git rev-parse --git-dir)/{FLAG}", O, True),
        ("python one-liner deleting the flag", f"python3 -c \"import os; os.remove('.git/{FLAG}')\"", O, True),
        ("perl one-liner deleting the flag", f"perl -e 'unlink \".git/{FLAG}\"'", O, True),
        ("python one-liner naming the flag", f"python3 -c \"print('{FLAG}')\"", O, False),
        ("cp with an fd redirect", f"cp file.txt {O}/out.txt 2>/dev/null", P, False),
        ("cp with an fd dup", f"cp file.txt {O}/out.txt 2>&1", P, False),
        ("cp into paired with an fd redirect", f"cp {F}/file.txt copy.txt 2>/dev/null", P, True),
        ("perl -M is not -i", f"perl -Mstrict -e 'print 1' {P}/file.txt", F, False),
        ("ruby -r is not -i", f"ruby -rdigest -e 'p 1' {P}/file.txt", F, False),
        ("perl -lpi", f"perl -lpi -e 's/a/b/' {P}/file.txt", F, True),
        ("git bisect start", "git bisect start", P, True),
        ("git bisect log", "git bisect log", P, False),
        ("git symbolic-ref write", "git symbolic-ref HEAD refs/heads/x", P, True),
        ("git symbolic-ref read", "git symbolic-ref --short HEAD", P, False),
        ("gh -R pr create", "gh -R o/r pr create --fill", P, True),
        ("gh --repo pr merge", "gh --repo o/r pr merge 1", P, True),
        ("gh -R pr view", "gh -R o/r pr view 1", P, False),
    ]
    for name, cmd, cwd, expect in bash_cases:
        r = run_hook("Bash", {"command": cmd}, cwd)
        blocked = r.returncode == 2
        check(name, blocked == expect, f"exit {r.returncode}, expected {'2' if expect else '0'}: {r.stderr.strip()[:200]}")

    file_cases = [
        ("Edit in paired", "Edit", {"file_path": f"{P}/file.txt"}, False),
        ("Write a new file in paired", "Write", {"file_path": f"{P}/new/dir/x.md"}, False),
        ("Write the flag", "Write", {"file_path": f"{P}/.git/{FLAG}"}, True),
        ("Write inside paired .git", "Write", {"file_path": f"{P}/.git/HEAD"}, True),
        ("Write inside free .git", "Write", {"file_path": f"{F}/.git/config"}, False),
    ]
    for name, tool, tool_input, expect in file_cases:
        r = run_hook(tool, tool_input, F)
        check(name, (r.returncode == 2) == expect, f"exit {r.returncode}: {r.stderr.strip()[:200]}")

    r = run_hook("Bash", {"command": "git commit -m x"}, P)
    check("message names the worktree", str(P) in r.stderr, r.stderr[:200])
    check("message names the toggle", "<Space>cg" in r.stderr, r.stderr[:200])

    (paired / ".git" / FLAG).unlink()
    r = run_hook("Bash", {"command": "git commit -m x && git push"}, P)
    check("toggling off unblocks", r.returncode == 0, r.stderr[:200])

    print(f"\n{len(_failures)} failure(s)")
    return 1 if _failures else 0


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="pairing-guard-")).resolve()
    try:
        return run(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
