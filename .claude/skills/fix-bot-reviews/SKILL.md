---
name: fix-bot-reviews
description: >
  Fixes bot review comments on a PR by creating a worktree, applying fixes, and
  opening a stacked fix PR.
disable-model-invocation: false
allowed-tools: Bash, Edit, Glob, Grep, Read
argument-hint: [pr-number]
---

You are fixing bot review comments on a pull request. The fixes are applied in
a new worktree and shipped as a stacked PR based on the original branch. Follow
every step in order.

## Step 1: Determine the pull request

If a PR number was passed (`$ARGUMENTS`), use it. Otherwise, detect the current
branch and find its open PR:

```
gh pr view --json number,headRefName,baseRefName \
  --jq '{number, headRefName, baseRefName}'
```

If no PR is found, stop and tell the user.

Save the PR number, head branch name, and base branch name for later steps.
Also determine the `{owner}/{repo}` from the remote:

```
gh repo view --json nameWithOwner --jq '.nameWithOwner'
```

## Step 2: Fetch bot comments

Collect bot comments from **both** sources:

1. **PR review comments** (inline comments on diffs):

   ```
   gh api repos/{owner}/{repo}/pulls/<pr-number>/comments --paginate
   ```

2. **Review-level comments** (comments attached to reviews): List all reviews,
   filter for bot authors, then fetch each review's comments:

   ```
   gh api repos/{owner}/{repo}/pulls/<pr-number>/reviews --paginate \
     --jq '.[] | select(
       .user.login == "sentry[bot]" or
       .user.login == "cursor[bot]" or
       .user.login == "copilot[bot]" or
       .user.type == "Bot"
     ) | .id'
   ```

   Then for each review ID:

   ```
   gh api repos/{owner}/{repo}/pulls/<pr-number>/reviews/<review-id>/comments
   ```

Filter for comments left by review bots (Copilot, Cursor Bugbot, Sentry, or
similar).

### Skip comments that are already resolved

For each bot comment, check whether:

- The comment thread is already resolved.
- The user (username: `nickolashkraus`) has already replied. Check the
  comment's reply thread for any comment where
  `.user.login == "nickolashkraus"`.

**Skip** any comment that is resolved or already has a reply from
`nickolashkraus`. Only act on unresolved comments with no reply.

If no actionable bot comments remain, stop and tell the user.

## Step 3: Create the worktree

Create a new worktree from the PR's head branch as a peer directory with a new
fix branch:

```
git worktree add -b <head-branch>-bot-fixes \
  ../<head-branch>-bot-fixes <head-branch>
```

All subsequent work (file reads, edits, CI commands) happens in the worktree
directory (`../<head-branch>-bot-fixes`).

## Step 4: Fix bot comments

For each unresolved bot comment, assess whether it is legitimate.

**Bias toward fixing.** If the suggestion is plausible, fix it. Only dismiss a
comment if it is clearly wrong:

- The bot misread the code or misunderstood the logic.
- The suggestion would break existing behavior.
- The suggestion contradicts project conventions.

For each comment:

- **Legitimate issue** (default): Read the relevant source files in the
  worktree to understand context, then apply the fix directly.
- **Clearly illegitimate**: Reply with a brief explanation of why the
  suggestion does not apply:

  ```
  gh api repos/{owner}/{repo}/pulls/<pr-number>/comments \
    -f body='<reply>' -F in_reply_to=<comment-id>
  ```

## Step 5: Run CI locally

Run the project's test/lint/build commands in the worktree to verify the fixes.
Use the project configuration (e.g., `Makefile`, `package.json`,
`pyproject.toml`) to identify the correct commands.

If any command fails, fix the issue and re-run until all checks pass locally.

## Step 6: Commit and push

Commit all fixes in the worktree. Follow the commit rules from
@~/.claude/rules/git.md:

- Subject line: 50 characters or less, capitalized, imperative mood, no
  period.
- Body: Explain what bot comments were addressed and why.
- No co-authored-by or signature lines.

Push the fix branch:

```
git push -u origin <head-branch>-bot-fixes
```

## Step 7: Create the fix PR

Create a pull request with the **original PR's head branch** as the base:

```
gh pr create --base <head-branch> --head <head-branch>-bot-fixes \
  --title "..." --body "..."
```

Write the PR description following @~/.claude/rules/git.md. Include a summary
of which bot comments were fixed and which were dismissed (with reasons).

Print the fix PR URL.

## Step 8: Delegate to `/fix-ci`

Run `/fix-ci <new-pr-number>` on the fix PR to handle any CI failures and new
bot comments that appear. `/fix-ci` runs in-place on the fix branch (no
additional PRs are created).

## Step 9: Summarize

List each bot comment and what you did: fixed, dismissed (with reason), or
skipped (already resolved/replied).
