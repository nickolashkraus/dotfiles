---
name: claude-resurrect
description: >
  Retrieve the day's interactive Claude Code sessions (custom name, directory,
  session ID, first prompt) and emit a resume table plus a tmux rebuild script.
  TRIGGER when: user says "claude-resurrect", "resurrect", "my sessions
  crashed", "tmux crashed", "retrieve my Claude sessions", "which sessions did
  I have open", or wants to rebuild their session layout after a crash.
disable-model-invocation: false
allowed-tools: Bash
argument-hint: "[today|yesterday|YYYY-MM-DD]"
---

Rebuild the user's Claude Code session layout after a crash (tmux, terminal, or
reboot). Recovers every real interactive session for a date, with the custom
window name, working directory, and a ready-to-run resume command.

## Step 1: Run the collector

Pass the date argument through verbatim (default is today, local time):

```bash
python3 ~/.claude/skills/claude-resurrect/resurrect.py "$ARGUMENTS"
```

If `$ARGUMENTS` is empty, run it with no argument. Accepts `today`,
`yesterday`, or an ISO `YYYY-MM-DD`.

## What the collector does

- Scans `~/.claude/projects/*/*.jsonl` (top-level sessions only; nested
  `*/subagents/*` transcripts are excluded by the glob).
- Keeps a session only if it has at least one genuine user turn on the target
  date. This is the key filter: hook-spawned subsessions (`rule-check`,
  `lint-outbound`) and skill-runner-only transcripts have zero genuine turns
  and are dropped, so the result is the windows the user actually drove.
- Reads each session's `customTitle` (the tmux window name the user set), the
  cwd, the first genuine prompt, and the local first/last activity time.
- Groups by directory and writes a tmux rebuild script to
  `/tmp/claude-resurrect-<date>.sh`.

## Step 2: Report

Present the sessions as a single Markdown table, most useful columns first:
Name, Directory (`~`-relative), Session ID, and a one-line summary derived from
the first prompt. Group-by-directory in prose is fine, but lead with the table.

Call out two things when present:

- **The current session**: The session ID matching this run is live, not dead.
  Do not tell the user to resume it.
- **Dead `/loop` sessions**: A session named `loop` (or whose first prompt
  starts with `# /loop`) was a running loop that died with the crash. Nothing
  is watching whatever it watched until re-armed. Flag it explicitly.

## Step 3: Offer the rebuild

The collector already wrote the tmux script and printed its path. The script
stages `claude --resume <id>` in each window WITHOUT pressing Enter, so the
user reviews before launching. Offer to run it (`bash
/tmp/claude-resurrect-<date>.sh`), but do not run it unprompted: it spawns
a new tmux session and one Claude process per window.

## Notes

- The custom name comes from `customTitle`; untitled sessions render as
  `(untitled)`. Duplicate names are allowed (e.g., two `ppp` windows);
  disambiguate them by their first prompt in the summary.
- Times are local. Date matching is by local date, so a session that ran past
  midnight appears under each date it touched.
