#!/usr/bin/env python3
"""
Unit tests for .claude/git-hooks/pre-commit.

Stages files in a throwaway Git repository, runs the hook there and checks
its exit code and stderr. A `yaml.py` on `PYTHONPATH` stands in for PyYAML,
either raising `ImportError` or parsing `key: value` lines, so the tests do
not depend on what the interpreter has installed.

Run: python3 .claude/evals/pre-commit/test_unit.py [HOOK_PATH]

HOOK_PATH defaults to the hook in this repo. Pass a deliberately broken
copy to confirm the tests catch the break.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_PATH = (
    Path(sys.argv[1])
    if len(sys.argv) > 1
    else Path(__file__).resolve().parents[2] / "git-hooks" / "pre-commit"
)
NO_YAML = "raise ImportError(\"No module named 'yaml'\")\n"
STUB_YAML = (
    "class YAMLError(Exception):\n"
    "    pass\n"
    "\n"
    "\n"
    "def safe_load(text):\n"
    '    return dict(line.split(": ", 1) for line in text.splitlines() if ": " in line)\n'
)
SKILL = "---\nname: x\ndescription: Does x.\n---\n\nBody.\n"
SKILL_NO_DESCRIPTION = "---\nname: x\n---\n\nBody.\n"

_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  [PASS] {name}")
    else:
        _failures.append(f"{name}: {detail}")
        print(f"  [FAIL] {name}  {detail}")


def git_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    return env


def run_hook(
    root: Path, files: dict[str, str], yaml_module: str
) -> subprocess.CompletedProcess[str]:
    """Stage `files` in a new repo under `root` and run the hook there."""
    repo = Path(tempfile.mkdtemp(dir=root))
    env = git_env()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=env)
    for name, text in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=env)
    stub = repo.with_name(repo.name + "-stub")
    stub.mkdir()
    (stub / "yaml.py").write_text(yaml_module)
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env={**env, "PYTHONPATH": str(stub), "PYTHONDONTWRITEBYTECODE": "1"},
    )


def run(root: Path) -> int:
    cases = [
        ("valid Python", {".claude/hooks/a.py": "x = 1\n"}, NO_YAML, 0, []),
        (
            "Python syntax error",
            {".claude/hooks/a.py": "def f(:\n"},
            NO_YAML,
            1,
            ["Python syntax error at line 1"],
        ),
        ("valid JSON", {".claude/settings.json": '{"a": 1}\n'}, NO_YAML, 0, []),
        (
            "JSON parse error",
            {".claude/settings.json": '{"a": 1,}\n'},
            NO_YAML,
            1,
            ["JSON parse error at line 1"],
        ),
        ("em dash in Markdown", {"notes.md": "One \u2014 two.\n"}, NO_YAML, 0, []),
        ("en dash in Markdown", {"notes.md": "Pages 1\u20132.\n"}, NO_YAML, 0, []),
        (
            "smart quote in Markdown",
            {"notes.md": "\nSay \u201chi\u201d now.\n"},
            NO_YAML,
            1,
            ["notes.md:2: left double quote"],
        ),
        (
            "apostrophe as a smart quote",
            {"notes.md": "It\u2019s here.\n"},
            NO_YAML,
            1,
            ["notes.md:1: right single quote"],
        ),
        (
            "left single smart quote",
            {"notes.md": "Say \u2018hi now.\n"},
            NO_YAML,
            1,
            ["notes.md:1: left single quote"],
        ),
        (
            "right double smart quote",
            {"notes.md": "Say hi\u201d now.\n"},
            NO_YAML,
            1,
            ["notes.md:1: right double quote"],
        ),
        (
            "smart quote in a code span or a fence",
            {"notes.md": "Run `a \u201cb\u201d`.\n\n```\n\u201cc\u201d \u2014\n```\n"},
            NO_YAML,
            0,
            [],
        ),
        (
            "hyphen list lead-in",
            {"notes.md": "- **Element** - description\n"},
            NO_YAML,
            1,
            ["notes.md:1: list item uses `**X** -`"],
        ),
        (
            "em dash list lead-in",
            {"notes.md": "- **Element** \u2014 description\n"},
            NO_YAML,
            1,
            ["notes.md:1: list item uses `**X** -`"],
        ),
        (
            "en dash list lead-in",
            {"notes.md": "1. **Element** \u2013 description\n"},
            NO_YAML,
            1,
            ["notes.md:1: list item uses `**X** -`"],
        ),
        (
            "dash later in a list item",
            {"notes.md": "- **Element**: Description \u2014 with a dash\n"},
            NO_YAML,
            0,
            [],
        ),
        (
            "SKILL.md without frontmatter",
            {"skills/x/SKILL.md": "Body.\n"},
            NO_YAML,
            1,
            ["missing frontmatter"],
        ),
        (
            "SKILL.md checks run when yaml imports",
            {"skills/x/SKILL.md": SKILL_NO_DESCRIPTION},
            STUB_YAML,
            1,
            ["missing or empty `description:`"],
        ),
        (
            "valid SKILL.md when yaml imports",
            {"skills/x/SKILL.md": SKILL},
            STUB_YAML,
            0,
            [],
        ),
    ]
    for name, files, yaml_module, code, needles in cases:
        r = run_hook(root, files, yaml_module)
        detail = f"exit {r.returncode}: {r.stderr.strip()[:300]}"
        check(f"{name}: exit {code}", r.returncode == code, detail)
        for needle in needles:
            check(f"{name}: reports {needle!r}", needle in r.stderr, detail)
        check(f"{name}: no yaml warning", "yaml" not in r.stderr, detail)

    r = run_hook(root, {"skills/x/SKILL.md": SKILL_NO_DESCRIPTION}, NO_YAML)
    lines = r.stderr.splitlines()
    detail = f"exit {r.returncode}: {r.stderr.strip()[:300]}"
    check("missing yaml alone still passes", r.returncode == 0, detail)
    check("missing yaml prints one line", len(lines) == 1, detail)
    warning = lines[0] if lines else ""
    check("warning is GNU form", warning.startswith("pre-commit: "), detail)
    check("warning has no trailing period", not warning.endswith("."), detail)
    check("warning names the module", "yaml" in warning, detail)
    check(
        "warning names the checks skipped",
        all(w in warning for w in ("SKILL.md", "description", "name")),
        detail,
    )

    r = run_hook(
        root,
        {"a/SKILL.md": SKILL_NO_DESCRIPTION, "b/SKILL.md": SKILL_NO_DESCRIPTION},
        NO_YAML,
    )
    check(
        "two SKILL.md files warn once",
        r.returncode == 0 and len(r.stderr.splitlines()) == 1,
        f"exit {r.returncode}: {r.stderr.strip()[:300]}",
    )

    r = run_hook(
        root,
        {"skills/x/SKILL.md": SKILL, ".claude/settings.json": "{"},
        NO_YAML,
    )
    detail = f"exit {r.returncode}: {r.stderr.strip()[:300]}"
    check("missing yaml does not hide other failures", r.returncode == 1, detail)
    check("warning still printed with failures", "yaml" in r.stderr, detail)

    print(f"\n{len(_failures)} failure(s)")
    return 1 if _failures else 0


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="pre-commit-")).resolve()
    try:
        return run(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
