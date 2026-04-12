---
name: fix-ci
description: >
  Fixes CI failures on a pull request by fetching check results, diagnosing the
  issues, and applying fixes.
disable-model-invocation: false
allowed-tools: Bash, Edit, Glob, Grep, Read
argument-hint: [--in-place] [--re-review] [pr-number]
---

You are fixing CI failures on a pull request. Follow every step in order.

## Step 1: Determine the pull request

Parse `$ARGUMENTS` for flags and an optional PR number:

- `--in-place`: Fix bot comments directly on this branch (no stacked PR).
- `--re-review`: Re-review all bot comments, even those already resolved or
  replied to.

Remove both flags before continuing.

If a PR number was passed, use it. Otherwise, detect the current branch and
find its open PR:

```
gh pr view --json number,headRefName --jq '.number'
```

If no PR is found, stop and tell the user.

## Step 2: Wait for all checks to complete

List all checks on the PR:

```
gh pr checks <pr-number>
```

Classify every check as **pass**, **fail**, or **pending**.

- If any checks are pending, wait 30 seconds and re-check. Always wait for
  **all** checks to complete before moving on, even external checks (e.g.,
  Cloud Build, Sentry, third-party scanners).
- Once all checks have completed, continue to Step 3.

## Step 3: Assess results

- If any checks have failed, continue to Step 4.
- If all checks pass, skip to Step 5 to assess bot comments.

**IMPORTANT**: Never create an empty commit to "Retry CI". Instead, read the
logs to diagnose the failure and, if the failure is transient or
infrastructure-related, re-run the specific check:

```
gh run rerun <run-id> --failed
```

## Step 4: Get failure details and fix

For each failed check, fetch its logs:

```
gh run view <run-id> --log-failed
```

If the log is too large, fetch logs for the specific failed job:

```
gh run view <run-id> --log-failed --job <job-id>
```

Read the logs carefully. Identify the root cause of each failure (e.g., lint
error, type error, test failure, formatting issue).

For each failure:

1. Read the relevant source files to understand context.
2. Apply the fix directly. Do not just describe what needs to change.
3. If the fix requires running a command (e.g., `npm run format`, `ruff .`),
   run it.

## Step 5: Assess review bot comments

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
`nickolashkraus`. Only act on unresolved comments with no reply from the
user.

If no actionable bot comments remain and all checks pass, go to Step 7.

### If `--in-place` was NOT set

If there are actionable bot comments and `--in-place` was not passed, delegate
to `/fix-bot-reviews <pr-number>` (include `--re-review` if it was set). This
creates a stacked fix PR for the bot comment fixes. Skip to Step 7 after
`/fix-bot-reviews` completes.

### If `--in-place` was set

For each remaining unresolved comment, assess whether it is legitimate and fix
in-place on the current branch.

**Bias toward fixing.** If the suggestion is plausible, fix it. Only dismiss
a comment if it is clearly wrong:

- The bot misread the code or misunderstood the logic.
- The suggestion would break existing behavior.
- The suggestion contradicts project conventions.
- The suggestion contradicts the product or feature specification.

For each comment:

- **Legitimate issue** (default): Read the relevant source files to understand
  context, then apply the fix directly.
- **Clearly illegitimate**: Reply with a brief explanation of why the
  suggestion does not apply:

  ```
  gh api repos/{owner}/{repo}/pulls/<pr-number>/comments \
    -f body='<reply>' -F in_reply_to=<comment-id>
  ```

## Step 6: Verify, commit, and push

Run the same CI commands locally to confirm the fixes work. Use the project's
test/lint/build commands as identified from the CI logs or project
configuration (e.g., `Makefile`, `package.json`, `pyproject.toml`).

If any command still fails, go back to Step 4. Do not push between fix
iterations.

Once **all** local verification passes (CI fixes and bot comment fixes), commit
and push in a single push. Then go back to Step 2 and wait for all checks to
complete before taking further action. Keep iterating until every check passes
and all bot comments are addressed.

Follow the commit rules from @~/.claude/rules/git.md:

- Subject line: 50 characters or less, capitalized, imperative mood, no period.
- Body: Explain what bot comments were addressed and why.
- No co-authored-by or signature lines.

## Step 7: Summarize

List each CI failure and review bot comment, and what you did to fix or resolve
each one.

If any bot comments were addressed (fixed or dismissed), post a summary comment
on the PR using tables. Number findings sequentially (F-01, F-02, ... for
fixed; D-01, D-02, ... for dismissed). Use each bot comment's `html_url` for
the link column. The Fix column should contain:

- A commit SHA if the fix was applied in-place.
- A link to the fix PR if the fix was delegated to `/fix-bot-reviews`.

```
gh pr comment <pr-number> --body "$(cat <<'EOF'
## Bot Review Findings

### Fixed

| #    | Comment            | Description   | Fix                |
| ---- | ------------------ | ------------- | ------------------ |
| F-01 | [→](<comment-url>) | <description> | <commit-or-fix-pr> |
| F-02 | [→](<comment-url>) | <description> | <commit-or-fix-pr> |

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
gh pr comment <pr-number> --body '## Bot Review Findings

✅ No actionable findings.'
```

This summary is in addition to the individual replies already posted on each
bot comment thread.
