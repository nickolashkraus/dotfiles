---
name: create-linear-issue
description: >
  Create a Linear issue with the Markdown contents of a local file.
disable-model-invocation: true
allowed-tools: Bash, Read, mcp__linear__save_issue, mcp__linear__list_teams
argument-hint: <file> <linear-project>
---

You are creating a Linear issue from the contents of a local Markdown file.

`$ARGUMENTS` contains two space-separated values: the path to the local file
and the Linear project name.

## Step 1: Parse arguments

Extract the file path and Linear project name from `$ARGUMENTS`.

## Step 2: Clean the Markdown file

Run `clean_markdown.py` to remove 80-character line wraps and convert HTML
escape characters:

```
python scripts/clean_markdown.py --input <file>
```

If the script is not available, read the file directly.

Read the cleaned output from `dist/<filename>`. This is the content you will
use in subsequent steps.

## Step 3: Determine the title

Use the first H1 header (`# ...`) in the file as the issue title. Use Title
Case. If there is no H1, derive the title from the filename.

## Step 4: Prepare the description

Remove the first H1 header from the cleaned Markdown. The remaining content is
the issue description.

## Step 5: Get the team

Use the `list_teams` tool to find available teams. Use the first team if there
is only one.

## Step 6: Create the issue

Use the `save_issue` tool to create the issue with:

- **title**: From Step 3.
- **description**: From Step 4.
- **project**: The Linear project from the arguments.
- **team**: From Step 5.
- **state**: Todo.

Print the issue identifier (e.g., EPD-123) when done.
