---
name: xp-harvesting
description: >
  Open a batch of small, genuinely useful PRs across Nickolas's top Function
  Health repos (bug fixes, dead code, docs the code contradicts), one agent
  per repo, then squash-merge each once CI is green and fh-pulse approves.
  Also reviews the open PRs requesting his review, which keeps reviews in
  balance with PRs. TRIGGER when: user says "xp harvesting", "harvest some
  XP", "PR sweep", "open easy PRs", "PRs that will get a Pulse approval",
  "quick wins across my repos", "review the PRs requesting my review".
  SKIP: a single known fix (use `ship` or `rip`); bot findings on an existing
  PR (use `fix-ci`).
disable-model-invocation: false
allowed-tools: Agent, SendMessage, Bash, Read, Grep, Glob
argument-hint: "[count] [repo ...]"
---

You are orchestrating a sweep: find one real defect per repo, open a PR for
each, verify every PR yourself, and merge the ones Pulse approves. Agents do
the finding and fixing; you keep verification and merging.

## Step 1: Pick the repos

If `$ARGUMENTS` names repos, use them. Otherwise rank by recent merged PRs and
take the top `count` (default 5):

```bash
gh search prs --author @me --owner Function-Health --merged \
  --created ">=<90 days ago>" --limit 300 --json repository \
  | jq -r '.[].repository.name' | sort | uniq -c | sort -rn | head -12
```

Skip infra repos (`sre-infra-terraform` and similar), where a merge can change
live infrastructure.

Check the balance first. The metrics score code reviews beside merged PRs, so
a sweep while reviews lag widens the gap:

```bash
gh search prs --reviewed-by nickolashkraus --owner Function-Health \
  --created ">=<90 days ago>" --limit 500 --json author \
  --jq '[.[]|select(.author.login!="nickolashkraus")]|length'
```

When that count is below the merged-PR count, post reviews first (see
Reviews below), and open no more sweep PRs in a day than reviews posted
that day. On 2026-11-18
it was 131 PRs to 83 reviews, and a five-repo sweep beside 51 review drafts
was too much: the load average passed 130 and no review was posted.

For each repo, record:

- **Default branch**: `gh api repos/Function-Health/<repo> --jq
  .default_branch`. Base PRs there.
- **Short link**: `ls ~/w | grep <repo-short>`. Use `~/w` links for every path,
  in your own commands and in agent briefs.
- **Merge rules**: `gh api repos/Function-Health/<repo>/rules/branches/<base>`.
  The org ruleset requires one approval (an `fh-pulse` APPROVED review
  satisfies it) plus the `pulse-review` and
  `sre-terraform-review-bot/risk-assessment` checks. Auto-merge is disabled
  org-wide, so `gh pr merge --auto` is not an option. Some repos also
  require the branch to be up to date with the base (member-app-middleware
  and membership-service do), which the classic protection endpoint does not
  show; a `BEHIND` merge state at green is the tell.

## Step 2: Fan out one agent per repo

Spawn one `general-purpose` agent per repo with `model: "opus"`, at most two at
a time, named `pr-<repo-short>`: each runs a full test suite, and five at once
beside other sessions made the machine unusable.

`Agent` subagents run on this session's account, and only the Function seat
counts in the Vibe Check AI-usage report. To put the spend there, run each
brief as a background headless session instead:

```bash
cd ~/w/<repo-short> && CLAUDE_CONFIG_DIR="$HOME/.claude-fh" command claude \
  --dangerously-skip-permissions -p "$BRIEF" --model opus \
  --name xp-sweep-<repo-short> --max-budget-usd 40 --output-format json \
  </dev/null > <log-dir>/sweep-<repo-short>.json
```

A headless session cannot be pinged, so its brief has to end at the open PR. On
2026-11-18 four of them cost $2 to $12 each and took 20 to 50 minutes; the
result's `result` field is the report.

Each brief must carry:

- **Goal**: One small PR (under ~100 added lines) fixing a verified defect:
  a bug with a test, dead code proven unreferenced, or a doc, docstring or
  comment the code contradicts. No churn or cosmetic rewording. Do not merge.
- **Avoid**: Migrations, Terraform, CI workflows and release gates, Datadog
  monitors, billing amounts, Stripe and payment behavior, entitlement
  grant/debit/refund behavior, auth, and any file touched by an open PR
  (`gh pr list -R <repo> --state open --limit 200 --json number,files`).
