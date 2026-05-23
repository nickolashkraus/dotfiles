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

## Step 3: Strip internal references

Per `rules/general.md`, external content must never reference internal or
local-only documents. Before publishing, scan the cleaned file and remove any
of the following:

- Paths under `~/nickolashkraus/` or `agent-os/` (e.g., `tasks/...md`,
  `investigations/...`, `notes/daily/...`, `final.md`) that did not get
  rewritten to a Notion URL by `--rewrite-local-links`.
- File paths that are not in a shared repo readers can open (private scratch
  notes, working docs, manifests).
- Bare references like "the runbook" or "the spec" that only resolve to an
  internal file.

When the underlying detail matters, inline a one-sentence summary in place of
the reference. References to shared repo paths (e.g., `enterprise-service/...`)
or fully-rewritten Notion URLs are fine.

## Step 4: Fetch the Notion page

Use the `notion-fetch` tool with the Notion page link to retrieve the current
page state.

## Step 5: Update the Notion page

Use the `notion-update-page` tool with the `replace_content` command to replace
the page content with the cleaned Markdown.

Strip the first H1 header from the content before replacing, since Notion uses
the page title for that. Update the page title if it differs from the H1.

Print the Notion page link when done.

@~/.claude/rules/meta-learning.md
