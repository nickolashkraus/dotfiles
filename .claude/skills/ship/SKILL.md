---
name: ship
description: >
  Review the diff, create the Git commit, and open a pull request. Combines
  `review-diff` + `commit` + `pr` in one workflow. TRIGGER when: user says
  "ship it", "ship this", "push and open PR", wants the full pipeline. SKIP:
  only one step needed (use `review-diff`, `commit`, or `pr` individually).
disable-model-invocation: false
allowed-tools: Bash, Skill
argument-hint: "[--no-pr] [--worktree] [linear-issue]"
---

You are reviewing, committing, and shipping a set of changes. Follow every
step in order.

Parse `$ARGUMENTS` for flags and a Linear issue slug:

- `--no-pr`: Push straight to the default branch (no new branch, no PR).  Also
  default to this path without the flag when the repo's convention is direct
  commits to the default branch (e.g., `agent-os`, where the entire history is
  direct-to-master and there is no PR workflow).
- `--worktree`: Move the work to a new worktree before reviewing.
- Anything else is treated as a Linear issue slug.

## Step 1: Set up the worktree (only if `--worktree`)

Skip if `--worktree` was not passed.

Move the uncommitted changes into a new worktree so the review, commit, and
PR phases all happen there:

1. Stash all changes including untracked:
   `git stash push --include-untracked`
2. Determine the worktree name (Linear slug if passed, else short descriptive
   name).
3. Create the worktree as a peer directory:
   `git worktree add -b <name> ../<name> HEAD`
4. `cd ../<name>`
5. `git stash pop`

All subsequent steps run in the worktree.

## Step 2: Review

Invoke `Skill(skill: "review-diff")` to review and fix issues in the diff. If
`--no-pr` was passed, pass `--staged` so only the staged subset is reviewed
(the unstaged tail will not ship in this push).

## Step 3: Commit

Invoke `Skill(skill: "commit", args: "<linear-issue>")`, passing the Linear
slug if one was provided. Pass `--staged` if `--no-pr` was passed.

## Step 4: Ship

If `--no-pr` was passed: push to the current branch.

```
git push
```

Stop here.

Otherwise, invoke `Skill(skill: "pr", args: "<linear-issue>")` to create the
branch (if needed), push, and open the pull request. Do NOT pass `--worktree`
to `pr`; the worktree was already set up in Step 1 and the commits already
live there.

Print the pull request URL when `pr` returns.
