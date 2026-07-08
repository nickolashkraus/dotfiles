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

## Step 3: Read the result

Read the output JSON. The shape mirrors the posted review: `findings`
(each with tier, path, line, body) and a summary with tier counts and risk.

- **Zero findings**: Report "Pulse clean" with the risk level and stop.
- **Findings**: For each, assess legitimacy with the same bias-toward-fixing
  standard as `fix-ci`. Fix legitimate findings in the worktree. Dismissals
  require the bot to be clearly wrong (misread code, contradicts repo
  conventions or the function's own docstring); note dismissals for the PR
  description rather than replying (there is no PR yet).

## Step 4: Iterate until clean (with a convergence stop)

After fixing, re-run Step 2 on the updated diff. Repeat until Pulse reports
zero critical and zero should-fix findings.

**Stop criterion for non-converging runs.** Some changes never reach zero
because a rule pack over-fires on that change's shape. The clearest case is a
documentation, rules, or prompt file (for example `rules/*.md`): the
prompt-quality packs review it as if it were an executable review prompt and
keep surfacing fresh instruction-clarity angles on the same content, so the
finding count plateaus or rises across rounds instead of falling. When findings
stop converging (roughly: two consecutive rounds where the count does not drop,
or the same passage is re-flagged from a new angle after a good-faith reword),
do not keep looping. Instead: incorporate the substantively valuable findings
(real bugs, factual errors, genuine omissions), dismiss the residual
prompt-clarity findings with a one-line reason, note the dismissals for the PR
description, and proceed. Chasing a doc-file review to literal zero is the
over-investment this stop is meant to prevent.

Then re-run the repo's standard local verification (ruff, pyright, pytest for
the touched files) since the fixes changed code after the last verification
pass.

Report the final state: findings fixed (with one-line descriptions),
findings dismissed (with reasons), and the final risk assessment.
