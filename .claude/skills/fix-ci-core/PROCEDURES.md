# Shared Procedures for fix-* Skills

These procedures are referenced by:

- `~/.claude/skills/fix-ci/SKILL.md`
- `~/.claude/skills/fix-ci-release/SKILL.md`
- `~/.claude/skills/fix-bot-reviews/SKILL.md`

The skill bodies tell you which procedures to apply at each step. This file
is the canonical source for the mechanics so that fixes and updates land in
one place.

## Resolve the pull request

Parse `$ARGUMENTS` for a PR reference (any unflagged token). It can be a PR
number (e.g., `123`) or a PR URL (e.g.,
`https://github.com/owner/repo/pull/123`). `gh pr view` accepts either form
natively; if no reference was passed, it falls back to the current branch's
open PR:

```
gh pr view [<ref>] --json number,url,headRefName,baseRefName,title \
  --jq '{number, url, headRefName, baseRefName, title}'
```

If no PR is found, stop and tell the user.

Resolve `{owner}/{repo}` for `gh api` calls from the PR's `url` field (the
segment between `github.com/` and `/pull/`, e.g.,
`https://github.com/foo/bar/pull/123` becomes `foo/bar`). This works in
both modes (ref passed vs. inferred from current branch) and resolves
correctly even when the URL points at a different repo.

When invoking a sister skill downstream (e.g., `Skill(skill:
"fix-bot-reviews", args: "<ref>")`), pass the original reference unchanged.
If the user provided a URL, pass the URL through; the downstream skill
re-parses it.

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
- **Default-setup CodeQL** (`gh run view <run-id> --json event` shows
  `"event": "dynamic"`; no workflow file in the repo): There is no API retry
  path. `gh run rerun` returns "cannot be retried" and the
  check-run/check-suite rerequest endpoints 404. The run re-executes on the
  next push to the branch, or the user can click "Re-run" in the GitHub UI. If
  the failure is a GitHub-side infra blip and the check is not in the required
  ruleset, report it rather than manufacturing a push.
- **External check (e.g., Google Cloud Build)**: `gh run rerun` does not
  apply. First try GitHub's check-run rerequest:
  `gh api -X POST repos/{owner}/{repo}/check-runs/<check-run-id>/rerequest`.
  If that returns 404 (the app does not support rerequest), fall back to the
  provider's native retry. For Cloud Build:

  ```
  curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  https://cloudbuild.googleapis.com/v1/projects/<project>/builds/<build-id>:retry
  ```

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

Fetch `id` and `pull_request_review_id` together when collecting findings,
since both are required for the durable comment link format (see below):

```
gh api repos/{owner}/{repo}/pulls/<pr>/comments --paginate \
  --jq '.[] | {id, pull_request_review_id}'
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

Do NOT use the Files-tab range anchor either
(`/files/<base>..<original_commit_id>#r<id>`). It depends on the file
still being in the PR's current diff and on `original_commit_id` still
being reachable from the PR's tip. Both assumptions break under rebase
and under stacked PRs: GitHub redirects the URL to whichever PR can
render the diff in its current state (often a parent PR), landing the
reader far from the comment.

Use the review wrapper instead, which has the following form:

```
https://github.com/<owner>/<repo>/pull/<N>#pullrequestreview-<review_id>
```

The review wrapper renders independently of diff context. It lands the
reader on the bot's review header in the Conversation tab, where the
inline comment is listed in the thread. This works under rebase, under
stacked PRs, and for comments on files no longer in the diff.

The tradeoff is precision. The reader may need to scroll a few comments
to find the specific finding. Mitigate by writing a self-contained
Description column in the summary table (one short sentence naming the
bot and the substance of the finding), so the link is a convenience and
not the primary information channel.

Fetch `pull_request_review_id` per comment:

```
gh api repos/<owner>/<repo>/pulls/comments/<id> --jq '.pull_request_review_id'
```

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

Always write the summary body to `/tmp/pr-<pr-number>-summary.md` and post via
`gh pr comment --body-file`. Never inline this body via `--body "$(cat <<'EOF'
... EOF)"`: the table contains backticks, links, and shell-special characters
that the typography pre-flight hook rejects when defensive escapes leak
through. The summary is always multi-line by nature (findings table,
dismissals, links), so the file path is the only correct path.

```
cat > /tmp/pr-<pr-number>-summary.md <<'EOF'
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

gh pr comment <pr-number> --body-file /tmp/pr-<pr-number>-summary.md
```

The Fix column should contain:

- A linked commit SHA (e.g., [`abc1234`](commit-url)) when the fix was
  applied in-place.
- A link to the fix PR when the fix was delegated to `/fix-bot-reviews`.
