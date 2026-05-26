---
name: fix-bot-reviews
description: >
  Fix bot review comments on a pull request by creating a worktree, applying
  fixes, and opening a stacked fix PR. TRIGGER when: PR has unresolved
  CodeRabbit / Cursor / Sentry / Copilot / Seer bot review comments to address.
  SKIP: failing CI checks (use `fix-ci`) or release PR (use `fix-ci-release`).
disable-model-invocation: false
allowed-tools: Bash, Edit, Glob, Grep, Read, Skill
argument-hint: "[--re-review [all | unresolved]] [pr-number]"
---

You are fixing bot review comments on a pull request as a stacked worktree
PR. Fixes are applied in a new worktree and shipped as a stacked PR based on
the original branch. Follow every step in order.

Shared procedures (PR resolution, bot comment fetch and filter, dismissal
criteria, reply format, durable link format, summary tables) are loaded
from:

@~/.claude/skills/fix-ci-core/PROCEDURES.md

## Step 1: Parse arguments and resolve the PR

Parse `$ARGUMENTS` for the `--re-review [all | unresolved]` flag (see
"Filter bot comments by resolution status" in PROCEDURES.md). Remove the
flag and its value before continuing.

Then follow "Resolve the pull request" in PROCEDURES.md. Save the PR number,
head branch name, base branch name, title, and extracted issue slug for
later steps. The slug is used in Step 7 for the fix PR title.

## Step 2: Fetch bot comments

Follow "Collect bot comments" and "Filter bot comments by resolution status"
in PROCEDURES.md.

If no actionable bot comments remain, stop and tell the user.

## Step 3: Create the worktree

Create a new worktree from the PR's head branch as a peer directory with
a new fix branch:

```
git worktree add -b <head-branch>-fixes-<number> \
  ../<head-branch>-fixes-<number> <head-branch>
```

All subsequent work (file reads, edits, CI commands) happens in the worktree
directory (`../<head-branch>-fixes-<number>`).

## Step 4: Fix bot comments

For each unresolved bot comment, apply "Bias toward fixing" in PROCEDURES.md.

For legitimate findings: Read the relevant source files in the worktree to
understand context, then apply the fix directly.

For dismissals: Follow "Reply to a bot comment" in PROCEDURES.md.

## Step 5: Run CI locally

Run the project's test/lint/build commands in the worktree to verify the
fixes. Use the project configuration (e.g., `Makefile`, `package.json`,
`pyproject.toml`) to identify the correct commands.

If any command fails, fix the issue and re-run until all checks pass
locally.

## Step 6: Commit and push

Commit all fixes in the worktree per @~/.claude/rules/git.md. The body
should explain which bot comments were addressed and why.

Push the fix branch:

```
git push -u origin <head-branch>-fixes-<number>
```

## Step 7: Create the fix PR

Create a pull request with the **original PR's head branch** as the base:

```
gh pr create --base <head-branch> --head <head-branch>-fixes-<number> \
  --title "<issue-slug>: Address bot review findings" --body "..."
```

The PR title must use the format `<issue-slug>: Address bot review
findings`, where `<issue-slug>` is extracted from the parent PR's title
(e.g., if the parent title is `BYB-1120: Handle missing statuses`, the slug
is `BYB-1120`). If the parent PR title has no issue slug prefix, use
`Address bot review findings` as the full title.

Write the PR description following @~/.claude/rules/git.md. Include a
summary of which bot comments were fixed and which were dismissed (with
reasons).

Print the fix PR URL.

## Step 8: Hand off to `fix-ci`

Invoke `Skill(skill: "fix-ci", args: "--in-place <new-pr-number>")` on the
fix PR to handle any CI failures and new bot comments that appear. The
`--in-place` flag ensures `fix-ci` fixes bot comments directly on the fix
branch instead of recursing back into `fix-bot-reviews`.

## Step 9: Summarize

List each bot comment and what you did: fixed, dismissed (with reason), or
skipped (already resolved/replied).

Post a summary comment on the fix PR. Follow "Findings summary" in
PROCEDURES.md and use the "Canonical Fixed/Dismissed template" from that
section.
