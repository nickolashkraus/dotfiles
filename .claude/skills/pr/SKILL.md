---
name: pr
description: >
  Create a branch and pull request from the current commits. TRIGGER when: user
  has commits ready and wants a branch + push + PR. SKIP: still need to commit
  (use `commit`) or want the full pipeline (use `ship`).
disable-model-invocation: false
allowed-tools: Bash, Read
argument-hint: "[--worktree] [linear-issue]"
---

You are creating a pull request. Follow every step in order.

Parse `$ARGUMENTS` for flags and a Linear issue slug:

- `--worktree`: Create a new worktree instead of switching branches.
- Anything else is treated as a Linear issue slug.

## Step 1: Determine the default branch

```
git remote show origin | grep 'HEAD branch' | awk '{print $NF}'
```

## Step 2: Understand the changes

Run `git log` and `git diff` against the default branch to understand all
commits that will be included in the pull request.

## Step 3: Create the branch and push

If already on a non-default branch, push it. Otherwise:

1. Determine the branch name:
   - If a Linear issue was passed, use it as the branch name (e.g.,
     `EPD-1337`).
   - Otherwise, derive a short descriptive name from the changes.
2. If `--worktree` was set:
   a. Create a worktree at HEAD with the new branch:
      `git worktree add -b <branch> ../<branch> HEAD`
   b. Reset the default branch to match the remote:
      `git reset --hard origin/<default-branch>`
   c. Change to the worktree: `cd ../<branch>`
   All subsequent steps happen in the worktree.
3. Otherwise, create and check out the branch.
4. Push.

## Step 4: Create the pull request

Create the pull request using `gh pr create` against the default branch:

- If a Linear issue was provided, fetch the issue title from Linear and use it
  as the pull request title, prefixed with the issue slug (e.g., `EPD-1337: Add
  Input Validation`). Always prefer the Linear issue title over deriving one
  from the diff.
- Write the description following the pull request rules from
  @~/.claude/rules/git.md:
  - Scale the description with the complexity of the change.
  - Trivial: Single sentence or empty body.
  - Small to medium: Declarative summary, code snippets if helpful,
    `**NOTE**` blocks for secondary context.
  - Large: `## Overview`, then `## Implementation Details`, `## Testing`,
    `## References` as needed.
- Do not add boilerplate sections the change does not warrant.
- If the description has a `## References` block with Linear issues (entries
  like `[BYB-NNNN](...)`), fetch each issue's verbatim title via
  `mcp__linear__get_issue` and use it after the colon. Never paraphrase or
  abbreviate the title; this matches the rule in @~/.claude/rules/git.md and
  avoids a manual round-trip with the user.
- For any non-trivial PR body, write the Markdown to `/tmp/pr-<N>-body.md` (or
  `/tmp/pr-new-body.md` before the number is known) and pass it via `gh pr
  create --body-file`. Do not inline the body via `--body "$(cat <<'EOF' ...
  EOF)"`; defensive escapes inside an inline heredoc tend to leak through as
  literal backticks and dollars.

Print the pull request URL when done.
