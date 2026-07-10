---
name: fix-ci-release
description: >
  Monitors CI and bot comments on a release PR. Creates a Linear issue for
  findings instead of committing fixes directly, since release branches only
  accept cherry-picked merge commits.
---

You are monitoring CI and bot comments on a **release PR**. Release branches
only accept cherry-picked merge commits, so you must never commit fixes
directly. Instead, triage findings and create a Linear issue. Follow every step
in order.

## Step 1: Determine the pull request

Parse the user-provided skill input for an optional `--re-review` flag and PR
number.

- `--re-review [all | unresolved]`: Re-review bot comments. `all` (default)
  re-reviews every comment. `unresolved` skips resolved comments but ignores
  reply status.

If no PR number, detect from the current branch:

```
gh pr view --json number --jq '.number'
```

Also determine `{owner}/{repo}`:

```
gh repo view --json nameWithOwner --jq '.nameWithOwner'
```

## Step 2: Wait for all checks to complete

```
gh pr checks <pr-number>
```

Wait for **all** checks (including external: Cloud Build, Sentry, Wiz, etc.).
Re-check every 30 seconds until none are pending.

## Step 3: Assess CI results

- All pass: Skip to Step 5.
- Any failed: Continue to Step 4.

For transient/infrastructure failures, re-run the specific check:

```
gh run rerun <run-id> --failed
```

For external checks (e.g., Cloud Build), follow the documented retry path:
GitHub check-run rerequest first, then the provider's native retry API.

**IMPORTANT**: Every check must pass, including non-required ones.
A non-blocking failure is still a failure and must be cleared, not documented
around.

**IMPORTANT**: Never close and reopen the release PR to retrigger CI. It
rewrites timestamps, fires PR-lifecycle webhooks with side effects, and leaves
the original failed check as a stuck record (a new run is created under
a different name, so it does not replace the old one). Release PRs are
especially sensitive: they accept only cherry-picked merge commits, so
destructive shortcuts that lose state are not recoverable. If the retry paths
above fail, diagnose and fix the root cause. Do not close/reopen, force-push,
or push empty commits as workarounds.

Then go back to Step 2.

## Step 4: Diagnose CI failures

```
gh run view <run-id> --log-failed
```

Read the logs. Identify root causes. **Do not fix them on this branch.**
Instead, record each failure for the Linear issue in Step 6.

If the failure is caused by code in the release (not transient), classify its
severity:

- **Critical/High**: The release may be broken. Present the failure to the user
  and ask: "This looks like it could affect the release. Should we fix it and
  cherry-pick into the release, or track it for post-release?" If the user
  approves, follow the cherry-pick fix flow in Step 4a.
- **Medium/Low**: Record for the Linear issue. The release can proceed.

### Step 4a: Cherry-pick fix flow

When the user approves a critical/high fix for the release:

1. Create a fix branch off `dev`:

   ```
   git worktree add -b <fix-branch> ../<fix-branch> origin/dev
   ```

2. Apply the fix in the worktree. Run CI locally.
3. Commit, push, and create a PR into `dev`:

   ```
   gh pr create --base dev --head <fix-branch>
   ```

4. Wait for CI to pass and the PR to be merged.
5. Cherry-pick the merge commit into the release branch:

   ```
   git cherry-pick -m 1 <merge-sha>
   git push
   ```

6. Go back to Step 2 to re-check CI on the release PR.

## Step 5: Assess review bot comments

Collect bot comments from **both** sources:

1. **PR review comments**:

   ```
   gh api repos/{owner}/{repo}/pulls/<pr-number>/comments --paginate
   ```

2. **Review-level comments**: List reviews, filter for bot authors, then fetch
   each review's comments:

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

Filter by resolution status (same rules as `$fix-ci`):

- **No flag**: Skip comments that are resolved or that `nickolashkraus` has
  already replied to. Check the comment's reply thread for any comment where
  `.user.login == "nickolashkraus"`.
- **`--re-review all`**: Act on all bot comments.
- **`--re-review unresolved`**: Skip resolved, ignore reply status.

If no actionable comments and all checks pass, go to Step 7.

### Triage each comment

For each bot comment, assess legitimacy and severity.

- **Clearly illegitimate**: Reply with a brief dismissal and reason.
- **Legitimate, Critical/High**: Present to the user with the code context.
  Ask: "This is a high-severity finding. Should we fix it and cherry-pick into
  the release, or track it for post-release?" If the user approves, follow Step
  4a (cherry-pick fix flow).
- **Legitimate, Medium/Low**: Record for the Linear issue. Reply acknowledging
  the finding and linking the Linear issue (once created in Step 6).

Post replies via:

```
gh api repos/{owner}/{repo}/pulls/<pr-number>/comments \
  -f body='<reply>' -F in_reply_to=<comment-id>
```

### Evidence in replies

When replying to a bot comment, include an **Evidence** section if external
documentation substantiates the decision:

```
**Evidence**:
- Brief factual statement.
- [Page title (Source)](https://...)
```

## Step 6: Create Linear issue

If there are any legitimate findings (CI failures or bot comments), create
a single Linear issue consolidating all of them:

- **Title**: "Address <Release Title> Bot Review Findings" (Title Case)
- **Team**: Detect from the release PR's issue slugs (e.g., `BYB`)
- **Project**: Detect from the PRs included in the release.
- **State**: Todo

Use this description format:

```markdown
## Overview

Consolidates actionable findings from bot reviews on the release PR (#XXXX).
These cannot be fixed on the release branch (cherry-picks only) and must be
addressed on `dev`.

## Acceptance Criteria

- [ ] <One checkbox per finding>

## Implementation Details

### 1. <Finding title> (<Severity>)

<Description of the issue, affected code, and suggested fix>

**Source**: [<Bot name>](<comment-url>).

## References

- [PR #XXXX](<pr-url>): Release PR.
```

After creating the issue, go back and reply to each bot comment with a link to
the Linear issue:

```
Tracked in [<linear-issue-slug>](<linear-issue-url>).
```

## Step 7: Summarize

Post a summary comment on the release PR:

```
gh pr comment <pr-number> --body "$(cat <<'EOF'
## Bot Review Findings

### Tracked

| #    | Comment            | Description   | Severity | Linear            |
| ---- | ------------------ | ------------- | -------- | ----------------- |
| T-01 | [→](<comment-url>) | <description> | <sev>    | [BYB-NNNN](<url>) |

### Dismissed

| #    | Comment            | Description   | Reason   |
| ---- | ------------------ | ------------- | -------- |
| D-01 | [→](<comment-url>) | <description> | <reason> |
EOF
)"
```

Omit a section if it has no entries. If zero findings:

```
gh pr comment <pr-number> --body '## Bot Review Findings

✅ No actionable findings.'
```

~/.codex/rules/meta-learning.md
