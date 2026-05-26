# Shared Procedures for fix-* Skills

These procedures are referenced by:

- `~/.claude/skills/fix-ci/SKILL.md`
- `~/.claude/skills/fix-ci-release/SKILL.md`
- `~/.claude/skills/fix-bot-reviews/SKILL.md`

The skill bodies tell you which procedures to apply at each step. This file
is the canonical source for the mechanics so that fixes and updates land in
one place.

## Resolve the pull request

Parse `$ARGUMENTS` for a PR number (any unflagged token). If a number was
passed, use it. Otherwise, detect the current branch's open PR:

```
gh pr view --json number,headRefName,baseRefName,title \
  --jq '{number, headRefName, baseRefName, title}'
```

If no PR is found, stop and tell the user.

Also resolve `{owner}/{repo}` for `gh api` calls:

```
gh repo view --json nameWithOwner --jq '.nameWithOwner'
```

Extract the Linear issue slug from the PR title (the prefix before the first
colon, e.g., `BYB-1120` from `BYB-1120: Handle missing statuses`). The slug
is used for downstream fix PRs and Linear issue creation.

## Wait for all checks to complete

```
gh pr checks <pr-number>
```

Classify every check as **pass**, **fail**, or **pending**.

- If any checks are pending, wait 30 seconds and re-check. Always wait for
  **all** checks to complete before moving on, including external checks
  (Cloud Build, Sentry, Wiz, third-party scanners).
- **Don't fake the handoff.** If you start a background wait (`Monitor`,
  `ScheduleWakeup`, `/loop`, or any `run_in_background` task), you must
  register a concrete resumption (cron, scheduled wakeup, or loop tick) in
  the same turn. Don't end the turn relying on the user to re-prompt. "I'll
  let the monitor continue running" or "waiting for monitor to notify me"
  are not valid handoffs unless paired with a registered resumption.

## Re-run failing checks

For transient or infrastructure failures, re-run the specific check rather
than committing a no-op or closing/reopening the PR.

- **GitHub Actions**: `gh run rerun <run-id> --failed`.
- **External check (e.g., Google Cloud Build)**: `gh run rerun` does not
  apply. First try GitHub's check-run rerequest:
  `gh api -X POST repos/{owner}/{repo}/check-runs/<check-run-id>/rerequest`.
  If that returns 404 (the app does not support rerequest), fall back to the
  provider's native retry. For Cloud Build:
  `curl -X POST -H "Authorization: Bearer $(gcloud auth print-access-token)" https://cloudbuild.googleapis.com/v1/projects/<project>/builds/<build-id>:retry`
  (`gcloud builds triggers run` does not work for GitHub PR triggers).

**IMPORTANT**: Every check must pass, including non-required ones.
A non-blocking failure is still a failure and must be cleared, not
documented around.

**IMPORTANT**: Never close and reopen a PR to retrigger CI. It rewrites
timestamps, fires PR-lifecycle webhooks with side effects, and leaves the
original failed check as a stuck record (a new run is created under
a different name, so it does not replace the old one). Never create an
empty commit to "retry CI". If the retry paths above fail, diagnose and fix
the root cause. Do not force-push or push empty commits as workarounds.

## Diagnose CI failures

For each failed check, fetch its logs:

```
gh run view <run-id> --log-failed
```

If the log is too large, fetch logs for the specific failed job:

```
gh run view <run-id> --log-failed --job <job-id>
```

Read the logs carefully. Identify the root cause of each failure (lint
error, type error, test failure, formatting issue, etc.).

## Collect bot comments

Bot comments live on two distinct endpoints; you must query both.

1. **PR review comments** (inline comments on diffs):

   ```
   gh api repos/{owner}/{repo}/pulls/<pr-number>/comments --paginate
   ```

2. **Review-level comments** (comments attached to reviews). List all
   reviews, filter for bot authors, then fetch each review's comments:

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

Fetch `id` and `original_commit_id` together when collecting findings, since
both are required for the durable comment link format:

```
gh api repos/{owner}/{repo}/pulls/<pr>/comments --paginate \
  --jq '.[] | {id, original_commit_id}'
```

## Filter bot comments by resolution status

How comments are filtered depends on the `--re-review` flag value parsed
from `$ARGUMENTS`:

