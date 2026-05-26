---
name: release
description: >
  Cut a release for a Function Health service. Gathers PRs, creates the release
  branch, Notion doc, and deployment announcement. TRIGGER when: user says "cut
  release", "release X", "do the release", or wants to bundle merged dev PRs
  into a release branch with a Notion doc and Slack announcement.
disable-model-invocation: false
allowed-tools: Bash, Read, Edit, Write, Glob, Grep, Agent, mcp__linear__list_issues, mcp__linear__list_issue_statuses, mcp__linear__get_issue, mcp__notion__notion-create-pages, mcp__notion__notion-update-page, mcp__notion__notion-fetch, mcp__claude_ai_Slack__slack_send_message_draft
argument-hint: "[--date YYYY-MM-DD] [--team TEAM] [--notion URL] [--title TITLE] [--cc USER_IDS_OR_HANDLES]"
---

You are cutting a release for a Function Health service.
Follow every step in order.

All release content (PR titles and descriptions, Notion doc, Slack
announcement, daily task file, commit messages) must follow
`@~/.claude/rules/typography.md` and `@~/.claude/rules/git.md`. In
particular: no em dashes, no smart quotes, hard-wrap prose at ~80
columns, lead PR descriptions with a declarative verb (no "This PR
does..."), and follow the Larger Changes structure (`## Overview`,
`## PRs`, `## Alembic Migrations`, `## Cross-Service Dependencies`,
`## New Secrets`, `## Notes`).

## Step 1: Determine service and date

Detect the service from the current working directory (e.g.,
`transaction-service` from `~/Function-Health/transaction-service`).

Parse `$ARGUMENTS` for:

- `--date YYYY-MM-DD`: Release date. Default to today.
- `--team TEAM`: Linear team slug (e.g., `BYB`). Default to detecting
  from the repo's Linear project conventions.
- `--notion URL`: Notion page URL for the release document (Step 6).
- `--title TITLE`: Release title (e.g., "PPP v1 - Bug Fixes"). If
  not provided, ask the user for a short release title.
- `--cc USER_IDS_OR_HANDLES`: Comma-separated list of Slack user IDs (`U...`)
  or `@handles` to cc on the deployment announcement (Step 7). Defaults to
  empty. Pass `--cc ""` to omit the cc line entirely.

Determine the default branch and `{owner}/{repo}`:

```
git remote show origin | grep 'HEAD branch' | awk '{print $NF}'
gh repo view --json nameWithOwner --jq '.nameWithOwner'
```

## Step 2: Gather PRs from Linear

Query Linear for issues in "Pending Deploy" status on the team:

```
list_issues(team=<team>, state="Pending Deploy")
```

Filter to issues whose attachments link to PRs in `{owner}/{repo}`.
Present as a table:

| Linear   | PR   | Title |
| -------- | ---- | ----- |

### Cross-check with unreleased merge commits

```
git log origin/main..origin/dev --merges --oneline
```

Match by PR number (`(#NNNN)` suffix). Flag merge commits on `dev`
not in the Linear "Pending Deploy" list. Present discrepancies.

Ask the user to confirm which issues to include. For each, find its
merge commit SHA on `dev`:

```
git log origin/dev --merges --oneline --grep="#<pr-number>"
```

## Step 3: Determine labels

For each PR, check for:

- Alembic migrations (files under `alembic/versions/`).
- New secrets/env vars (`os.environ` / `os.getenv` not on `main`).

Report which labels (`AlembicMigration`, `NewSecret`) are needed.

## Step 4: Create release branch and PR

```
git checkout main && git pull
git checkout -b release/<date>.00
git cherry-pick -m 1 <merge-sha>  # for each PR
git push -u origin release/<date>.00
gh pr create --base main \
  --title "Release <date>.00 (<release-title>)" \
  --label release
```

Add `AlembicMigration`/`NewSecret` labels if applicable.

## Step 5: Wait for CI

Run `/fix-ci-release <pr-number>` to monitor CI and triage bot
comments. This creates a Linear issue for findings instead of
committing fixes directly (release branches only accept cherry-
picked merge commits).

## Step 6: Notion release document

If `--notion` was not provided, ask for the Notion page URL. The
user creates the page manually (e.g., duplicate a previous release)
so it appears in the database view. MCP-created pages do not appear
in Notion database views.

Read the template from `@templates/notion.md` and populate it with
the release data. Update the page using `notion-update-page`.

## Step 7: Post deployment announcement

Read the template from `@templates/slack.md` and populate it. Send
as a draft using `slack_send_message_draft`.

## Step 8: Create daily task file

Read the template from `@templates/daily-task.md` and populate it.
Write to `~/nickolashkraus/agent-os/tasks/daily/<date>.md`.

## Step 9: Deploy

When the user is ready:

1. Confirm CI is green and all secrets are set.
2. Merge the release PR to `main`.
3. Remind user to apply Alembic migrations (if applicable).
4. Remind user to monitor deployment and check Prod logs.

## Step 10: Summarize

Print: release PR URL, Notion doc URL, PRs included, and any
outstanding items.
