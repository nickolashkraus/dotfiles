---
name: fix-ci
description: >
  Fixes CI failures on a pull request by fetching check results, diagnosing the
  issues, and applying fixes.
disable-model-invocation: false
allowed-tools: Bash, Edit, Glob, Grep, Read
argument-hint: [--in-place] [--re-review [all | unresolved]] [pr-number]
---

You are fixing CI failures on a pull request. Follow every step in order.

## Step 0: Invoke this skill explicitly

If you reached this workflow by improvising a manual loop (polling `gh pr
checks`, replying to bot comments inline, etc.) without invoking `Skill(skill:
"fix-ci")` first, stop and invoke it now. The procedure below is not a list of
suggestions; it encodes the inline-reply, Evidence-block, and findings-table
conventions that downstream reviewers and re-runs depend on.

If you tried to delegate this to a sub-agent (e.g., via the `Agent` tool) and
the spawn failed (worktree-isolation error, missing hook, etc.), the failed
delegation does **not** excuse skipping the skill. Run the skill yourself on
every affected PR. The fallback for a failed agent spawn is not ad-hoc bash; it
is "run the skill in this conversation, one PR at a time."

When working a stack of PRs, run the skill once per PR in stack order. Do not
batch-loop across PRs without re-entering the procedure for each one.

## Step 1: Determine the pull request

Parse `$ARGUMENTS` for flags and an optional PR number:

- `--in-place`: Fix bot comments directly on this branch (no stacked PR).
- `--re-review [all | unresolved]`: Re-review bot comments. `all` (default)
  re-reviews every comment regardless of resolution or reply status.
  `unresolved` re-reviews only comments that have not been resolved via the
  GitHub UI, ignoring reply status.

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
- **Don't fake the handoff.** If you start a background wait (`Monitor`,
  `ScheduleWakeup`, `/loop`, or any `run_in_background` task), you must
  register a concrete resumption (cron, scheduled wakeup, or loop tick) in the
  same turn. Don't end the turn relying on the user to re-prompt. "I'll let the
  monitor continue running" or "waiting for monitor to notify me" are not valid
  handoffs unless paired with a registered resumption.
- Once all checks have completed, continue to Step 3.

## Step 3: Assess results

- If any checks have failed, continue to Step 4.
- If all checks pass, skip to Step 5 to assess bot comments.

**IMPORTANT**: Never create an empty commit to "Retry CI". Instead, read the
logs to diagnose the failure and, if the failure is transient or
infrastructure-related, re-run the specific check:

- **GitHub Actions**: `gh run rerun <run-id> --failed`.
- **External check (e.g., Google Cloud Build)**: `gh run rerun` does not
  apply. First try GitHub's check-run rerequest:
  `gh api -X POST repos/{owner}/{repo}/check-runs/<check-run-id>/rerequest`.
  If that returns 404 (the app does not support rerequest), fall back to the
  provider's native retry. For Cloud Build:
  `curl -X POST -H "Authorization: Bearer $(gcloud auth print-access-token)" https://cloudbuild.googleapis.com/v1/projects/<project>/builds/<build-id>:retry`
  (`gcloud builds triggers run` does not work for GitHub PR triggers).

**IMPORTANT**: Every check must pass, including non-required ones.
A non-blocking failure is still a failure and must be cleared, not documented
around.

**IMPORTANT**: Never close and reopen a PR to retrigger CI. It rewrites
timestamps, fires PR-lifecycle webhooks with side effects, and leaves the
original failed check as a stuck record (a new run is created under a different
name, so it does not replace the old one). If the retry paths above fail,
diagnose and fix the root cause. Do not force-push or push empty commits as
workarounds.

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

### Filter comments by resolution status

How comments are filtered depends on the `--re-review` flag:

- **No flag** (default): Skip comments that are resolved or that
  `nickolashkraus` has already replied to. Check the comment's reply thread for
  any comment where `.user.login == "nickolashkraus"`.
- **`--re-review all`**: Act on all bot comments regardless of resolution or
  reply status.
- **`--re-review unresolved`**: Skip resolved comments, but ignore reply
  status. This is for the workflow where you review findings in the GitHub UI,
  resolve the ones you want to skip, then re-run to fix the rest.

If no actionable bot comments remain and all checks pass, go to Step 7.

### If `--in-place` was NOT set

**Pre-check**: Trivial fixes auto-promote to in-place. Before delegating, size
up the actionable findings. If the total fix is *trivial*, apply in-place on
the current branch instead of spinning up a stacked fix PR. The stacked-PR
overhead (worktree, separate PR, separate CI run, separate review thread,
summary cross-posts) is not worth it for a one-line fix.

Treat a fix as trivial when **all** of the following hold:

- Total affected files: 1-3
- Total code delta: under ~15 lines (excluding test parametrize-list
  adjustments).
- No new helpers, abstractions, or refactors. Existing code shape is preserved;
  you are tweaking constants, frozensets, guards, or conditionals.
- Test changes are limited to parametrize lists, docstrings, or assertion-value
  flips. No new test classes or fixtures.
