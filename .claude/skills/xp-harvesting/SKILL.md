---
name: xp-harvesting
description: >
  Open a batch of small, genuinely useful PRs across Nickolas's top Function
  Health repos (bug fixes, dead code, docs the code contradicts), one agent
  per repo, then squash-merge each once CI is green and fh-pulse approves.
  TRIGGER when: user says "xp harvesting", "harvest some XP", "PR sweep",
  "open easy PRs", "PRs that will get a Pulse approval", "quick wins across
  my repos". SKIP: a single known fix
  (use `ship` or `rip`); bot findings on an existing PR (use
  `fix-bot-reviews`).
disable-model-invocation: false
allowed-tools: Agent, SendMessage, Bash, Read, Grep, Glob
argument-hint: "[count] [repo ...]"
---

You are orchestrating a sweep: find one real defect per repo, open a PR for
each, verify every PR yourself, and merge the ones Pulse approves. Agents do
the finding and fixing; you keep verification and merging.

## Step 1: Pick the repos

If `$ARGUMENTS` names repos, use them. Otherwise rank by recent merged PRs
and take the top `count` (default 5):

```bash
gh search prs --author @me --owner Function-Health --merged \
  --created ">=<90 days ago>" --limit 300 --json repository \
  | jq -r '.[].repository.name' | sort | uniq -c | sort -rn | head -12
```

Skip infra repos (`sre-infra-terraform` and similar), where a merge can
change live infrastructure.

For each repo, record:

- **Default branch**: `gh api repos/Function-Health/<repo> --jq
  .default_branch`. Base PRs there.
- **Short link**: `ls ~/w | grep <repo-short>`. Use `~/w` links for every
  path, in your own commands and in agent briefs.
- **Merge rules**: `gh api repos/Function-Health/<repo>/rules/branches/<base>`.
  The org ruleset requires one approval (an `fh-pulse` APPROVED review
  satisfies it) plus the `pulse-review` and
  `sre-terraform-review-bot/risk-assessment` checks. Auto-merge is disabled
  org-wide, so `gh pr merge --auto` is not an option. Some repos also
  require the branch to be up to date with the base (member-app-middleware
  and membership-service do), which the classic protection endpoint does not
  show; a `BEHIND` merge state at green is the tell.

## Step 2: Fan out one agent per repo

Spawn one `general-purpose` agent per repo in a single message, named
`pr-<repo-short>`. Each brief must carry:

- **Goal**: One small PR (under ~100 added lines) fixing a verified defect:
  a bug with a test, dead code proven unreferenced, or a doc, docstring or
  comment the code contradicts. No churn or cosmetic rewording. Do not merge.
- **Avoid**: Migrations, Terraform, CI workflows and release gates, Datadog
  monitors, billing amounts, Stripe and payment behavior, entitlement
  grant/debit/refund behavior, auth, and any file touched by an open PR
  (`gh pr list -R <repo> --state open --limit 200 --json number,files`).
- **Dead-code proof**: Grep for string and dynamic references, tests,
  scripts, config and entry points before deleting.
- **Worktree**: `git -C ~/Function-Health/<repo> worktree add
  ~/Function-Health/<repo>/<branch> -b <branch> origin/<base>`, then
  `worktree-links` and work through the `~/w` link. Branch names are short
  hyphenated descriptions, no Linear slug.
- **Local CI**: The full suite exactly as `.github/workflows/*` runs it,
  through the project runner. For a bug fix, break the fix and watch the test
  fail. Run `pulse-review` once for runtime changes; skip it for docs. In
  member-journey-services, run pytest under `env -u XDG_CONFIG_HOME`: the
  release-gate tests move `HOME` but not `XDG_CONFIG_HOME`, so their
  `git config --global` writes otherwise land in the real
  `~/.config/git/config`, which is tracked in dotfiles.
- **Commit and PR**: Imperative subject, 50 characters or fewer, no
  attribution. PR title matches; body is one or two sentences opening with
  a declarative verb.
- **Report promptly**: Return the PR URL, the change in two lines, local CI
  results, and any defects found but left out. Agents tend to miss their own
  background-completion notices and go silent for an hour. Tell them not to
  use `Monitor` or `run_in_background` for the test suite, since "run it in
  the foreground" alone did not stop two of five from idling on a Monitor.
  Send a status ping to any agent quiet for 20 minutes.

## Step 3: Verify each PR

When an agent reports, read `gh pr diff` and check its central claim with
one grep against `origin/<base>`: the route prefix, the absent references,
the real signature. An agent's report is a claim, not evidence.

## Step 4: Get merge approval once

