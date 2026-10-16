#!/usr/bin/env python3
#
# DESCRIPTION
#   SessionStart hook. Prints the state needed to answer "where did we
#   leave off" without a ten-call reconstruction: the most recent daily
#   compact-log entries for this repo, the newest notes in the matching
#   agent-os project, and the open pull requests.
#
#   Written after the 2026-10-15 Entitlement-Driven Scheduling retro, which
#   counted 39 "where did we leave off" asks against 133 compactions and 15
#   session directories, with every input already on disk and nothing
#   reading it.
#
# USAGE
#   Configured as a SessionStart hook in settings.json. Reads the hook JSON
#   on stdin and prints plain text on stdout, which Claude Code adds to the
#   conversation. Never fails a session: every step degrades to silence.

import json
import os
import re
import subprocess
import sys

LOG_ROOT = os.path.expanduser(
    "~/nickolashkraus/agent-os/master/notes/logs"
)
PROJECT_GLOB_ROOT = os.path.expanduser(
    "~/nickolashkraus/agent-os/master/domains"
)

# Sources worth printing for. A compaction already carries its own summary
# and PostCompact writes the log entry, so re-printing there is noise.
SOURCES = {"startup", "resume", "clear", "fork"}

MAX_LOG_ENTRIES = 2
MAX_NOTES = 3
MAX_PRS = 6
BLOCK_LINES = 3

# Directory names the compact log records for more than one repo. The log
# keys an entry on `basename(cwd)` alone, so these say nothing about which
# repo the entry came from and need the body checked before they count.
GENERIC_DIRS = {
    "main", "master", "dev", "develop", "trunk", "src",
    "agent-os", "dotfiles", "nickolas", "nickolashkraus",
    "Function-Health", "",
}


def run(args, cwd=None, timeout=6):
    """Return stdout, or None on any failure. Never raises."""
    try:
        out = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception:
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def repo_name(cwd):
    """The `owner/repo` short name, from the origin remote or the path."""
    url = run(["git", "-C", cwd, "remote", "get-url", "origin"])
    if url:
        m = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", url)
        if m:
            return m.group(1).split("/")[-1]
    # Bare-plus-worktrees layout: the repo is the parent of the worktree.
    parent = os.path.basename(os.path.dirname(os.path.abspath(cwd)))
    return parent or os.path.basename(os.path.abspath(cwd))


def candidate_dirs(cwd, repo):
    """Directory names whose log entries belong to this repo.

    The compact log keys each entry on `basename(cwd)`, which in a
    bare-plus-worktrees layout is the worktree name rather than the repo.
    Every sibling worktree counts, so a session opened in one worktree
    still sees what the last session did in another.
    """
    names = {os.path.basename(os.path.abspath(cwd)), repo}
    root = os.path.dirname(os.path.abspath(cwd))
    if os.path.basename(root) == repo:
        try:
            names.update(
                d for d in os.listdir(root)
                if os.path.isdir(os.path.join(root, d))
            )
        except OSError:
            pass
    return {n for n in names if n}


def recent_log_files(limit=8):
    """Daily compact-log paths, newest first."""
    found = []
    for dirpath, _dirnames, filenames in os.walk(LOG_ROOT):
        for name in filenames:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.md", name):
                found.append(os.path.join(dirpath, name))
    return sorted(found, reverse=True)[:limit]


def log_entries(names, repo):
    """The newest compact-log entries written from these directories.

    An entry under a directory name that several repos share only counts
    when its body names this repo, since the heading alone cannot tell
    `member-journey-services/main` from `membership-service/main`.
    """
    wanted = []
    seen = set()
    for path in recent_log_files():
        day = os.path.basename(path)[:-3]
        try:
            with open(path, errors="replace") as handle:
                text = handle.read()
        except OSError:
            continue
        # Split on the `## HH:MM | dir | id` headings the log writes.
        parts = re.split(r"(?m)^## (\d{2}:\d{2}) \| (.+?) \| (\w+)\s*$", text)
        # parts: [preamble, time, dir, id, body, time, dir, id, body, ...]
        chunks = []
        for i in range(1, len(parts) - 3, 4):
            chunks.append(
                (parts[i], parts[i + 1].strip(), parts[i + 3])
            )
        for time, directory, body in reversed(chunks):
            if directory not in names:
                continue
            if directory in GENERIC_DIRS and repo.lower() not in body.lower():
                continue
            key = (day, time, directory)
            if key in seen:
                continue
            blocks = summarize(body)
            if not blocks:
                continue
            seen.add(key)
            wanted.append((day, time, directory, blocks))
            if len(wanted) >= MAX_LOG_ENTRIES:
                return wanted
    return wanted


