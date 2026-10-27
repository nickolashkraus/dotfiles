---
name: pr-window
description: Open a tmux window on a pull request's worktree, with Vim on the pull request diff and `pr-body --check` beside it, so Nickolas can review and hand-edit the change
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

## Step 4: Open the window with Vim on the diff

The layout is Vim on the pull request diff on the left and `pr-body --check`
on the right.

If `tmux list-windows -t '<session>:' -F '#{window_index} #{window_name}'`
already shows `<name>`, leave that window alone and report its target.
Re-invoking this skill must never add panes to, or type into,
a window Nickolas has already arranged.

Open the window, capture its pane ID, and start Vim in it:

```bash
DIFF_PANE=$(tmux new-window -d -P -F '#{pane_id}' \
  -t '<session>:' -c '<worktree>' -n '<name>')
tmux send-keys -t "$DIFF_PANE" "vim \
  -c 'autocmd VimEnter * ++once NERDTree' \
  -c 'autocmd VimEnter * ++once GitGutterToggleDiffBase' \
  -c 'autocmd VimEnter * ++once NERDTreeToggleChangedOnly'" Enter
```

The three commands are what `<Leader>hb` and `<Leader>nc` map to in `.vimrc`:
the gutter diffs against the merge base with the default branch, and NERDTree
shows only the files the pull request changes. Two details matter:

- **The commands run on `VimEnter`, not directly from `-c`.** Vim runs `-c`
  before `VimEnter`, and `.vimrc` registers the changed-files filter on
  `VimEnter`, so a bare `-c NERDTreeToggleChangedOnly` renders the full tree.
- **`NERDTree` opens first.** `GitGutterToggleDiffBase` refreshes the tree
  root, so the tree has to exist when it runs.

Vim is sent to the shell rather than passed as the window's command, so
quitting Vim leaves a shell in the worktree instead of closing the pane.

Target the **session**, with a trailing colon. `-t 1` is parsed as window index
1 and fails with `create window failed: index 1 in use`; `-t '1:'` means "that
session, next free index".

Do not take focus. `-d` opens the window in the background and Nickolas's
cursor stays where it is. He decides when to switch to it; a window that grabs
focus interrupts whatever he was reading. Report the target so he can jump to
it himself.

## Step 5: Split a second pane for the pull request body

Split from the captured pane ID and send to the new one, never to a guessed
pane index:

```bash
BODY_PANE=$(tmux split-window -h -d -P -F '#{pane_id}' \
  -t "$DIFF_PANE" -c '<worktree>')
tmux send-keys -t "$BODY_PANE" 'pr-body --check <number>' Enter
```

**Never target `<name>.1`.** Pane indices are positional, so `.1` is only the
new pane when the window had exactly one. On a window Nickolas has already
split himself, `.1` is one of *his* panes, and `send-keys` types the command
straight into whatever is running there. It did exactly that once, into a vim
buffer in INSERT mode, mangling two lines of an unsaved PR-body draft.
`#{pane_id}` (`%7`-style) is stable and unambiguous.

Three further details that matter:

- **`-d` is correct here too.** Without it the new pane takes focus and the
  window opens on the body instead of the diff. The diff is the thing being
  reviewed, so it stays the active pane within the window.
- **`-h` is the side-by-side split.** tmux names it "horizontal" after the
  split axis, but it produces a vertical divider with the panes left and
  right, which is what a wide terminal wants. `-v` stacks them and halves the
  diff's height for no gain.
- **`pr-body` fetches the live body.** It works when reopening a window days
  later, and it shows the body as it stands now rather than as it was first
  written. It opens the body in `$EDITOR`, and on exit runs the spelling and
  fact check, shows the diff, and asks before pushing, so nothing reaches
  GitHub without Nickolas confirming it.

## Step 6: Report

One or two lines:

- The window target (`1:2 sre#1914`) and the file or files worth editing.
- That a plain `git commit` and `git push` updates the pull request, because the
  branch already tracks origin.

Do not re-summarize the change itself. The diff and the body are both on
screen.
