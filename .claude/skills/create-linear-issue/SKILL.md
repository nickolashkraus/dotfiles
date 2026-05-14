---
name: create-linear-issue
description: Create a Linear issue from context.
disable-model-invocation: false
allowed-tools: Bash, Read, mcp__linear__save_issue, mcp__linear__list_projects
argument-hint: <team> <project>
---

You are creating a Linear issue from the current conversation context.
Follow @rules/linear.md for all formatting and content conventions.

`$ARGUMENTS` contains two space-separated values: `<team> <project>`.

## Step 1: Parse arguments

Extract the team name and project name from `$ARGUMENTS`.

## Step 2: Draft the issue body

Draft the issue body from the current conversation context and write it to
`/tmp/linear-drafts/<short-slug>.md`. If the conversation has no obvious topic
to draft from, ask the user before writing a draft.

The `/tmp` draft is required even if a draft already exists elsewhere in the
conversation (e.g., in a working doc). It serves as the canonical pre-creation
artifact and lets the user diff the as-saved description against the as-sent
payload. Do not skip this step.

## Step 3: Resolve the project

Use `list_projects` with the project name from Step 1 as the `query` parameter.
If a single result is returned, use it. If multiple results are returned, pick
the best match. If no results are returned, report an error and stop.

Use the matched project's name or slug for the `project` field in Step 4.

## Step 4: Create the issue

Use the `save_issue` tool to create the issue with:

- **title**: From context.
- **description**: From context.
- **team**: The team name from the arguments.
- **project**: The resolved project from Step 3.
- **state**: Todo.

Print the issue identifier (e.g., EPD-123) when done.

@~/.claude/rules/meta-learning.md