def summarize(body):
    """Keep the Intent and Pending blocks, which answer the question."""
    blocks = {}
    label = None
    for line in body.splitlines():
        m = re.match(r"\*\*(\w+)\*\*:\s*(.*)", line)
        if m:
            label = m.group(1)
            blocks[label] = [m.group(2)] if m.group(2) else []
        elif label and line.strip():
            blocks[label].append(line.strip())
    out = []
    for label in ("Intent", "Pending", "Work"):
        if label in blocks and blocks[label]:
            kept = [x for x in blocks[label] if x][:BLOCK_LINES]
            out.append(f"  {label}: " + " ".join(kept)[:400])
        if len(out) >= 2:
            break
    return out


def find_project(repo):
    """The agent-os project directory whose manifest names this repo."""
    hits = []
    for dirpath, dirnames, filenames in os.walk(PROJECT_GLOB_ROOT):
        if "manifest.yaml" not in filenames:
            continue
        dirnames[:] = []
        path = os.path.join(dirpath, "manifest.yaml")
        try:
            with open(path, errors="replace") as handle:
                text = handle.read()
        except OSError:
            continue
        if re.search(r"(?m)^\s*-\s+\S+/" + re.escape(repo) + r"\s*$", text):
            try:
                mtime = os.path.getmtime(dirpath)
            except OSError:
                mtime = 0
            hits.append((mtime, dirpath))
    if not hits:
        return None
    return sorted(hits, reverse=True)[0][1]


def project_notes(project_dir):
    """The newest dated notes, with each one's status line."""
    notes_dir = os.path.join(project_dir, "notes")
    try:
        names = sorted(
            (n for n in os.listdir(notes_dir) if n.endswith(".md")),
            reverse=True,
        )[:MAX_NOTES]
    except OSError:
        return []
    out = []
    for name in names:
        status = ""
        try:
            with open(os.path.join(notes_dir, name), errors="replace") as fh:
                for line in fh:
                    m = re.match(r"\*\*Status\*\*:\s*(.+)", line)
                    if m:
                        status = " " + m.group(1).strip()[:110]
                        break
        except OSError:
            pass
        out.append(f"  {name}:{status}" if status else f"  {name}")
    return out


def open_prs(cwd):
    raw = run(
        [
            "gh", "pr", "list", "--author", "@me", "--state", "open",
            "--limit", str(MAX_PRS),
            "--json", "number,title",
            "--jq", '.[] | "#\\(.number) \\(.title)"',
        ],
        cwd=cwd,
    )
    if not raw:
        return []
    return [f"  {line.strip()}" for line in raw.splitlines() if line.strip()]


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}

    if payload.get("source") not in SOURCES:
        return
    if payload.get("agent_type"):
        return
    # Headless runs, such as rule-check.py's `claude --print`, have nobody
    # to ask where things left off.
    if os.environ.get("CLAUDE_CODE_SESSION_ATTENDED") == "0":
        return

    cwd = payload.get("cwd") or os.getcwd()
    if not os.path.isdir(cwd):
        return
    # A session opened through a `~/w` short link reports the link as its
    # working directory, whose basename is the link name rather than the
    # worktree's. Resolving it first keeps the sibling-worktree lookup and
    # the log matching identical either way.
    cwd = os.path.realpath(cwd)

    repo = repo_name(cwd)
    lines = []

    worktree = os.path.basename(os.path.abspath(cwd))
    head = f"Repo: {repo}"
    if worktree != repo:
        head += f" (worktree {worktree})"
    lines.append(head)

    project = find_project(repo)
    if project:
        lines.append(f"Project: {os.path.basename(project)}")

    entries = log_entries(candidate_dirs(cwd, repo), repo)
    if entries:
        lines.append("")
        lines.append("Where the last sessions left off:")
        for day, time, directory, blocks in entries:
            lines.append(f"- {day} {time} in {directory}")
            lines.extend(blocks)

    if project:
        notes = project_notes(project)
        if notes:
            lines.append("")
            lines.append("Newest project notes:")
            lines.extend(notes)

    prs = open_prs(cwd)
    if prs:
        lines.append("")
        lines.append("Your open pull requests here:")
        lines.extend(prs)

    if len(lines) <= 2:
        return

    print("<session-state>")
    print("\n".join(lines))
    print("</session-state>")
    print(
        "Treat the above as a starting point, not as current truth: verify "
        "anything you are about to act on."
    )


if __name__ == "__main__":
    main()
