---
name: fix-ci
description: >
  Fix CI failures on a pull request by fetching check results, diagnosing the
  issues, and applying fixes. TRIGGER when: `gh pr checks` shows failures, user
  says "fix CI on PR N", user pastes failing check name or deploy log error.
  SKIP: only bot review comments to address (use `fix-bot-reviews`).
disable-model-invocation: false
allowed-tools: Bash, Edit, Glob, Grep, Read, Skill
argument-hint: "[--in-place] [--re-review [all | unresolved]] [pr-ref]"
---

You are fixing CI failures on a pull request. Follow every step in order.

Shared procedures (PR resolution, check waiting, retry handling, bot comment
fetch and filter, reply format, durable link format, summary tables) are
loaded from:

@~/.claude/skills/fix-ci-core/PROCEDURES.md

When working a stack of PRs, run this skill once per PR in stack order. Do
not batch-loop across PRs without re-entering the procedure for each one.

## Step 1: Parse arguments and resolve the PR

Parse `$ARGUMENTS` for flags:

- `--in-place`: Fix bot comments directly on this branch. **This is now the
  default**, and the flag is accepted only so existing invocations keep
  working. A stacked fix PR costs a worktree, a second CI run, a second
  review thread and two summary cross-posts, and the review bots now land
  findings fast enough that the parent PR is still open and unreviewed when
  they arrive. Fixing in place is what I want every time.
- `--stacked`: Opt in to the old behavior and delegate to `fix-bot-reviews`.
  Only use this when I ask for it by name.
- `--re-review [all | unresolved]`: See "Filter bot comments by resolution
  status" in PROCEDURES.md.

Remember the `--re-review` value (if set) for Step 5; it must be threaded
through to `fix-bot-reviews`. Remove both flags from `$ARGUMENTS` before
continuing. Then follow "Resolve the pull request" in PROCEDURES.md.

## Step 2: Wait for all checks to complete

Follow "Wait for all checks to complete" in PROCEDURES.md.

**Do not idle while checks run.** A review bot posts its findings as soon as
its own check finishes, long before the slowest check (often the test suite or
an external build) completes. Once a bot review is on the PR, start Step 5
against it immediately rather than waiting for the rollup: triage the comments,
fix the legitimate ones, and draft the replies. Fold any resulting code change
into the same commit as the CI fixes from Step 4, so the push in Step 6 is
still one push and one re-run.

The waiting itself is still required before Step 6 and before declaring the job
done; what is not required is doing nothing during it. Reporting "waiting on
the remaining checks" while a bot review sits unread is wasted wall-clock, and
on a slow suite that is most of the cycle.

## Step 3: Assess CI results

- If any checks failed, continue to Step 4.
- If all checks pass, skip to Step 5 to assess bot comments.

For transient or infrastructure failures, follow "Re-run failing checks" in
PROCEDURES.md.

## Step 4: Diagnose and fix CI failures

Follow "Diagnose CI failures" in PROCEDURES.md to fetch logs.

For each failure:

1. Read the relevant source files to understand context.
2. Apply the fix directly. Do not just describe what needs to change.
3. If the fix requires running a command (e.g., `npm run format`, `ruff .`),
   run it.

## Step 5: Assess review bot comments

Follow "Collect bot comments" and "Filter bot comments by resolution status"
in PROCEDURES.md.

If no actionable bot comments remain and all checks pass, go to Step 7.

### If `--stacked` was set

Invoke `Skill(skill: "fix-bot-reviews", args: "<pr-ref> [--re-review
<value>]")`, where `<pr-ref>` is the original PR URL or number the user
passed (or the resolved number if the PR was inferred from the current
branch), and `<value>` is the value remembered from Step 1. Skip to Step 7
after `fix-bot-reviews` completes.

### Otherwise (the default, and what `--in-place` selects)

**Run the round counter first.** Follow "Count the rounds per file, and stop
at three" in PROCEDURES.md before reading a single finding. If it prints
anything, stop there and ask; the design in that file is the problem, and
another round of fixes enlarges it.

**Bot findings are advice, not a gate.** Weigh each one against the code and
the rules, and dismiss the ones that do not hold rather than fixing
everything a bot can generate.

Before editing, sync the local worktree to the PR head. A worktree left on an
older commit (or a concurrent session's push) means you fix code that no longer
matches the PR, and the resulting commit must be discarded. Run `git fetch
origin <headRefName>` and, if `origin/<headRefName>` is ahead of `HEAD`, `git
reset --hard origin/<headRefName>` (or rebase local-only work onto it) so the
diff you read is the diff the bot reviewed. Re-read the flagged code from the
synced tree, not from memory of an earlier read.

For each remaining unresolved comment, apply "Bias toward fixing" in
PROCEDURES.md. For dismissals, follow "Reply to a bot comment".

For legitimate findings, read the relevant source files to understand
context, then apply the fix directly on the current branch.

## Step 6: Verify, commit, and push

Run the same CI commands locally to confirm the fixes work. Use the
project's test/lint/build commands as identified from the CI logs or project
configuration (e.g., `Makefile`, `package.json`, `pyproject.toml`).

If any command still fails, go back to Step 4. Do not push between fix
iterations.

Once **all** local verification passes (CI fixes and bot comment fixes),
commit and push in a single push. Always create a new commit rather than
amending and force-pushing, so that review history and prior CI runs are
preserved. Then go back to Step 2 and wait for all checks to complete before
taking further action. Keep iterating until every check passes and all bot
comments are addressed.

Commit per @~/.claude/rules/git.md. The body should explain which bot
comments were addressed and why.

## Step 7: Summarize

List each CI failure and review bot comment, and what you did to fix or
resolve each one.

If any bot comments were addressed (fixed or dismissed), post a summary
comment on the PR. Follow "Findings summary" in PROCEDURES.md and use the
"Canonical Fixed/Dismissed template" from that section.
