---
name: commit
description: >
  Create a Git commit from the current changes. TRIGGER when: user says
  "commit", staged or unstaged changes need a commit message. SKIP: user wants
  commit + push + open PR in one shot (use `ship`).
disable-model-invocation: false
allowed-tools: Bash, Read
argument-hint: "[--staged] [linear-issue]"
---

You are committing a set of changes. Follow every step in order.

## Step 1: Parse arguments

Check if `$ARGUMENTS` contains `--staged`. If present, only commit files that
are already staged. Do not stage additional files. Remove `--staged` from the
arguments before continuing (the remaining argument, if any, is the Linear
issue).

## Step 2: Get the changes

Run `git status` to see all changes. Run `git diff` and `git diff --cached` to
understand the staged and unstaged changes.

## Step 3: Stage changes

If `--staged` was passed, skip this step.

Otherwise, stage all relevant files. Do not stage files that contain secrets.

## Step 4: Create the commit

Follow the commit rules from @~/.claude/rules/git.md exactly:

- Subject line: 50 characters or less, capitalized, imperative mood, no period.
- Body (optional): Wrap at 72 characters, explain what and why.
- No co-authored-by or signature lines.

If there is a Linear issue, prefix the subject line with it (e.g.,
`EPD-1337: Fix bug in user login flow`).

When the change set spans multiple unrelated logical changes (per the squashing
rule in rules/git.md), split it into one commit per logical grouping rather
than one grab-bag commit. With `--staged`, splitting the already-staged set is
fine (no new files); a file shared across groups can be staged incrementally by
snapshotting its final version and applying its independent edits in stages.
