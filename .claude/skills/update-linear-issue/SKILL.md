---
name: update-linear-issue
description: >
  Update a Linear issue with the Markdown contents of a local file.
disable-model-invocation: false
allowed-tools: Bash, Read, mcp__linear__save_issue, mcp__linear__get_issue, mcp__linear__list_projects
argument-hint: <file> [linear-issue] [project]
---

You are updating a Linear issue with the contents of a local Markdown file.

`$ARGUMENTS` contains one to three space-separated values: the path to the
local file, an optional Linear issue identifier (e.g., EPD-123), and an
optional project name.

## Step 1: Parse arguments

Extract the file path, optional Linear issue identifier, and optional project
name from `$ARGUMENTS`.

If no issue identifier is provided, derive it from the filename (e.g.,
`epd-123.md` becomes `EPD-123`).

## Step 2: Clean the Markdown file

Run `clean_markdown.py` to remove 80-character line wraps and convert HTML
escape characters:

```
python scripts/clean_markdown.py --input <file>
```

If the script is not available, read the file directly.

Read the cleaned output from `dist/<filename>`. This is the content you will
use in subsequent steps.

## Step 3: Fetch the existing issue

Use the `get_issue` tool with the issue identifier to confirm the issue exists.

## Step 4: Resolve the project (if provided)

If a project name was provided in Step 1, use `list_projects` with the project
name as the `query` parameter. If a single result is returned, use it. If
multiple results are returned, pick the best match. If no results are returned,
report an error and stop.

Use the matched project's name or slug for the `project` field in Step 6.

## Step 5: Prepare the updates

Use the first H1 header (`# ...`) as the issue title. Use Title Case. If there
is no H1, do not update the title.

Remove the first H1 header from the cleaned Markdown. The remaining content is
the issue description.

## Step 6: Update the issue

Use the `save_issue` tool with the `id` parameter to update the issue:

- **title**: From Step 5 (if applicable).
- **description**: From Step 5.
- **project**: From Step 4 (if applicable).

Print the issue identifier when done.

@~/.claude/rules/meta-learning.md
