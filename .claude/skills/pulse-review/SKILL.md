---
name: pulse-review
description: >
  Run the Pulse review bot locally against the current branch's diff with
  full repo context, mirroring the process the fh-pulse bot runs against
  a PR. TRIGGER when: before creating a PR in a Function-Health repo, user
  says "run pulse", "pulse this", or a pre-PR quality gate is required.
  SKIP: non-Function-Health repos (Pulse rules target FH repos).
disable-model-invocation: false
allowed-tools: Bash, Edit, Glob, Grep, Read
argument-hint: "[--no-pulse] [base-branch]"
---

You are running the Pulse review bot locally against the current branch,
reproducing the same pipeline the `fh-pulse` bot runs against a PR (per-rule
sub-agent fan-out with repo read access, then orchestrator dedupe). The goal
is a clean Pulse result *before* the PR exists.

## Step 0: Opt-out check

If `$ARGUMENTS` contains `--no-pulse` (or `--skip`), do not run Pulse. Report
"Local Pulse gate skipped by request" and stop. This is the local opt-out for
changes where a local Pulse pass adds no value (for example, docs-only or
rules-file changes that the prompt-quality rule packs review as if they were
agent prompts). It disables only this local gate; the `fh-pulse` bot still
reviews the PR after push.

## Step 1: Resolve inputs

1. The reviewed repo worktree is the current working directory. It must be
   the Function-Health service repo (not the pulse repo).
2. Parse `$ARGUMENTS` for a base branch (ignoring the `--no-pulse` / `--skip`
   flag handled above). If absent, use the repo's default branch:
   `git remote show origin | grep 'HEAD branch' | awk '{print $NF}'`.