- **No flag** (default): Skip comments that are resolved or that
  `nickolashkraus` has already replied to. Check the comment's reply thread
  for any comment where `.user.login == "nickolashkraus"`.
- **`--re-review all`** (or `--re-review` with no value): Act on all bot
  comments regardless of resolution or reply status.
- **`--re-review unresolved`**: Skip resolved comments, but ignore reply
  status. This is for the workflow where you review findings in the GitHub
  UI, resolve the ones you want to skip, then re-run to fix the rest.

## Bias toward fixing

For each unresolved bot comment, assess whether it is legitimate. Default
to fixing. Only dismiss a comment if it is clearly wrong:

- The bot misread the code or misunderstood the logic.
- The suggestion would break existing behavior.
- The suggestion contradicts project conventions.
- The suggestion contradicts the product or feature specification.
- The suggestion contradicts the function's own docstring or in-tree
  comments. Before mutating a function based on a "sibling pattern" or
  "consistency" argument, read the docstring of the function being changed.
  If the docstring documents an intentional divergence (e.g., "preserved on
  relink" vs siblings that reset), trust the docstring; the bot's analogy
  is likely missing context.

When the finding identifies a fix in one of a parallel pair/set of helpers
(e.g., `_try_customer_fallback` vs `_try_member_id_fallback`, or sibling
upsert helpers), grep for the parallel sites and apply the same fix to
each. A bot reporting on one site rarely means the issue is unique to that
site; the omission almost always exists symmetrically.

## Reply to a bot comment

```
gh api repos/{owner}/{repo}/pulls/<pr-number>/comments \
  -f body='<reply>' -F in_reply_to=<comment-id>
```

When replying (whether fixing or dismissing), include an **Evidence**
section if external documentation (e.g., Stripe docs, API specs, framework
guides) substantiates the decision:

```
**Evidence**:
- Brief factual statement.
- [Page title (Source)](https://...)
```

Do not fabricate an Evidence section when no external documentation is
relevant.

## Durable comment link format

Do NOT use the API's `html_url` (`pull/N#discussion_r<id>`) for comment
links in summary tables or cross-references. That anchor lives on the
Conversation tab and is silently collapsed for outdated comments (any
comment whose `line` attribute is now `null` because the underlying diff
line changed). The link appears to do nothing because GitHub does not
auto-expand the "Outdated" section on navigation.

Instead, build the durable Files-tab anchor from the comment's
`original_commit_id` and `id`:

```
https://github.com/<owner>/<repo>/pull/<N>/files/<original_commit_id>#r<id>
```

This anchor lives on the file/commit pair the bot actually reviewed, so it
always scrolls to and expands the comment regardless of whether the line is
"outdated" in the current diff.

## Findings summary

Post a summary comment on the PR using a Markdown table. Number findings
sequentially: `F-NN` for fixed, `D-NN` for dismissed, `T-NN` for tracked
(when findings are filed to Linear instead of fixed).

Use the durable comment link format (above) for the Comment column. Omit
any section that has no entries.

If there are zero findings (nothing fixed, dismissed, or tracked), post the
short-circuit body instead of an empty table:

```
gh pr comment <pr-number> --body '## Bot Review Findings

✅ No actionable findings.'
```

This summary is in addition to the individual replies already posted on
each bot comment thread.

### Canonical Fixed/Dismissed template

Use this template for skills that fix and dismiss findings inline (`fix-ci`,
`fix-bot-reviews`). For the Tracked variant (`fix-ci-release`), see that
skill's Step 7.

```
gh pr comment <pr-number> --body "$(cat <<'EOF'
## Bot Review Findings

### Fixed

| #    | Comment            | Description   | Fix                     |
| ---- | ------------------ | ------------- | ----------------------- |
| F-01 | [→](<comment-url>) | <description> | [`<sha>`](<commit-url>) |
| F-02 | [→](<comment-url>) | <description> | [`<sha>`](<commit-url>) |

### Dismissed

| #    | Comment            | Description   | Reason   |
| ---- | ------------------ | ------------- | -------- |
| D-01 | [→](<comment-url>) | <description> | <reason> |
| D-02 | [→](<comment-url>) | <description> | <reason> |
EOF
)"
```

The Fix column should contain:

- A linked commit SHA (e.g., [`abc1234`](commit-url)) when the fix was
  applied in-place.
- A link to the fix PR when the fix was delegated to `/fix-bot-reviews`.
