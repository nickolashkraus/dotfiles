---
name: pr-window
description: Open a tmux window on a pull request's worktree, with `pr-body --check`, Vim on the pull request diff and a Claude Code session named after the window, so Nickolas can review and hand-edit the change. Takes `v` (the default, stacked on his vertical monitor) or `h` (side by side in the current session)
---

You are opening a tmux window on a pull request's worktree, so the change can
be reviewed and edited by hand instead of through another round of agent
instructions. Follow every step in order.

This runs automatically as the last step of the `pr` skill. Invoke it directly
when a pull request already exists and needs a window, or to reopen one that
was closed.

## Arguments

- **Layout**: `v` or `h`, matching `tmux-layout` in `bash-scripts`. With
  neither, use `v`; on 2026-11-19 Nickolas chose to have every PR window open
  on his left, vertical monitor.
  - **`v`**: In the session his vertical monitor shows, three stacked panes:
    the pull request body on top for his review, the diff in the middle, and
    the Claude Code session that manages the change at the bottom.
  - **`h`**: In the current pane's session, the diff on the left, with the
    body above the Claude Code session on the right.
- **Pull request**: An optional number or URL. Without one, Step 1 reads it
  from the worktree.

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

## Step 2: Resolve the session, never by inference

Do NOT pick a session out of `tmux list-sessions`: more than one session is
usually attached, other agents run in the others, and opening a window in the
wrong one puts the diff in a session he is not looking at. Each layout has one
deterministic source.

- **`h`**: Claude Code runs inside Nickolas's own pane, so the session is
  readable directly:

  ```bash
  tmux display-message -p -t "$TMUX_PANE" '#{session_name}'
  ```

  If `$TMUX_PANE` is unset, there is no pane to anchor to. Say so and stop.
- **`v`**: The session attached to the portrait client. A terminal cell is
  about twice as tall as it is wide, so a portrait monitor's client has more
  than half as many rows as columns (on 2026-11-19, `264x206` on session `2`
  against `474x114` on session `1`):

  ```bash
  tmux list-clients -F '#{client_width} #{client_height} #{session_name}' \
    | awk '$2 * 2 > $1 {print $3}' | sort -u
  ```

  Exactly one name is the session. None means the vertical monitor has no
  client: fall back to `h` in the current pane's session and say so. More than
  one means it is ambiguous: say so and stop.

Do not guess a session, and do not fall back to the first attached one.

## Step 3: Name the window

Use `<repo>#<number>`, for example `sre#1914`, `mjs#126`, `mam#4192`.

| Repo                      | Short      |
| ------------------------- | ---------- |
| `sre-infra-terraform`     | `sre`      |
| `member-journey-services` | `mjs`      |
| `member-app-middleware`   | `mam`      |
| `transaction-service`     | `ts`       |
| `membership-service`      | `ms`       |
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

With `v`, the panes stack top to bottom: `pr-body --check`, Vim on the pull
request diff, then the Claude Code session, sized 15%, 60% and 25% like
`tmux-layout v` (30, 122 and 52 rows on the 206-row monitor). With `h`, Vim
is on the left, `pr-body --check` on the top right and Claude Code on the
bottom right. Either way the window opens on the diff pane, which is split to
make the other two.

If `tmux list-windows -t '<session>:' -F '#{window_index} #{window_name}'`
already shows `<name>`, leave that window alone and report its target.
Re-invoking this skill must never add panes to, or type into,
a window Nickolas has already arranged.

When he asks to close and reopen windows fresh, target every window by its
`#{window_id}` (`@8`), never by index: `renumber-windows` is on, so each
`kill-window` shifts the indices after it. On 2026-11-16 a loop that killed
`1:7` and then `1:8` closed the wrong windows, including one running
a Claude Code session. Kill with `kill-window -t @<id>`, and reopen in place
with `new-window -b -t @<id of the window that followed>`. Stop when a
captured pane ID comes back empty, since `send-keys` and `split-window` with
an empty `-t` act on the caller's own pane.