`~/.claude/hooks/confirm-risky.py` blocks `gh pr merge` and `gh pr close`
until the user approves the exact command. An instruction like "once green,
squash and merge" does not count. Show the first merge command and ask
whether the approval covers the whole batch under these criteria: all
checks pass, `fh-pulse` approved, and no open bot review comments. On
approval, prefix each command with `# user-approved: `.

## Step 5: Run a merge loop per PR

Run this in the background for each verified PR, with the approval prefix
on the first line so the hook sees the merge command:

```bash
# user-approved: gh pr merge <PR> -R Function-Health/<repo> --squash --delete-branch=false
R=Function-Health/<repo>; PR=<PR>
for attempt in 1 2 3; do
  [ "$(gh pr view $PR -R $R --json mergeStateStatus -q .mergeStateStatus)" = "BEHIND" ] && { gh pr update-branch $PR -R $R --rebase >/dev/null 2>&1; sleep 30; }
  head=$(gh pr view $PR -R $R --json headRefOid -q .headRefOid)
  for i in $(seq 1 60); do
    out=$(gh pr view $PR -R $R --json statusCheckRollup,mergeStateStatus,headRefOid)
    [ "$(echo "$out" | jq -r .headRefOid)" != "$head" ] && break
    pending=$(echo "$out" | jq '[.statusCheckRollup[]|select((.status // "COMPLETED")!="COMPLETED" or (.state // "")=="PENDING")]|length')
    bad=$(echo "$out" | jq '[.statusCheckRollup[]|select(((.name // .context)|test("pr-plan-prod")) and (.conclusion=="ACTION_REQUIRED")|not)|select((.conclusion // .state) as $c|["FAILURE","ERROR","CANCELLED","TIMED_OUT","ACTION_REQUIRED"]|index($c))]|length')
    pulse=$(echo "$out" | jq -r '[.statusCheckRollup[]|select((.name // .context)=="pulse-review")|(.conclusion // .state)]|first // "none"')
    ms=$(echo "$out" | jq -r .mergeStateStatus)
    [ "$bad" != "0" ] && { echo "attempt $attempt: failing checks"; echo "$out" | jq -r '.statusCheckRollup[]|"\(.name // .context)=\(.conclusion // .state)"'; exit 1; }
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

- **Busy bases**: `member-app-middleware` gets a commit on `main` every 20
  to 30 minutes, and checks take about 10, so a PR can fall behind at green
  more than once. The loop rebases and retries up to three times; restart it
  if all three lose the race. Merging one PR in a strict repo puts its
  siblings behind, which the loop handles the same way.
- **Prod plan gates**: A Cloud Build `*-pr-plan-prod` check sitting at
  `ACTION_REQUIRED` is a manual approval gate, not a failure, and is not
  required. Prior PRs merged past it.
- **Pulse owner gate**: `pulse-review` failing with zero findings means
  Pulse rated the PR medium-high or above and wants a code owner. Read
  `risk=` in the review body. Never add `/pulse:skip-review` to get past
  it. Report the risk rationale, check it against the code, and let the
  user choose between getting an owner's approval and closing the PR.
- **Approved with a should-fix**: Pulse can approve and still leave an
  inline should-fix comment, so the loop checks for open review threads
  rather than trusting the approval. Fix it with an amended commit; the old
  thread goes outdated and the loop ignores it. The `sleep 30` gives Pulse
  time to post inline comments after its check turns green.
- **Stale quotes in docs**: When a doc quotes a message whose content is
  now wrong, correct the quote and add a note that it was updated. A note
  beside an untouched stale quote still reads as contradictory guidance,
  and Pulse flags it.

## Step 6: Offer the follow-ups

Agents report defects they left out of scope. Verify each one, then offer it
as its own PR. When a follow-up touches the same file as an open PR in the
sweep, have its agent wait for that PR to merge and branch from the new
base, or the two will conflict.

## Step 7: Clean up

After the user agrees, remove each worktree the sweep created:

1. `git -C <worktree> status --porcelain` must be empty.
2. `git -C <worktree> cherry origin/<base> HEAD` must print only `-` lines.
   A rebase done through `gh pr update-branch` rewrites the remote branch
   and leaves the old commit locally, so it shows as unpushed even though
   its change is on the base.
3. `git -C ~/Function-Health/<repo> worktree remove <worktree>`, never
   `--force`.
4. `git branch -D <branch>` for merged PRs only. Keep a closed PR's branch
   so it can be reopened. Leave remote branches alone.
5. Run `worktree-links`.

## Report

End with one table: repo and PR, the change in a few words, and the final
state (merged with SHA, open with the blocker, or closed).
