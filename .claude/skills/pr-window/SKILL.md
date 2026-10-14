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

Leave the pane as a plain interactive shell in the worktree. **Do not run
`git diff`, or any other command, in it.** Nickolas reads the diff in his own
editor, and a pager sitting in the pane means he has to dismiss it before the
shell is usable.

One thing not to do:

- Do not take focus. Pass `-d` so the window opens in the background and
  Nickolas's cursor stays where it is. He decides when to switch to it; a
  window that grabs focus interrupts whatever he was reading. Report the
  target so he can jump to it himself.

## Step 5: Split a second pane for the pull request body

The layout is the worktree on the left and the pull request body on the right.
The body is the one thing worth having on screen that is not already in his
editor.

Capture the new pane's ID from the split and send to that, never to a guessed
pane index:

```bash
BODY_PANE=$(tmux split-window -h -d -P -F '#{pane_id}' \
  -t '<session>:<name>' -c '<worktree>')
tmux send-keys -t "$BODY_PANE" \
  'gh pr view --json body --jq .body | bat --language md --style plain' Enter
```

**Never target `<name>.1`.** Pane indices are positional, so `.1` is only the
new pane when the window had exactly one. Re-invoking this skill on a window
Nickolas has already split himself makes `.1` one of *his* panes, and
`send-keys` types the command straight into whatever is running there. It did
exactly that once, into a vim buffer in INSERT mode, mangling two lines of an
unsaved PR-body draft. `#{pane_id}` (`%7`-style) is stable and unambiguous.

For the same reason, check the pane count before splitting:

```bash
tmux list-panes -t '<session>:<name>' -F '#{pane_index} #{pane_current_command}'
```

More than one pane means the window is already laid out. Leave it alone and
say so rather than adding a pane to someone else's arrangement.

Three further details that matter:

- **`-d` is correct here too.** Without it the new pane takes focus and the
  window opens on the body instead of the diff. The diff is the thing being
  reviewed, so it stays the active pane within the window.
- **`-h` is the side-by-side split.** tmux names it "horizontal" after the
  split axis, but it produces a vertical divider with the panes left and
  right, which is what a wide terminal wants. `-v` stacks them and halves the
  diff's height for no gain.
- **Read the body from `gh`, not from `/tmp/pr-<N>-body.md`.** The temp file
  exists only when this session just created the pull request; `gh` also works
  when reopening a window days later, and it shows the body as it stands now
  rather than as it was first written.

Pass `--jq .body` unquoted so the string survives `send-keys` without nested
quoting. If `bat` is not installed, `less` is the fallback; do not silently
drop the pager, since a long body scrolls off the top.

## Step 6: Report

One or two lines:

- The window target (`1:2 sre#1914`) and the file or files worth editing.
- That a plain `git commit` and `git push` updates the pull request, because the
  branch already tracks origin.

Do not re-summarize the change itself. The diff and the body are both on
screen.
