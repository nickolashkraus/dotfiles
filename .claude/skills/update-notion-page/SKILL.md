---
name: update-notion-page
description: >
  Update a Notion page with the Markdown contents of a local file.
disable-model-invocation: false
allowed-tools: Bash, Read, mcp__notion__notion-fetch, mcp__notion__notion-update-page
argument-hint: <file> <notion-page-link>
---

You are updating a Notion page with the contents of a local Markdown file.

`$ARGUMENTS` contains two space-separated values: the path to the local file
and the Notion page link.

## Step 1: Parse arguments

Extract the file path and Notion page link from `$ARGUMENTS`.

## Step 2: Clean the Markdown file

Run `clean_markdown.py` to remove 80-character line wraps and convert HTML
escape characters:

```
python scripts/clean_markdown.py --input <file>
```

If the script is not available, read the file directly.

Read the cleaned output from `dist/<filename>`. This is the content you will
use in subsequent steps.

## Step 3: Fetch the Notion page

Use the `notion-fetch` tool with the Notion page link to retrieve the current
page state.

## Step 4: Update the Notion page

Use the `notion-update-page` tool with the `replace_content` command to replace
the page content with the cleaned Markdown.

Strip the first H1 header from the content before replacing, since Notion uses
the page title for that. Update the page title if it differs from the H1.

Print the Notion page link when done.
