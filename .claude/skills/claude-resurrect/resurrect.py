#!/usr/bin/env python3
"""Retrieve interactive Claude Code sessions for a given date and emit a
resume table plus a tmux rebuild script.

Filters to real interactive sessions: those with at least one genuine user
turn on the target date. Hook-spawned subsessions (rule-check, lint-outbound)
and skill-runner-only sessions have zero genuine turns and are dropped.
Nested subagent transcripts live under */subagents/ and are excluded by the
top-level glob.

Usage:
    resurrect.py [today|yesterday|YYYY-MM-DD]   # default: today (local)
"""

import datetime
import glob
import json
import os
import sys

PROJECTS = os.path.expanduser("~/.claude/projects")

# User messages that are not genuine turns (harness/hook/skill-runner noise).
_NOISE_PREFIXES = ("<", "Caveat", "[SYSTEM NOTIFICATION")
_NOISE_CONTAINS = (
    "local-command",
    "strict rule-compliance",
    "continued from a previous",
    "Base directory for this skill",
)


def _target_date(arg: str | None) -> datetime.date:
    today = datetime.date.today()
    if not arg or arg == "today":
        return today
    if arg == "yesterday":
        return today - datetime.timedelta(days=1)
    return datetime.date.fromisoformat(arg)


def _local_dt(ts: str) -> datetime.datetime | None:
    try:
        return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
    except (ValueError, AttributeError):
        return None


def _message_text(o: dict) -> str:
    m = o.get("message", {})
    c = m.get("content")
    if isinstance(c, str):
        return c.strip()
    if isinstance(c, list):
        return " ".join(
            p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text"
        ).strip()
    return ""


def _is_genuine(text: str) -> bool:
    if not text:
        return False
    if text.startswith(_NOISE_PREFIXES):
        return False
    return not any(s in text for s in _NOISE_CONTAINS)


def collect(target: datetime.date) -> list[dict]:
    sessions = []
    for f in glob.glob(os.path.join(PROJECTS, "*", "*.jsonl")):
        sid = os.path.basename(f)[:-6]
        title = None
        cwd = None
        first_genuine = None
        genuine = 0
        day_times = []
        try:
            with open(f) as fh:
                for line in fh:
                    if not line.startswith("{"):
                        continue
                    try:
                        o = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if o.get("type") == "custom-title" and o.get("customTitle"):
                        title = o["customTitle"]
                    if cwd is None and o.get("cwd"):
                        cwd = o["cwd"]
                    ldt = _local_dt(o.get("timestamp", ""))
                    if ldt and ldt.date() == target:
                        day_times.append(ldt)
                    if o.get("type") == "user":
                        t = _message_text(o)
                        if _is_genuine(t):
                            genuine += 1
                            if first_genuine is None:
                                first_genuine = t.replace("\n", " ")[:200]
        except OSError:
            continue
        if not day_times or genuine < 1:
            continue
        sessions.append(
            {
                "sid": sid,
                "title": title or "(untitled)",
                "cwd": cwd or "(unknown)",
                "first": min(day_times),
                "last": max(day_times),
                "turns": genuine,
                "prompt": first_genuine or "",
            }
        )
    sessions.sort(key=lambda s: (s["cwd"], s["first"]))
    return sessions


def _tilde(path: str) -> str:
    home = os.path.expanduser("~")
    return path.replace(home, "~", 1) if path.startswith(home) else path


def render(sessions: list[dict], target: datetime.date) -> str:
    out = [f"# Claude sessions with activity on {target.isoformat()}: {len(sessions)}", ""]
    if not sessions:
        out.append("No interactive sessions found for that date.")
        return "\n".join(out)
    by_dir: dict[str, list[dict]] = {}
    for s in sessions:
        by_dir.setdefault(s["cwd"], []).append(s)
    for cwd, group in by_dir.items():
        out.append(f"## {_tilde(cwd)}")
        for s in group:
            hhmm = f"{s['first']:%H:%M}-{s['last']:%H:%M}"
            out.append(f"  [{s['title']}] {hhmm}  turns={s['turns']}")
            out.append(f"    resume: (cd {_tilde(cwd)} && claude --resume {s['sid']})")
            out.append(f"    first:  {s['prompt'][:120]}")
        out.append("")
    return "\n".join(out)


def write_tmux_script(sessions: list[dict], target: datetime.date) -> str:
    path = f"/tmp/claude-resurrect-{target.isoformat()}.sh"
    session_name = "resurrect"
    lines = [
        "#!/usr/bin/env bash",
        f"# Rebuild a tmux session with one window per Claude session ({target.isoformat()}).",
        "# Each window cd's to the right directory and stages `claude --resume <id>`",
        "# WITHOUT pressing Enter, so you can review before launching each one.",
        "set -euo pipefail",
        f'tmux kill-session -t {session_name} 2>/dev/null || true',
    ]
    for i, s in enumerate(sessions):
        # tmux window names cannot contain ':' or '.'; keep it simple.
        name = s["title"].replace(":", "-").replace(".", "-").replace(" ", "-")[:32]
        cwd = s["cwd"]
        cmd = f"claude --resume {s['sid']}"
        if i == 0:
            lines.append(f'tmux new-session -d -s {session_name} -n {name!r} -c {cwd!r}')
        else:
            lines.append(f'tmux new-window -t {session_name} -n {name!r} -c {cwd!r}')
        target_pane = f"{session_name}:{i}"
        lines.append(f'tmux send-keys -t {target_pane} {cmd!r}')
    lines.append(f'tmux attach -t {session_name}')
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    os.chmod(path, 0o755)
    return path


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    target = _target_date(arg)
    sessions = collect(target)
    print(render(sessions, target))
    if sessions:
        path = write_tmux_script(sessions, target)
        print(f"\ntmux rebuild script written to: {path}")
        print(f"Review it, then run: bash {path}")


if __name__ == "__main__":
    main()
