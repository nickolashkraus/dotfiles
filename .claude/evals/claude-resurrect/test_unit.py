#!/usr/bin/env python3
"""
Unit tests for ~/.claude/skills/claude-resurrect/resurrect.py.

Builds two config directories with transcripts, collects from them, and runs
the tmux rebuild script it writes against a fake `tmux`.

Run: python3 .claude/evals/claude-resurrect/test_unit.py [SCRIPT_PATH]

SCRIPT_PATH defaults to the script in this repo. Pass a deliberately broken
copy to confirm the tests catch the break.
"""

from __future__ import annotations

import datetime
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_PATH = (
    Path(sys.argv[1])
    if len(sys.argv) > 1
    else Path(__file__).resolve().parents[2]
    / "skills"
    / "claude-resurrect"
    / "resurrect.py"
)
DAY = datetime.date(2026, 11, 23)
STAMP = "2026-11-23T15:00:00+00:00"

_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  [PASS] {name}")
    else:
        _failures.append(f"{name}: {detail}")
        print(f"  [FAIL] {name}  {detail}")


def load():
    spec = importlib.util.spec_from_file_location("resurrect", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def transcript(path: Path, title: str, cwd: str, prompts: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"type": "custom-title", "customTitle": title}]
    for prompt in prompts:
        rows.append(
            {
                "type": "user",
                "cwd": cwd,
                "timestamp": STAMP,
                "message": {"content": prompt},
            }
        )
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def fake_tmux(directory: Path, has_session: bool) -> Path:
    """A `tmux` that logs its arguments and answers `has-session`."""
    bindir = directory / "bin"
    bindir.mkdir(exist_ok=True)
    log = directory / "tmux.log"
    log.write_text("")
    script = bindir / "tmux"
    script.write_text(
        "#!/bin/sh\n"
        f'echo "$*" >>"{log}"\n'
        f'if [ "$1" = has-session ]; then exit {0 if has_session else 1}; fi\n'
        "exit 0\n"
    )
    script.chmod(0o755)
    return log


def run_script(path: str, directory: Path) -> subprocess.CompletedProcess:
    env = {"PATH": f"{directory / 'bin'}:/usr/bin:/bin", "HOME": str(directory)}
    return subprocess.run(
        ["bash", path], capture_output=True, text=True, check=False, env=env
    )


def main() -> int:
    resurrect = load()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        personal, work = root / "personal", root / "work"
        transcript(
            personal / "projects" / "p1" / "aaaa.jsonl",
            "notes: daily",
            "/Users/x/notes dir",
            ["Plan the day"],
        )
        transcript(
            work / "projects" / "p2" / "bbbb.jsonl",
            "ppp",
            "/Users/x/work/ppp",
            ["Fix the pool"],
        )
        transcript(
            personal / "projects" / "p1" / "cccc.jsonl",
            "hook",
            "/Users/x/notes dir",
            ["<system>noise</system>"],
        )
        transcript(
            personal / "projects" / "p1" / "aaaa" / "subagents" / "dddd.jsonl",
            "sub",
            "/Users/x/notes dir",
            ["A subagent prompt"],
        )
        configs = ((str(personal), "claude"), (str(work), "claude-fh"))

        print("collect")
        sessions = resurrect.collect(DAY, configs)
        by_id = {s["sid"]: s for s in sessions}
        check(
            "reads both config directories",
            set(by_id) == {"aaaa", "bbbb"},
            f"got {sorted(by_id)}",
        )
        check(
            "a personal session resumes with claude",
            by_id.get("aaaa", {}).get("command") == "claude --resume aaaa",
            f"got {by_id.get('aaaa', {}).get('command')!r}",
        )
        check(
            "a work session resumes with claude-fh",
            by_id.get("bbbb", {}).get("command") == "claude-fh --resume bbbb",
            f"got {by_id.get('bbbb', {}).get('command')!r}",
        )
        check(
            "no session on another date",
            resurrect.collect(DAY - datetime.timedelta(days=1), configs) == [],
        )
        check(
            "the default configs are the two real directories",
            [os.path.basename(c) for c, _ in resurrect.CONFIGS]
            == [".claude", ".claude-fh"]
            and [launcher for _, launcher in resurrect.CONFIGS]
            == ["claude", "claude-fh"],
            f"got {resurrect.CONFIGS!r}",
        )

        print("render")
        text = resurrect.render(sessions, DAY)
        check(
            "the resume line carries the session's own command",
            "&& claude-fh --resume bbbb)" in text
            and "&& claude --resume aaaa)" in text,
            text,
        )

        print("rebuild script")
        path = resurrect.write_tmux_script(sessions, DAY, str(root))
        body = Path(path).read_text()
        check("never kills a session", "kill-session" not in body, body)
        check(
            "is written where it was asked to be",
            path == str(root / f"claude-resurrect-{DAY.isoformat()}.sh"),
            path,
        )

        log = fake_tmux(root, has_session=True)
        done = run_script(path, root)
        calls = log.read_text().splitlines()
        check(
            "refuses when the session exists",
            done.returncode == 1 and "claude-resurrect:" in done.stderr,
            f"rc={done.returncode} stderr={done.stderr!r}",
        )
        check(
            "asks for the exact session name",
            calls[:1] == ["has-session -t =resurrect"],
            f"got {calls[:1]}",
        )
        check(
            "creates nothing when it refuses",
            len(calls) == 1,
            f"got {calls}",
        )

        log = fake_tmux(root, has_session=False)
        done = run_script(path, root)
        calls = log.read_text().splitlines()
        check(
            "builds the session when none exists",
            done.returncode == 0
            and any(c.startswith("new-session -d -s resurrect") for c in calls)
            and any(c.startswith("new-window -t resurrect") for c in calls),
            f"rc={done.returncode} calls={calls} stderr={done.stderr!r}",
        )
        check(
            "stages each session's command without running it",
            "send-keys -t resurrect:0 claude --resume aaaa" in calls
            and "send-keys -t resurrect:1 claude-fh --resume bbbb" in calls
            and not any("Enter" in c for c in calls),
            f"got {calls}",
        )
        check(
            "keeps a directory with a space as one argument",
            any(c.endswith("-c /Users/x/notes dir") for c in calls),
            f"got {calls}",
        )
        check(
            "strips characters tmux rejects in a window name",
            any("-n notes--daily " in c for c in calls),
            f"got {calls}",
        )

    print()
    if _failures:
        print(f"{len(_failures)} failure(s)")
        return 1
    print("0 failure(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
