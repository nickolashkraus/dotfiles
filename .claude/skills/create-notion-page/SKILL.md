---
name: create-notion-page
description: >
  Create a Notion page with the Markdown contents of a local file.
disable-model-invocation: false
allowed-tools: Bash, Read, mcp__notion__notion-fetch, mcp__notion__notion-create-pages
argument-hint: <file> [<notion-parent-page-link>]
---

You are creating a Notion page from the contents of a local Markdown file.
Follow @rules/notion.md for all formatting and content conventions.

`$ARGUMENTS` contains the path to the local file and, optionally, a Notion
parent page link separated by whitespace.

## Step 1: Parse arguments

Extract the file path and (optional) Notion parent page link from `$ARGUMENTS`.
If only one argument is given, treat it as the file path and create the page
without a parent (workspace-level private page).

## Step 2: Clean the Markdown file

Run `clean_markdown.py` to remove 80-character line wraps, convert HTML escape
characters, resolve reference-style links to inline links (Notion does not
render reference-style links), rewrite local file links to their Notion URLs
per the project's `manifest.yaml`, and convert Markdown footnotes to Notion
`<callout>` blocks (Notion does not render `[^label]` natively):

```
python scripts/clean_markdown.py --input <file> \
  --resolve-refs --rewrite-local-links --notion-footnotes
```

`--rewrite-local-links` walks up from `<file>` to the nearest `manifest.yaml`,
reads `notion.pages` (and any nested `children`), and replaces inline links
whose target resolves to a `file` entry with the corresponding `url`. Pass
`--manifest <path>` to override auto-detection.

`--notion-footnotes` strips each `[^label]` reference from the body and each
`[^label]: ...` definition from the bottom, inserting a `<callout>` block
carrying the footnote's content at the end of the paragraph that referenced it.

If the script is not available or no manifest exists yet, run without the flag
(or read the file directly). Local links pointing at unmapped files are left
unchanged.

Read the cleaned output from `dist/<filename>`. This is the content you will
use in subsequent steps.

## Step 3: Determine the title

Use the first H1 header (`# ...`) in the file as the page title. If there is no
H1, derive the title from the filename.

## Step 4: Prepare the content

Remove the first H1 header from the cleaned Markdown. The remaining content is
the page body.

## Step 5: Resolve the parent (only if a parent link was provided)

If a parent link was provided in Step 1, use the `notion-fetch` tool with the
Notion parent page link to retrieve the parent page ID. Otherwise, skip this
step.

**Placeholder Check**: If the fetched parent page is empty (no content) AND its
title closely matches the file's H1, the user may have intended to populate the
existing page rather than nest under it. Pause and confirm before creating.
Offer two options: (a) create a child page under the placeholder as instructed,
or (b) switch to `/update-notion-page` against the same URL to populate the
existing page directly.

## Step 6: Create the page

Use the `notion-create-pages` tool with:

- **title**: From Step 3.
- **content**: From Step 4.
- **parent**: The parent ID from Step 5 if available; otherwise omit the
  `parent` parameter so the page is created as a workspace-level private page
  the user can organize later.

Print the new Notion page link when done.

@~/.claude/rules/meta-learning.md
