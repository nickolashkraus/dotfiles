---
name: create-notion-page
description: >
  Create a Notion page with the Markdown contents of a local file.
disable-model-invocation: false
allowed-tools: Bash, Read, mcp__notion__notion-fetch, mcp__notion__notion-create-pages
argument-hint: <file> <notion-parent-page-link>
---

You are creating a Notion page from the contents of a local Markdown file.
Follow @rules/notion.md for all formatting and content conventions.

`$ARGUMENTS` contains two space-separated values: the path to the local file
and the Notion parent page link.

## Step 1: Parse arguments

Extract the file path and Notion parent page link from `$ARGUMENTS`.

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

Use the first H1 header (`# ...`) in the file as the page title. If there is no
H1, derive the title from the filename.

## Step 4: Prepare the content

Remove the first H1 header from the cleaned Markdown. The remaining content is
the page body.

## Step 5: Fetch the parent page

Use the `notion-fetch` tool with the Notion parent page link to retrieve the
parent page ID.

## Step 6: Create the page

Use the `notion-create-page` tool to create a new child page under the parent
with:

- **title**: From Step 3.
- **content**: From Step 4.

Print the new Notion page link when done.
