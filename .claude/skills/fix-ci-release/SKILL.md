---
name: fix-ci-release
description: >
  Fix CI failures on a release PR by triaging findings into a Linear issue
  (release branches only accept cherry-picked merge commits, so do not commit
  fixes directly). TRIGGER when: failing CI or bot comments on a `release/*`
  branch PR. SKIP: dev-branch PR (use `fix-ci` or `fix-bot-reviews`).
disable-model-invocation: false
allowed-tools:
  Bash, Read, Glob, Grep, mcp__linear__save_issue, mcp__linear__list_projects
argument-hint: "[--re-review [all | unresolved]] [pr-number]"
---

You are fixing CI failures on a release PR (triage to Linear, do not commit).
Release branches only accept cherry-picked merge commits, so never commit
fixes directly. Instead, triage findings and create a Linear issue. Follow
every step in order.

Shared procedures (PR resolution, check waiting, retry handling, bot comment
fetch and filter, reply format, durable link format, summary tables) are
loaded from:

@~/.claude/skills/fix-ci-core/PROCEDURES.md

## Step 1: Parse arguments and resolve the PR

Parse `$ARGUMENTS` for the `--re-review [all | unresolved]` flag (see "Filter
bot comments by resolution status" in PROCEDURES.md). Remove the flag and
its value before continuing.

Then follow "Resolve the pull request" in PROCEDURES.md.

## Step 2: Wait for all checks to complete

Follow "Wait for all checks to complete" in PROCEDURES.md.

## Step 3: Assess CI results

- All pass: Skip to Step 5.
- Any failed: Continue to Step 4.

For transient or infrastructure failures, follow "Re-run failing checks" in
PROCEDURES.md. Note that release PRs are especially sensitive to destructive
shortcuts (close/reopen, force-push, empty commits): they accept only
cherry-picked merge commits, so state loss is not recoverable. If the retry
paths fail, diagnose and fix the root cause.

## Step 4: Diagnose CI failures

Follow "Diagnose CI failures" in PROCEDURES.md to fetch logs.

**Do not fix failures on this branch.** Instead, record each failure for the
Linear issue in Step 6.

If the failure is caused by code in the release (not transient), classify
its severity:

- **Critical/High**: The release may be broken. Present the failure to the
  user and ask: "This looks like it could affect the release. Should we fix
  it and cherry-pick into the release, or track it for post-release?" If the
  user approves, follow the cherry-pick fix flow in Step 4a.
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

Follow "Collect bot comments" and "Filter bot comments by resolution status"
in PROCEDURES.md.

If no actionable comments and all checks pass, go to Step 7.

### Triage each comment

For each bot comment, assess legitimacy and severity.

- **Clearly illegitimate**: Reply with a brief dismissal and reason. Follow
  "Reply to a bot comment" in PROCEDURES.md.
- **Legitimate, Critical/High**: Present to the user with the code context.
  Ask: "This is a high-severity finding. Should we fix it and cherry-pick
  into the release, or track it for post-release?" If the user approves,
  follow Step 4a (cherry-pick fix flow).
- **Legitimate, Medium/Low**: Record for the Linear issue. Reply
  acknowledging the finding and linking the Linear issue (once created in
  Step 6).

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

After creating the issue, go back and reply to each bot comment with a link
to the Linear issue (follow "Reply to a bot comment" in PROCEDURES.md):

```
Tracked in [<linear-issue-slug>](<linear-issue-url>).
```

## Step 7: Summarize

Post a summary comment on the release PR. Follow "Findings summary" and
"Durable comment link format" in PROCEDURES.md. Use these table headers
(note the additional Severity and Linear columns for the Tracked section):

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
