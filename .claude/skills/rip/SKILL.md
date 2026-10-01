---
name: rip
description: >
  Commit and open a pull request at maximum speed, skipping review, Pulse and
  the local test suite. For low-blast-radius changes only. TRIGGER when: user
  says "rip it", "rip this", "fast PR", "no CI, fast". SKIP: anything that
  fails the blast-radius test below (use `ship`).
disable-model-invocation: false
allowed-tools: Bash, Read, Edit, Write, Skill
argument-hint: "[--no-pr] [linear-issue]"
---

You are shipping a change as fast as it can safely go. Speed comes from
skipping process, never from skipping verification.

Parse `$ARGUMENTS`:

- `--no-pr`: Push straight to the default branch, no branch and no PR.
- Anything else is a Linear issue slug.

## Step 1: Blast-radius test

Size the change by what it can break, not by how many lines it touches. A
one-line edit to shared Prod infrastructure is a small diff with wide reach.

**Abort and tell the user to run `/ship` instead** when the change touches any
of these:

- A migration, backfill, or anything that runs against Prod rows
- Auth, secrets, IAM, or any permission widening
- A webhook, event handler, or consumer where idempotency matters
- A Terraform resource **removal**, `moved` block, or state operation
- Another contributor's branch
- Anything whose effect cannot be reverted by a revert commit

Rip freely when the change is a config flip, a tfvars toggle that another
apply or review still gates, a comment, a doc, a rename, a constant, or a
test-only edit.

State the verdict in one line, then continue or stop. Do not deliberate in
prose; if it is genuinely ambiguous, it is not a rip.

## Step 2: The two checks that never get skipped

These cost seconds and are the failures that actually hurt:

1. **Read before you overwrite.** Read the file, and check `git status` for
   the user's own staged or unstaged work before staging anything. Staged
   changes are deliberate human work. Ask, never infer.
2. **Verify every external contract you name.** Read the field, route, column,
   flag or topic from the SDK, the schema, the type stubs, or the source. A
   plausible name that does not exist is the expensive failure mode, because
   nothing downstream questions it.

## Step 3: Commit and push

Follow @~/.claude/rules/git.md for the branch name, commit subject and PR
body. Briefly:

- Branch is the lowercase Linear slug plus a short description, never the bare
  slug.
- Commit subject is `SLUG: Exact Linear Issue Title` when a Linear issue
  applies, otherwise a clean imperative subject. Never a fabricated slug.
- No AI attribution of any kind on the commit or the PR.

Do not run `review-diff`, `pulse-review`, the repo lint suite or the test
suite. The user has accepted that cost.

If `--no-pr`: `git push`. If the remote moved, fetch and rebase (never
merge), then push again. Stop here.

Otherwise push the branch and open the PR with `gh pr create`. Scale the body
to the change: a trivial change gets a single declarative sentence, and
anything with a non-obvious reason gets that reason plus a `## References`
link to the Linear issue. Use `--body-file` for anything longer than one
line.

**Never merge.** Invoking `rip` approves the push and the PR, nothing beyond
that.

## Step 4: Report

Two lines maximum: the PR URL and what was skipped. Say plainly that local
verification did not run, so the user knows CI is the first real gate.

## Meta-learning

Apply @~/.claude/rules/meta-learning.md. If a rip produced a broken PR, the
blast-radius list in Step 1 is probably missing a category. Add it.