Open the window, capture its pane ID, and start Vim in it:

```bash
DIFF_PANE=$(tmux new-window -d -P -F '#{pane_id}' \
  -t '<session>:' -c '<worktree>' -n '<name>')
tmux send-keys -t "$DIFF_PANE" "vim \
  -c 'autocmd VimEnter * ++once NERDTree' \
  -c 'autocmd VimEnter * ++once GitGutterToggleDiffBase' \
  -c 'autocmd VimEnter * ++once NERDTreeToggleChangedOnly' \
  $(pr-stat --vim <number>)" Enter
```

The three commands are what `<Leader>hb` and `<Leader>nc` map to in `.vimrc`:
the gutter diffs against the merge base with the default branch, and NERDTree
shows only the files the pull request changes. `pr-stat --vim` (in
`bash-scripts`) adds the `-c` arguments that put the pull request's size at the
far right of Vim's tabline the way GitHub shows it (`+3,984 -26` and five
proportional blocks), on the terminal background, so the window says at a
glance how much there is to review. It is Vim's tabline rather than a tmux pane
border because `pane-border-status` draws a line under its text and leaves a
two-cell stub of it at each end that no option removes. Two details matter:

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
# v: above the diff, 15% of the window
BODY_PANE=$(tmux split-window -v -b -l 15% -d -P -F '#{pane_id}' \
  -t "$DIFF_PANE" -c '<worktree>')
# h: right of the diff
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
- **The split flag follows the layout.** tmux names `-h` "horizontal" after
  the split axis, but it produces a vertical divider with the panes left and
  right, which is what a wide terminal wants. On the vertical monitor the
  width is short and the height is not, so `v` stacks with `-v`, and `-b` puts
  the body above the diff instead of below it.
- **`pr-body` fetches the live body.** It works when reopening a window days
  later, and it shows the body as it stands now rather than as it was first
  written. It opens the body in `$EDITOR`, and on exit runs the spelling and
  fact check, shows the diff, and asks before pushing, so nothing reaches
  GitHub without Nickolas confirming it.

## Step 6: Split a third pane for Claude Code

Split again and start Claude Code named after the window:

```bash
# v: below the diff; 30% of the diff's 85% is 25% of the window
CLAUDE_PANE=$(tmux split-window -v -l 30% -d -P -F '#{pane_id}' \
  -t "$DIFF_PANE" -c '<worktree>')
# h: under the body, leaving the diff at full height
CLAUDE_PANE=$(tmux split-window -v -d -P -F '#{pane_id}' \
  -t "$BODY_PANE" -c '<worktree>')

tmux send-keys -t "$CLAUDE_PANE" "claude -n '<name>'" Enter
```

- **Which pane to split**: With `v`, split the diff, so Claude sits at the
  bottom under it; `-l` takes a share of the pane being split, not of the
  window. With `h`, split the body. `-d` keeps focus on the diff, as in Step 5.
- **The session name is the window name** (`ppp#614`), so `/resume` and the
  session list match the tmux status bar. Quote it; `#` is a comment character
  in a shell with `interactive_comments` set.
- **No `--model`.** The default from `settings.json` applies.
- **Match the account.** If this session's `$CLAUDE_CONFIG_DIR` is
  `~/.claude-fh`, send `claude-fh` instead of `claude`. Both are zsh wrappers
  (an alias and a function), which is why they are typed into the pane's shell
  rather than passed as the split's command.

## Step 7: Report

One or two lines:

- The window target (`2:3 sre#1914`), the layout, and the file or files worth
  editing. With `v`, the target is in the vertical monitor's session, so name
  that session; say so too when `v` fell back to `h`.
- That a plain `git commit` and `git push` updates the pull request, because the
  branch already tracks origin.

Do not re-summarize the change itself. The diff and the body are both on
screen.
