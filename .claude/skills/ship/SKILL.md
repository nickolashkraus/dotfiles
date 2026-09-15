---
name: ship
description: >
  Review the diff, create the Git commit, and open a pull request. Combines
  `review-diff` + `commit` + `pr` in one workflow. TRIGGER when: user says
  "ship it", "ship this", "push and open PR", wants the full pipeline. SKIP:
  only one step needed (use `review-diff`, `commit`, or `pr` individually).
disable-model-invocation: false
allowed-tools: Bash, Skill
argument-hint: "[--no-pr] [--no-pulse] [--worktree] [linear-issue]"
---

You are reviewing, committing, and shipping a set of changes. Follow every
step in order.

Parse `$ARGUMENTS` for flags and a Linear issue slug:

- `--no-pr`: Push straight to the default branch (no new branch, no PR).  Also
  default to this path without the flag when the repo's convention is direct
  commits to the default branch (e.g., `agent-os`, where the entire history is
  direct-to-master and there is no PR workflow).
- `--no-pulse`: Skip the local Pulse gate (passed through to `pr` in Step 4).
  The `fh-pulse` bot still reviews the PR after push.
- `--worktree`: Move the work to a new worktree before reviewing.
- Anything else is treated as a Linear issue slug.

## Step 1: Set up the worktree (only if `--worktree`)

Skip if `--worktree` was not passed.

Move the uncommitted changes into a new worktree so the review, commit, and
PR phases all happen there:

1. Stash all changes including untracked:
   `git stash push --include-untracked`
2. Determine the worktree name. If a Linear issue was passed, use the lowercase
   slug plus a short hyphenated description (e.g., `epd-1337-require-ssl`), not
   the bare slug. Otherwise, use a short descriptive name.
3. Create the worktree as a peer directory:
   `git worktree add -b <name> ../<name> HEAD`
4. `cd ../<name>`
5. `git stash pop`

All subsequent steps run in the worktree.

## Step 2: Review

Invoke `Skill(skill: "review-diff")` to review and fix issues in the diff. If
`--no-pr` was passed, pass `--staged` so only the staged subset is reviewed
(the unstaged tail will not ship in this push). If nothing is staged, the
whole working tree is the ship set: review and commit all of it.

## Step 3: Commit

Invoke `Skill(skill: "commit", args: "<linear-issue>")`, passing the Linear
slug if one was provided. Pass `--staged` if `--no-pr` was passed.

Skip this step if the working tree is already clean because the changes were
committed before `ship` was invoked; the review in Step 2 still runs against
the committed diff.

## Step 4: Ship

If `--no-pr` was passed: push to the current branch.

```
git push
```

If the push is rejected because the remote moved, fetch and rebase onto the
remote branch (never merge), resolve any conflicts, then push again.

Stop here.

Otherwise, invoke `Skill(skill: "pr", args: "<linear-issue>")` to create the
branch (if needed), push, and open the pull request. If `--no-pulse` was
passed, include it in the `pr` args (e.g., `"--no-pulse <linear-issue>"`) so
the local Pulse gate is skipped there too. Do NOT pass `--worktree` to `pr`;
the worktree was already set up in Step 1 and the commits already live there.

Print the pull request URL when `pr` returns.

## Final report

One to three lines: the pushed SHA or PR URL, plus anything that deviated
(rebase, review fix). No step-by-step recap.
