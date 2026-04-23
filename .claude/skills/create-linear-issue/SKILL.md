---
name: create-linear-issue
description: >
  Create a Linear issue with the Markdown contents of a local file.
disable-model-invocation: false
allowed-tools: Bash, Read, mcp__linear__save_issue, mcp__linear__list_projects
argument-hint: <file> <team> <project>
---

You are creating a Linear issue from the contents of a local Markdown file.
Follow @rules/linear.md for all formatting and content conventions.

`$ARGUMENTS` contains three space-separated values: the path to the local file,
the Linear team name, and the Linear project name.

## Step 1: Parse arguments

Extract the file path, team name, and project name from `$ARGUMENTS`.

## Step 2: Clean the Markdown file

Run `clean_markdown.py` to remove 80-character line wraps and convert HTML
escape characters:

```
python scripts/clean_markdown.py --input <file>
```

If the script is not available, read the file directly.

Read the cleaned output from `dist/<filename>`. This is the content you will
use in subsequent steps.

## Step 3: Resolve the project

Use `list_projects` with the project name from Step 1 as the `query` parameter.
If a single result is returned, use it. If multiple results are returned, pick
the best match. If no results are returned, report an error and stop.

Use the matched project's name or slug for the `project` field in Step 6.

## Step 4: Determine the title

Use the first H1 header (`# ...`) in the file as the issue title. Use Title
Case. If there is no H1, derive the title from the filename.

## Step 5: Prepare the description

Remove the first H1 header from the cleaned Markdown. The remaining content is
the issue description.

## Step 6: Create the issue

Use the `save_issue` tool to create the issue with:

- **title**: From Step 4.
- **description**: From Step 5.
- **team**: The team name from the arguments.
- **project**: The resolved project from Step 3.
- **state**: Todo.

Print the issue identifier (e.g., EPD-123) when done.
