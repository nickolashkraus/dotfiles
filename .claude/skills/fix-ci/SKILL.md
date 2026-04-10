---
name: fix-ci
description: >
  Fixes CI failures on a pull request by fetching check results, diagnosing the
  issues, and applying fixes.
disable-model-invocation: false
allowed-tools: Bash, Edit, Glob, Grep, Read
argument-hint: [pr-number]
---

You are fixing CI failures on a pull request. Follow every step in order.

## Step 1: Determine the pull request

If a PR number was passed (`$ARGUMENTS`), use it. Otherwise, detect the current
branch and find its open PR:

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

- If all checks pass and no unresolved bot comments remain (see Step 5), go to
  Step 7.
- If any checks have failed, continue to Step 4.

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

For each bot comment, check whether:

- The comment thread is already resolved.
- I (username: `nickolashkraus`) have already replied. Check the comment's
  reply thread for any comment where `.user.login == "nickolashkraus"`.

**Skip** any comment that is resolved or already has a reply from
`nickolashkraus`. Only act on unresolved comments with no reply from me.

### For each remaining unresolved comment

- **Legitimate issue**: Fix it the same way as a CI failure (read context,
  apply the fix directly).
- **Illegitimate issue**: Resolve the comment with a reply explaining why the
  suggestion does not apply or is incorrect. Post the reply using:

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

## Step 7: Summarize

List each CI failure and review bot comment, and what you did to fix or resolve
each one.
