---
name: update-linear-issue
description: Update a Linear issue from context.
---

You are updating a Linear issue from the current conversation context.
Follow ~/.codex/rules/linear.md for all formatting and content conventions.

the user-provided skill input contains one value: a Linear issue identifier (e.g., EPD-123).

## Step 1: Parse arguments

Extract the Linear issue identifier from the user-provided skill input.

## Step 2: Draft the issue body

Draft the updated issue body from the current conversation context and write it
to `/tmp/linear-drafts/<issue-id>.md`. If the conversation has no obvious topic
to draft from, ask the user before writing a draft.

## Step 3: Fetch the existing issue

Use the `get_issue` tool with the issue identifier to confirm the issue exists.

## Step 4: Update the issue

Use the `save_issue` tool with the `id` parameter to update the issue with:

- **title**: From context.
- **description**: From context.

Print the issue identifier when done.

~/.codex/rules/meta-learning.md
