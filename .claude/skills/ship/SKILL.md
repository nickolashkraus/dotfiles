---
name: ship
description: >
  Reviews the diff, creates the Git commit, and opens a pull request.
disable-model-invocation: false
allowed-tools: Bash, Edit, Glob, Grep, Read
argument-hint: [--no-pr] [--worktree] [linear-issue]
---

You are reviewing, committing, and shipping a set of changes. Follow every step
in order.

Parse `$ARGUMENTS` for flags and a Linear issue slug:

- `--no-pr`: Push straight to the default branch (no new branch, no PR).
- `--worktree`: Create a new worktree instead of switching branches.
- Anything else is treated as a Linear issue slug.

## Step 1: Determine the default branch

```
git remote show origin | grep 'HEAD branch' | awk '{print $NF}'
```

## Step 2: Get the diff

Diff all changes (staged, unstaged, and untracked) against the default branch.

If there are untracked files, read them in full. You need complete context to
review.

## Step 3: Review the diff

Go through every changed file. For each file, check for:

- **Typos**: Misspelled words, wrong variable names, copy/paste errors.
- **Bugs**: Logic errors, off-by-one mistakes, null/undefined risks, missing
  error handling, race conditions, resource leaks.
- **Inconsistencies**: Naming conventions that break from the rest of the file,
  mismatched types, formatting that diverges from surrounding code.
- **Security**: Injection risks, hardcoded secrets, overly broad permissions.

Read surrounding context in each file when needed to understand intent.

If you find issues, fix them directly. Do not just list them.

After fixing, re-run the diff to confirm your fixes are correct.

If the diff is clean, say so and move on.

If the project has CI (workflows, pre-commit, scripts in `package.json` /
`pyproject.toml` / `Makefile`), run the relevant commands locally to ensure
the changes will pass.

## Step 4: Create the branch (skip if `--no-pr`)

If already on a non-default branch, skip this step. Otherwise:

1. Determine the branch name:
   - If a Linear issue was passed, use it as the branch name (e.g.,
     `EPD-1337`).
   - Otherwise, derive a short descriptive name from the changes.
2. If `--worktree` was set:
   a. Stash all changes including untracked files:
      `git stash push --include-untracked`
   b. Create a worktree as a peer directory with the new branch:
      `git worktree add -b <branch> ../<branch> HEAD`
   c. Change to the worktree: `cd ../<branch>`
   d. Pop the stash: `git stash pop`
   All subsequent steps happen in the worktree.
3. Otherwise, create and check out the branch.

## Step 5: Create the commit

Follow the commit rules from @~/.claude/rules/git.md exactly:

- Subject line: 50 characters or less, capitalized, imperative mood, no period.
- Body (optional): Wrap at 72 characters, explain what and why.
- No co-authored-by or signature lines.

Stage all relevant changes and commit. Do not stage files that contain
secrets.

If there is a Linear issue, prefix the subject line with it (e.g.,
`EPD-1337: Fix bug in user login flow`).

If a pre-commit hook or user reformats files (the commit succeeds but `git
status` shows new staged changes from the formatter), fold them into the
original commit with `git reset --soft HEAD~1 && git commit -C ORIG_HEAD`. This
keeps a single clean commit without using `--amend`.

## Step 6: Push

```
git push -u origin <current-branch>
```

## Step 7: Create the pull request (skip if `--no-pr`)

Create the pull request using `gh pr create` against the default branch:

- If a Linear issue was provided, prefix the pull request title (e.g.,
  `EPD-1337: Add input validation`).
- Write the description following the pull request rules from
  @~/.claude/rules/git.md:
  - Scale the description with the complexity of the change.
  - Trivial: Single sentence or empty body.
  - Small to medium: Declarative summary, code snippets if helpful,
    `**NOTE**` blocks for secondary context. Use a bulleted list when
    the commit contains multiple logical changes.
  - Large: `## Overview`, then `## Implementation Details`, `## Testing`,
    `## References` as needed.
- Do not add boilerplate sections the change does not warrant.

Print the pull request URL when done.

@~/.claude/rules/meta-learning.md
