---
name: fix-bot-reviews
description: >
  Fixes bot review comments on a PR by creating a worktree, applying fixes, and
  opening a stacked fix PR.
disable-model-invocation: false
allowed-tools: Bash, Edit, Glob, Grep, Read
argument-hint: [--re-review] [pr-number]
---

You are fixing bot review comments on a pull request. The fixes are applied in
a new worktree and shipped as a stacked PR based on the original branch. Follow
every step in order.

## Step 1: Determine the pull request

Parse `$ARGUMENTS` for the `--re-review` flag and an optional PR number. The
`--re-review` flag means all bot comments should be re-reviewed, even those
already resolved or replied to. Remove the flag before continuing.

If a PR number was provided, use it. Otherwise, detect the current branch and
find its open PR:

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

**If `--re-review` was set, skip this subsection entirely.** Act on all bot
comments regardless of resolution or reply status.

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
git worktree add -b <head-branch>-fixes-<number> \
  ../<head-branch>-fixes-<number> <head-branch>
```

All subsequent work (file reads, edits, CI commands) happens in the worktree
directory (`../<head-branch>-fixes-<number>`).

## Step 4: Fix bot comments

For each unresolved bot comment, assess whether it is legitimate.

**Bias toward fixing.** If the suggestion is plausible, fix it. Only dismiss
a comment if it is clearly wrong:

- The bot misread the code or misunderstood the logic.
- The suggestion would break existing behavior.
- The suggestion contradicts project conventions.
- The suggestion contradicts the product or feature specification.

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

- Subject line: 50 characters or less, capitalized, imperative mood, no period.
- Body: Explain what bot comments were addressed and why.
- No co-authored-by or signature lines.

Push the fix branch:

```
git push -u origin <head-branch>-fixes-<number>
```

## Step 7: Create the fix PR

Create a pull request with the **original PR's head branch** as the base:

```
gh pr create --base <head-branch> --head <head-branch>-fixes-<number> \
  --title "..." --body "..."
```

Write the PR description following @~/.claude/rules/git.md. Include a summary
of which bot comments were fixed and which were dismissed (with reasons).

Print the fix PR URL.

## Step 8: Delegate to `/fix-ci`

Run `/fix-ci --in-place <new-pr-number>` on the fix PR to handle any CI
failures and new bot comments that appear. The `--in-place` flag ensures
`/fix-ci` fixes bot comments directly on the fix branch instead of delegating
back to `/fix-bot-reviews` (which would cause infinite recursion).

## Step 9: Summarize

List each bot comment and what you did: fixed, dismissed (with reason), or
skipped (already resolved/replied).

If any bot comments were addressed (fixed or dismissed), post a summary comment
on the fix PR using tables. Number findings sequentially (F-01, F-02, ... for
fixed; D-01, D-02, ... for dismissed). Use each bot comment's `html_url` for
the link column.

```
gh pr comment <fix-pr-number> --body "$(cat <<'EOF'
## Bot Review Findings

### Fixed

| #    | Comment            | Description   | Fix      |
| ---- | ------------------ | ------------- | -------- |
| F-01 | [→](<comment-url>) | <description> | <commit> |
| F-02 | [→](<comment-url>) | <description> | <commit> |

### Dismissed

| #    | Comment            | Description   | Reason   |
| ---- | ------------------ | ------------- | -------- |
| D-01 | [→](<comment-url>) | <description> | <reason> |
| D-02 | [→](<comment-url>) | <description> | <reason> |
EOF
)"
```

Omit a section if it has no entries. If there are zero findings (nothing fixed
or dismissed), post:

```
gh pr comment <fix-pr-number> --body '## Bot Review Findings

✅ No actionable findings.'
```

This summary is in addition to the individual replies already posted on each
bot comment thread.
