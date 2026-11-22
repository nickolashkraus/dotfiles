#!/usr/bin/env python3
"""
Unit tests for ~/.claude/hooks/session-start-state.py.

Builds a throwaway `domains/` tree of project manifests and checks which
project `find_project` picks for a repo, then runs the hook end to end with
`HOME` pointed at a throwaway directory, so the real notes repo is never
read.

Run: python3 .claude/evals/session-start-state/test_unit.py [HOOK_PATH]

HOOK_PATH defaults to the hook in this repo. Pass a deliberately broken
copy to confirm the tests catch the break.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_PATH = (
    Path(sys.argv[1])
    if len(sys.argv) > 1
    else Path(__file__).resolve().parents[2] / "hooks" / "session-start-state.py"
)
DOMAINS = "nickolashkraus/agent-os/master/domains"
MANIFESTS = {
    "function/projects/payments": (
        "name: Payments\n"
        "github:\n"
        "  tool: gh\n"
        "  repos:\n"
        "    - Function-Health/ppp-service\n"
        "    - Function-Health/transaction-service\n"
    ),
    "infrable": (
        "name: Infrable\n"
        "repos:\n"
        "  - path: ~/infrable-io/infrable-io\n"
        "    note: The infrable.io site.\n"
        "  - path: ~/nickolashkraus/founder\n"
        "    note: The Founder Hugo theme.\n"
    ),
    "personal/projects/other": (
        "name: Other\n"
        "description: Notes on Function-Health/admin-app, in prose only.\n"
        "related:\n"
        "  - name: Grind\n"
        "    path: ../../../grind-rip-site\n"
    ),
}

_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  [PASS] {name}")
    else:
        _failures.append(f"{name}: {detail}")
        print(f"  [FAIL] {name}  {detail}")


def load_hook():
    spec = importlib.util.spec_from_file_location("session_start_state", HOOK_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(home: Path) -> Path:
    domains = home / DOMAINS
    for project, text in MANIFESTS.items():
        (domains / project / "notes").mkdir(parents=True)
        (domains / project / "manifest.yaml").write_text(text)
        (domains / project / "notes" / "2026-11-20.01.md").write_text(
            "# 2026-11-20.01\n\n**Status**: In progress\n"
        )
    return domains


def run_hook(home: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("GIT_", "GH_", "GITHUB_", "CLAUDE_"))
    }
    env.update(HOME=str(home), GIT_CEILING_DIRECTORIES=str(home.parent))
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps({"source": "startup", "cwd": str(cwd)}),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def run(root: Path) -> int:
    home = root / "home"
    domains = build(home)
    hook = load_hook()
    hook.PROJECT_GLOB_ROOT = str(domains)

    cases = [
        ("`- Org/repo` list entry", "ppp-service", "function/projects/payments"),
        (
            "second `- Org/repo` entry",
            "transaction-service",
            "function/projects/payments",
        ),
        ("`- path: ~/org/repo` entry", "infrable-io", "infrable"),
        ("second `- path:` entry", "founder", "infrable"),
        ("repo named only in prose", "admin-app", None),
        ("repo named only in a nested `path:`", "grind-rip-site", None),
        ("repo named nowhere", "unlisted", None),
        ("repo name is a path prefix", "infrable", None),
    ]
    for name, repo, project in cases:
        got = hook.find_project(repo)
        want = str(domains / project) if project else None
        check(name, got == want, f"find_project({repo!r}) = {got!r}, want {want!r}")

    cwd = home / "infrable-io" / "infrable-io"
    cwd.mkdir(parents=True)
    r = run_hook(home, cwd)
    check(
        "session line names the `path:` project",
        r.returncode == 0 and "Project: infrable\n" in r.stdout,
        f"exit {r.returncode}: {r.stdout.strip()[:300]} {r.stderr.strip()[:300]}",
    )

    print(f"\n{len(_failures)} failure(s)")
    return 1 if _failures else 0


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="session-start-state-")).resolve()
    try:
        return run(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