- The bot finding is precise and the suggested fix is well-defined. You are not
  making a judgment call that could span multiple files.

When in doubt, delegate. The asymmetry is: a small fix done in-place is cheap;
a sprawling fix done in-place pollutes the parent branch's commit history and
review surface, and the user cannot ask for the fix to be revised separately.

If the fix is trivial: Act as if `--in-place` was passed and follow the
in-place section below.

If the fix is non-trivial: Delegate to `/fix-bot-reviews <pr-number>` (pass
through `--re-review <value>` if it was set). This creates a stacked fix PR for
the bot comment fixes. Skip to Step 7 after `/fix-bot-reviews` completes.

### If `--in-place` was set

For each remaining unresolved comment, assess whether it is legitimate and fix
in-place on the current branch.

**Bias toward fixing.** If the suggestion is plausible, fix it. Only dismiss
a comment if it is clearly wrong:

- The bot misread the code or misunderstood the logic.
- The suggestion would break existing behavior.
- The suggestion contradicts project conventions.
- The suggestion contradicts the product or feature specification.
- The suggestion contradicts the function's own docstring or in-tree comments.
  Before mutating a function based on a "sibling pattern" or "consistency"
  argument, read the docstring of the function being changed. If the docstring
  documents an intentional divergence (e.g., "preserved on relink" vs siblings
  that reset), trust the docstring; the bot's analogy is likely missing
  context.

For each comment:

- **Legitimate issue** (default): Read the relevant source files to understand
  context, then apply the fix directly. When the finding identifies a fix in
  one of a parallel pair/set of helpers (e.g., `_try_customer_fallback` vs
  `_try_member_id_fallback`, or sibling upsert helpers), grep for the parallel
  sites and apply the same fix to each. A bot reporting on one site rarely
  means the issue is unique to that site; the omission almost always exists
  symmetrically.
- **Clearly illegitimate**: Reply with a brief explanation of why the
  suggestion does not apply:

  ```
  gh api repos/{owner}/{repo}/pulls/<pr-number>/comments \
    -f body='<reply>' -F in_reply_to=<comment-id>
  ```

### Evidence in replies

When replying to a bot comment (whether fixing or dismissing), include an
**Evidence** section if there is existing source documentation (e.g., Stripe
docs, API specs, framework guides) that substantiates the decision. Use the
format:

```
**Evidence**:
- Brief factual statement.
- [Page title (Source)](https://...)
```

Do not fabricate an evidence section when no external documentation is
relevant.

## Step 6: Verify, commit, and push

Run the same CI commands locally to confirm the fixes work. Use the project's
test/lint/build commands as identified from the CI logs or project
configuration (e.g., `Makefile`, `package.json`, `pyproject.toml`).

If any command still fails, go back to Step 4. Do not push between fix
iterations.

Once **all** local verification passes (CI fixes and bot comment fixes), commit
and push in a single push. Always create a new commit rather than amending and
force-pushing, so that review history and prior CI runs are preserved. Then go
back to Step 2 and wait for all checks to complete before taking further action.
Keep iterating until every check passes and all bot comments are addressed.

Follow the commit rules from @~/.claude/rules/git.md:

- Subject line: 50 characters or less, capitalized, imperative mood, no period.
- Body: Explain what bot comments were addressed and why.
- No co-authored-by or signature lines.

## Step 7: Summarize

List each CI failure and review bot comment, and what you did to fix or resolve
each one.

If any bot comments were addressed (fixed or dismissed), post a summary comment
on the PR using tables. Number findings sequentially (F-01, F-02, ... for
fixed; D-01, D-02, ... for dismissed).

**Comment link format**: Do NOT use the API's `html_url`
(`pull/N#discussion_r<id>`) directly. That anchor lives on the Conversation tab
and is silently collapsed for outdated comments (any comment whose `line`
attribute is now `null` because the underlying diff line changed). The link
appears to do nothing because GitHub does not auto-expand the "Outdated"
section on navigation. Instead, build the durable Files-tab anchor from the
comment's `original_commit_id` and `id`:

```
https://github.com/<owner>/<repo>/pull/<N>/files/<original_commit_id>#r<id>
```

This anchor lives on the file/commit pair the bot actually reviewed, so it
always scrolls to and expands the comment regardless of whether the line is
"outdated" in the current diff. Fetch `id` and `original_commit_id` together
when collecting findings:

```
gh api repos/{owner}/{repo}/pulls/<pr>/comments --paginate \
  --jq '.[] | {id, original_commit_id}'
```

The Fix column should contain:

- A linked commit SHA (e.g., [`abc1234`](commit-url)) if the fix was applied
  in-place.
- A link to the fix PR if the fix was delegated to `/fix-bot-reviews`.

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

Omit a section if it has no entries. If there are zero findings (nothing fixed
or dismissed), post:

```
gh pr comment <pr-number> --body '## Bot Review Findings

✅ No actionable findings.'
```

This summary is in addition to the individual replies already posted on each
bot comment thread.

@~/.claude/rules/meta-learning.md