- **Dead-code proof**: Grep for string and dynamic references, tests, scripts,
  config and entry points before deleting.
- **Worktree**: `git -C ~/Function-Health/<repo> worktree add
  ~/Function-Health/<repo>/<branch> -b <branch> origin/<base>`, then
  `worktree-links` and work through the `~/w` link. Branch names are short
  hyphenated descriptions, no Linear slug. Never check out or edit in the
  default worktree; one agent detached `~/w/mam` by mistake.
- **Local CI**: The full suite exactly as `.github/workflows/*` runs it,
  through the project runner. For a bug fix, break the fix and watch the test
  fail. Run `pulse-review` once for runtime changes; skip it for docs. In
  member-journey-services, run pytest under `env -u XDG_CONFIG_HOME`: the
  release-gate tests move `HOME` but not `XDG_CONFIG_HOME`, so their
  `git config --global` writes otherwise land in the real
  `~/.config/git/config`, which is tracked in dotfiles. In
  membership-service, pytest needs
  `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/opt/libpq/lib` and
  `--postgresql-exec=/opt/homebrew/opt/postgresql@17/bin/pg_ctl` (the
  config points at CI's Linux `pg_ctl`), and must keep the cache plugin,
  since pytest-xprocess errors under `-p no:cacheprovider`. A
  membership-service suite that hangs is waiting on a Pub/Sub emulator
  a killed run left behind; `pytest --xkill` in that worktree clears it.
  Split the suite into directories rather than cutting a run off with
  `timeout`, which leaves its test Postgres running. The ppp-service
  and transaction-service suites take about 10 minutes, past the Bash
  tool's foreground limit, which moves them to the background; split the
  run (ppp-service: `tests/migrations` on its own; transaction-service: by
  directory). transaction-service's default worktree has no `.env`, so use
  the `TEST_POSTGRES_*` values from `.github/workflows/pytest.yml`, on
  another port when Homebrew Postgres holds 5432. member-app-middleware's
  Redis-backed suites need the workflow's `redis:7-alpine` service and its
  Redis URLs, or about 50 tests fail.
- **Commit and PR**: Imperative subject, 50 characters or fewer, no
  attribution. PR title matches; body is one or two sentences opening with
  a declarative verb.
- **Report promptly**: Return the PR URL, the change in two lines, local CI
  results, and any defects found but left out. Agents tend to miss their own
  background-completion notices and go silent for an hour. Tell them not to use
  `Monitor` or `run_in_background` for the test suite, since "run it in the
  foreground" alone did not stop two of five from idling on a Monitor. Send
  a status ping to any agent quiet for 20 minutes.

## Step 3: Verify each PR

When an agent reports, read `gh pr diff` and check its central claim with one
grep against `origin/<base>`: the route prefix, the absent references, the real
signature. An agent's report is a claim, not evidence.

## Step 4: Merge under the standing approval

`~/.claude/hooks/confirm-risky.py` blocks `gh pr merge` and `gh pr close` until
the command carries the `# user-approved: ` prefix, which normally takes a yes
from Nickolas for that exact command. On 2026-11-23 he gave this skill
a standing approval, recorded as an exception in `rules/git.md` (Merging) and
in `rules/security.md`: squash-merge a PR this sweep opened, without asking,
once all checks pass, `fh-pulse` has approved and no bot review comment is
open. The loop in Step 5 tests those criteria before it merges, so write the
prefix on it yourself.

The approval covers nothing else. Ask first before `gh pr close`, before
merging a PR the sweep did not open, before merging with a failing check or
without the `fh-pulse` approval, and before any other merge command (`--admin`,
`--merge`, `--rebase`).

## Step 5: Run a merge loop per PR

Run this in the background for each PR verified in Step 3, with the approval
prefix on the first line so the hook sees the merge command:

```bash
# user-approved: gh pr merge <PR> -R Function-Health/<repo> --squash --delete-branch=false
R=Function-Health/<repo>; PR=<PR>
for attempt in 1 2 3; do
  [ "$(gh pr view $PR -R $R --json mergeStateStatus -q .mergeStateStatus)" = "BEHIND" ] && { gh pr update-branch $PR -R $R --rebase >/dev/null 2>&1; sleep 30; }
  head=$(gh pr view $PR -R $R --json headRefOid -q .headRefOid)
  for i in $(seq 1 60); do
    out=$(gh pr view $PR -R $R --json statusCheckRollup,mergeStateStatus,headRefOid)
    [ "$(printf '%s\n' "$out" | jq -r .headRefOid)" != "$head" ] && break
    pending=$(printf '%s\n' "$out" | jq '[.statusCheckRollup[]|select((.status // "COMPLETED")!="COMPLETED" or (.state // "")=="PENDING")]|length')
    bad=$(printf '%s\n' "$out" | jq '[.statusCheckRollup[]|select(((.name // .context)|test("pr-plan-prod")) and (.conclusion=="ACTION_REQUIRED")|not)|select((.conclusion // .state) as $c|["FAILURE","ERROR","CANCELLED","TIMED_OUT","ACTION_REQUIRED"]|index($c))]|length')
    pulse=$(printf '%s\n' "$out" | jq -r '[.statusCheckRollup[]|select((.name // .context)=="pulse-review")|(.conclusion // .state)]|first // "none"')
    ms=$(printf '%s\n' "$out" | jq -r .mergeStateStatus)
    [ "$bad" != "0" ] && { echo "attempt $attempt: failing checks"; printf '%s\n' "$out" | jq -r '.statusCheckRollup[]|"\(.name // .context)=\(.conclusion // .state)"'; exit 1; }
    if [ "$pending" = "0" ] && [ "$pulse" = "SUCCESS" ]; then
      [ "$ms" = "BEHIND" ] && { echo "attempt $attempt: behind at green"; break; }
      sleep 30
      open=$(gh api graphql -F o=Function-Health -F n=<repo> -F p=$PR -f query='query($o:String!,$n:String!,$p:Int!){repository(owner:$o,name:$n){pullRequest(number:$p){reviewThreads(first:50){nodes{isResolved isOutdated}}}}}' --jq '[.data.repository.pullRequest.reviewThreads.nodes[]|select((.isResolved|not) and (.isOutdated|not))]|length')
      [ "$open" != "0" ] && { echo "open review threads on current head: $open"; exit 1; }
      gh pr view $PR -R $R --json reviews --jq '[.reviews[]|"\(.author.login)=\(.state)"]|join(", ")'
      gh pr merge $PR -R $R --squash --delete-branch=false && { gh pr view $PR -R $R --json state,mergedAt,mergeCommit --jq '"\(.state) \(.mergedAt) \(.mergeCommit.oid[:9])"'; exit 0; }
      echo "attempt $attempt: merge rejected"; break
    fi
    sleep 20
  done
done
echo "gave up after 3 attempts"; exit 1
```

What the loop encodes:

- **Busy bases**: `member-app-middleware` gets a commit on `main` every 20 to
  30 minutes, and checks take about 10, so a PR can fall behind at green more
  than once. The loop rebases and retries up to three times; restart it if all
  three lose the race. Merging one PR in a strict repo puts its siblings
  behind, which the loop handles the same way. Right after a base merge,
  `mergeStateStatus` reads `UNKNOWN` rather than `BEHIND`, so a loop that waits
  on a base fix should run `gh pr update-branch` unconditionally once the fix
  merges, or it judges the stale checks.
- **Prod plan gates**: A Cloud Build `*-pr-plan-prod` check sitting at
  `ACTION_REQUIRED` is a manual approval gate, not a failure, and is not
  required. Prior PRs merged past it.
- **Pulse owner gate**: `pulse-review` failing with zero findings means Pulse
  rated the PR medium-high or above and wants a code owner. Read `risk=` in the
  review body. Never add `/pulse:skip-review` to get past it. Report the risk
  rationale, check it against the code, and let the user choose between getting
  an owner's approval and closing the PR.
- **Approved with a should-fix**: Pulse can approve and still leave an
  inline should-fix comment, so the loop checks for open review threads
  rather than trusting the approval. Fix it with an amended commit; the old
  thread goes outdated and the loop ignores it, but resolve it anyway
  (`resolveReviewThread`). An outdated, unresolved thread kept
  transaction-service #2286 `BLOCKED` ("base branch policy prohibits the
  merge") for four days, though no visible rule requires resolution. The
  `sleep 30` gives Pulse time to post inline comments after its check
  turns green. When the finding is a docstring that overstates behavior,
  weaken or drop the claim instead of listing every branch: enumerating
  early returns on transaction-service #2286 drew a second finding about
  the ones missed.
- **Infra failures**: A check that dies before running (a registry 404
  while installing dependencies, say) is transient when the same workflow
  passes on other PRs. `gh run rerun <run> --failed`, then restart the
  loop. member-app-middleware's `fh-pypi-gateway` 404s in `Install
  dependencies` hit four checks in one afternoon, so for that repo have the
  loop rerun failures confined to the install steps (`gh run view <run>
  --json jobs`) a few times before exiting. When the same failures show
  on the base branch's push runs, the base is broken: gate the loop on the
  base's latest push run going green instead of rerunning.
- **`printf`, not `echo`**: The Bash tool runs zsh, whose `echo` expands the
  `\n` escapes inside JSON strings, and `jq` then rejects the control
  characters. Pipe captured `gh` JSON through `printf '%s\n'`.
- **Stale quotes in docs**: When a doc quotes a message whose content is now
  wrong, correct the quote and add a note that it was updated. A note beside an
  untouched stale quote still reads as contradictory guidance, and Pulse flags
  it.

## Step 6: Offer the follow-ups

Agents report defects they left out of scope. Verify each one, then offer it as
its own PR. When a follow-up touches the same file as an open PR in the sweep,
have its agent wait for that PR to merge and branch from the new base, or the
two will conflict.

## Step 7: Clean up

After the user agrees, remove each worktree the sweep created:

1. `git -C <worktree> status --porcelain` must be empty.
2. `git -C <worktree> cherry origin/<base> HEAD` must print only `-` lines.
   A rebase done through `gh pr update-branch` rewrites the remote branch and
   leaves the old commit locally, so it shows as unpushed even though its
   change is on the base. A `+` can also appear when later commits on the base
   touch the same lines, which changes the patch ID; if the local `HEAD` equals
   the merged PR's `headRefOid`, it is safe to remove.
3. `git -C ~/Function-Health/<repo> worktree remove <worktree>`, never
   `--force`.
4. `git branch -D <branch>` for merged PRs only. Keep a closed PR's branch so
   it can be reopened. Leave remote branches alone.
5. Run `worktree-links`.

## Reviews

The other half of the balance. Follow the Review Pipeline in the agent-os
project `domains/function/projects/xp-harvesting` (its `README.md`). Its
`reviews/run.sh <repo> <number>` runs a drafting session and then an
adversarial pass, both headless on the Function seat, and writes
`reviews/<repo>-<number>.md`. Nothing reaches GitHub until Nickolas approves
each review. Findings from the first full run, 2026-11-18:

- **Queue**: `gh search prs --review-requested @me --owner Function-Health
  --state open --limit 500` returned 210 PRs, 110 from dependabot or the
  sync bot. Review the ready, mergeable code PRs. Set aside drafts and PRs
  that conflict with their base, since the author has to change them.
- **Run**: `XP_LOG_DIR=<dir> xargs -P 2 -L 1 reviews/run.sh < <list>`, one
  `<repo> <number>` per line. Both sessions together cost about $5 and
  8 minutes per PR. `run.sh` skips a finished file, so a stopped batch resumes
  from the same list. Five at a time was too many.
- **Decide**: Apply "Text That Gets Posted" in `reviews/brief.md` again
  when writing `## To Post`. Nickolas rewrote every approval posted that
  day: each body became `LGTM 👍🏼`, a non-blocking question was deleted
  and the ask after a nit was cut. The COMMENT with concrete findings went
  out unchanged.
- **Post**: Recheck the head and the reviews first. Post with
  `gh api -X POST repos/Function-Health/<repo>/pulls/<n>/reviews --input
  <file>`, where the JSON holds the full head SHA as `commit_id`, `event`,
  `body`, and `comments` with `path`, `line` and `side: "RIGHT"`. Confirm
  each inline line is an added or context line in the diff first. Give
  Nickolas each review's `html_url`.
- **Another session**: When a second session reviews from the same
  directory, split the PRs by number and let each touch only its own files.

## Report

End with one table: repo and PR, the change in a few words, and the final state
(merged with SHA, open with the blocker, or closed).
