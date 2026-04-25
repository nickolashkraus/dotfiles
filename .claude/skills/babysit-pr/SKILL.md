---
name: babysit-pr
description: >
  Monitors a PR for new commits, checks CI status, and deploys on approval.
disable-model-invocation: false
allowed-tools: Bash, Read, Glob, Grep
argument-hint: <pr-url-or-number> [deploy-script]
---

You are monitoring a pull request, checking CI, and deploying when approved.
Follow every step in order.

## Step 1: Parse arguments

Parse `$ARGUMENTS` for:

1. **PR identifier** (required): A GitHub PR URL or number. If a URL, extract
   the owner/repo and PR number. If a bare number, detect the repo from the
   current git remote.
2. **Deploy script** (optional): Path to a deploy script. If not provided, skip
   deployment steps and just report CI status.

If no PR identifier is provided, stop and tell the user:

```
Usage: /babysit-pr <pr-url-or-number> [deploy-script]
```

## Step 2: Check CI status

Fetch all checks on the PR:

```
gh pr checks <pr-number> --repo <owner/repo>
```

Classify every check as **pass**, **fail**, or **pending**.

- If any checks are **pending**, report which checks are still running and
  stop. The next loop iteration will re-check.
- If any checks have **failed**, go to Step 3.
- If all checks **pass**, go to Step 4.

## Step 3: Summarize failures

For each failed check, report:

- Check name
- Failure summary (from the check output or log if available)

Do not attempt to fix failures. Just report them and stop. The next loop
iteration will re-check after the developer pushes a fix.

## Step 4: All checks pass

Present the deployment plan:

1. Show the latest commit (SHA, message, author).
2. Show the PR title and branch.
3. If a deploy script was provided, show the deploy command that will be run.

Then ask: **"All CI checks pass. Deploy? [Waiting for approval]"**

Do not proceed until the user explicitly approves (e.g., "yes", "approved",
"deploy", "ship it").

## Step 5: Deploy

If no deploy script was provided, tell the user all checks pass and stop.

If a deploy script was provided:

1. Verify the script exists at the given path. If not, tell the user and stop.
2. Run the deploy script. If it has an interactive confirmation prompt, pipe
   `echo "y"` into it.
3. Report the result: success or failure with relevant output.

After a successful deploy, stop monitoring. The loop can be cancelled.

@~/.claude/rules/meta-learning.md
