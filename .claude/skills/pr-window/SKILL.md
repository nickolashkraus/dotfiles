---
name: pr-window
description: Open a tmux window on a pull request's worktree so Nickolas can review and hand-edit the change
---

You are opening a tmux window on a pull request's worktree, so the change can
be reviewed and edited by hand instead of through another round of agent
instructions. Follow every step in order.

This runs automatically as the last step of the `pr` skill. Invoke it directly
when a pull request already exists and needs a window, or to reopen one that
was closed.

## Preconditions

Both must hold before a window opens. If either fails, say which and stop.

- **Local CI has passed.** The repo's full lint, type-check, and test commands
  ran and are green, per @~/.claude/rules/git.md. The window is for reviewing a
  change that is already known to build, not for finding out whether it does.
- **The pull request exists.** Never open a window on a branch that has no pull
  request yet. There is nothing to review against, and the window would be
  named after a branch whose number does not exist.

Neither is this skill's job to perform: `ship` and `pr` own running CI and
creating the pull request. This skill only refuses to run before they have.

## Step 1: Resolve the worktree and the pull request

- **Worktree**: The directory the pull request's branch is checked out in.
  Default to the current working directory, resolved with `git rev-parse
  --show-toplevel`. Never target a bare repo root; in a bare-plus-worktrees
  layout that directory has no checkout to edit.
- **Pull request**: From that directory, read what the window needs:

  ```bash
  gh pr view --json number,baseRefName,headRefName,url \
    --jq '{n:.number, base:.baseRefName, head:.headRefName, url:.url}'
  ```

  An empty result means there is no pull request. Stop; see Preconditions.

## Step 2: Resolve the session from the current pane, never by inference

Claude Code runs inside Nickolas's own pane, so the session is readable
directly:

```bash
tmux display-message -p -t "$TMUX_PANE" '#{session_name}'
```

Use that value. Do NOT pick a session out of `tmux list-sessions`: more than
one session is usually attached, other agents run in the others, and opening a
window in the wrong one puts the diff in a session he is not looking at.

If `$TMUX_PANE` is unset, there is no pane to anchor to. Say so and stop. Do
not guess a session, and do not fall back to the first attached one.

## Step 3: Name the window

Use `<repo>#<number>`, for example `sre#1914`, `mjs#126`, `mam#4192`.

| Repo                      | Short      |
| ------------------------- | ---------- |
| `sre-infra-terraform`     | `sre`      |
| `member-journey-services` | `mjs`      |
| `member-app-middleware`   | `mam`      |
| `transaction-service`     | `ts`       |
| `membership-service`      | `memb`     |
| `ppp-service`             | `ppp`      |
| `enterprise-service`      | `ent`      |
| `admin-app-fe-next`       | `admin`    |
| `frontend-mono`           | `fe`       |
| `agent-os`                | `agent-os` |

For a repo not listed, use the initials of the hyphenated segments
(`member-data-platform` becomes `mdp`). Add a row here when a repo starts
coming up often enough that its initials read badly.

Keep the name short, under about 12 characters. tmux truncates names in the
status bar, and the worktree path is already visible in the pane's prompt, so
the name only has to be unique and recognizable at a glance, not descriptive.

## Step 4: Open the window

```bash
tmux new-window -t '<session>:' -c '<worktree>' -n '<name>'
```

Target the **session**, with a trailing colon. `-t 1` is parsed as window index
1 and fails with `create window failed: index 1 in use`; `-t '1:'` means "that
session, next free index".

Then show the diff and leave an interactive shell behind it:

```bash
tmux send-keys -t '<session>:<name>' 'git diff origin/<base>' Enter
```

Take `<base>` from `baseRefName` in Step 1 rather than assuming `main`; some
repos are on `master`.

Two things not to do:

- Do not pass the diff as the window's command (`tmux new-window ... 'git diff
  ...'`). The window closes as soon as the pager exits.
- Do not pass `-d`. The window should be active, since the point is to review
  the change now.

## Step 5: Report

One or two lines:

- The window target (`1:2 sre#1914`) and the file or files worth editing.
- That a plain `git commit` and `git push` updates the pull request, because the
  branch already tracks origin.

Do not re-summarize the change itself. The diff is on screen.
