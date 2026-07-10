---
name: create-linear-issue
description: Create a Linear issue from context.
---

You are creating a Linear issue from the current conversation context.
Follow ~/.codex/rules/linear.md for all formatting and content conventions.

the user-provided skill input contains two space-separated values:
`<team> <project>`.

## Step 1: Parse arguments

Extract the team name and project name from the user-provided skill input.

## Step 2: Draft the issue body

Draft the issue body from the current conversation context and write it to
`/tmp/linear-drafts/<short-slug>.md`. If the conversation has no obvious topic
to draft from, ask the user before writing a draft.

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

~/.codex/rules/meta-learning.md