3. Resolve `owner/repo` from `git config --get remote.origin.url`.
4. Fetch the base: `git fetch origin <base>`.
5. Sync the pulse checkout to the deployed bot's version. A stale or
   feature-branch checkout runs different rule packs and models than the
   `fh-pulse` bot and the local result diverges wildly from the PR review
   (observed: a checkout parked on a rules feature branch was missing two
   entire rule packs that produced 5 of the PR's 7 criticals). Run:

   ```bash
   git -C ~/Function-Health/pulse fetch origin
   git -C ~/Function-Health/pulse status -sb
   ```

   If the checkout is not on the default branch tip (detached, feature
   branch, or behind), check out the default branch and fast-forward it
   before running the review. If the checkout is dirty or holds
   work-in-progress you cannot switch away from, say so and warn that the
   local result may diverge from the bot.

   After any branch switch or fast-forward, run
   `npm --prefix ~/Function-Health/pulse install` before the review.
   A stale `node_modules` from the previous checkout fails at startup
   with `ERR_MODULE_NOT_FOUND`.

   A checkout already sitting on the default branch tip is not proof that
   `node_modules` is current: it also goes stale when the lockfile moved
   under an unchanged branch name since the last local review. That failure
   looks different, a `SyntaxError` naming a missing export rather than a
   missing module (observed: `The requested module 'ai' does not provide an
   export named 'isStepCount'`). Treat any startup crash out of
   `src/subagent.ts` or `src/review.ts` as a stale install, run `npm install`,
   and retry once before investigating further.

## Step 2: Run Pulse

Pipe the merge-base diff into the pulse checkout at
`~/Function-Health/pulse`, with repo context and repo identity forced. The
OpenAI key is injected at point of use from GCP Secret Manager (never write
it to a file; the production worker reads the same secret):

```bash
git diff origin/<base>...HEAD | \
  OPENAI_API_KEY="$(gcloud secrets versions access latest \
    --secret=pulse-openai-api-key --project=function-health-dev-env)" \
  npm --prefix ~/Function-Health/pulse run review -- \
    --reviewed-repo <owner>/<repo> \
    --repo-root "$PWD" \
    --out <scratchpad>/pulse-<branch>.json
```

Notes:

- `--repo-root` gives sub-agents `read_file`/`grep` tools rooted at the
  worktree, matching the bot's PR checkout. Without it the review is
  diff-only and shallower than the bot.
- `--reviewed-repo` forces repo identity so `repo_allowlist` rule packs
  resolve for the service repo (stdin mode would otherwise resolve the repo
  from the invocation cwd).
- Include uncommitted work by using `git diff origin/<base>` (two dots, no
  HEAD) instead; the committed three-dot form is the default because it
  matches what the PR will contain.
- Runtime is a few minutes (11 rule packs fan out). Run it in the
  background and read the JSON when it completes. stderr is the verbose
  per-rule log; the JSON file is the review.

## Step 3: Fix the real bugs, then stop

Read the output JSON. The shape mirrors the posted review: `findings`
(each with tier, path, line, body) and a summary with tier counts and risk.

**This gate exists to catch defects before they reach a reviewer, not to
produce a clean Pulse result.** Fix the findings that name a defect: a wrong
result, a lost write, a race, a regression the diff introduces, a claim in a
comment or docstring that the code contradicts. Leave everything else for the
PR, where the same bot will raise it again if it still holds and a human can
weigh it.

Leave, specifically:

- A finding whose substance is a rule ID rather than a failure (for example
  "violates PY-MIG-03") where the rule's premise does not hold for this code:
  chunking demanded on a table with four matching rows, a logging shape that
  contradicts every sibling call in the file.
- Style, naming, comment-coverage and test-coverage findings.
- Anything you would answer with "correct in general, not here".

Note what you left and why, in one line each, for the PR description. There is
no PR yet, so there is nothing to reply to.

## Step 4: Do not re-run

Run Pulse once. Fix the real bugs. Push.

Three reasons:

- **The local run cannot preempt the CI check**, because it is the same bot
  with the same rule packs. Clearing it locally does not reduce what CI finds;
  CI re-reviews from scratch and routinely raises findings on a diff the local
  run passed.
- **Driving findings to zero may not change the outcome.** Auto-approval is
  gated on the risk *tier*, not the findings (`decideReviewEvent` in
  `pulse/src/risk-assessment.ts`): zero criticals approves only at very-low,
  low or medium. At medium-high and above the check reports `failure` with
  "Owner approval required" and needs a named owner, however clean the
  findings are. Read `summary.risk` in the JSON before spending anything on
  convergence.
- **Iterating generates work.** A local finding can ask for code that the CI
  run then flags as a violation of a different rule, so the fix is written and
  then removed. One rule pack does not know what another asked for, and a
  second local round is where that collision gets built rather than caught.

If a fix in Step 3 was substantial enough that you want it checked, that is
what the PR review is for. Re-run locally only when the user asks.

## Step 5: Check the size gate before pushing

**Size gate counts ADDED lines.** The deployed bot short-circuits PRs whose
counted ADDED lines exceed 2,000 (strict `>`; excludes come from configured
globs). Check the count before pushing:

```bash
git diff <base>...HEAD --numstat | awk '{a+=$1} END {print a}'
```

Two traps for a PR near the limit:

- **Deduplicating existing code makes it worse, not better.** Rewriting a
  line converts it into an added line, so a change that shortens the file can
  still raise the counted total.
- **Each fix round adds lines**, usually tests, so a PR just under the limit
  can cross it mid-review.

Over the limit, the bot skips review entirely and its standing
`CHANGES_REQUESTED` blocks the PR. Get under it by trimming added prose in
the new files, or split into stacked PRs along a seam in the change.

Then re-run the repo's standard local verification (ruff, pyright, pytest for
the touched files) since the fixes changed code after the last verification
pass.

Report the final state in a few lines: the bugs fixed (one line each), the
count left for the PR with a one-line reason each, and the risk tier with
whether it is above the auto-approve cut-line. Say the tier explicitly, since
it tells the user up front whether an owner approval is needed regardless of
what the findings say.
