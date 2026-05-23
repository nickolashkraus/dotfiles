---
name: update-linear-issue
description: Update a Linear issue from context.
disable-model-invocation: false
allowed-tools: Bash, Read, mcp__linear__save_issue, mcp__linear__get_issue
argument-hint: <linear-issue>
---

You are updating a Linear issue from the current conversation context.
Follow @rules/linear.md for all formatting and content conventions.

`$ARGUMENTS` contains one value: a Linear issue identifier (e.g., EPD-123).

## Step 1: Parse arguments

Extract the Linear issue identifier from `$ARGUMENTS`.

## Step 2: Draft the issue body

Draft the updated issue body from the current conversation context and write it
to `/tmp/linear-drafts/<issue-id>.md`. If the conversation has no obvious topic
to draft from, ask the user before writing a draft.

## Step 3: Unwrap the draft

Linear renders Markdown but treats hard line breaks as `<br>`, so a draft that
hard-wraps at <80 characters renders as a wrapped block on Linear. Before
sending, unwrap paragraphs and list items into single lines.

Run `clean_markdown.py` against the draft and use the cleaned output as the
description payload in Step 6. If the script is not available, unwrap manually:
each paragraph and each bullet must be one unbroken line.

```
python3 /Users/nickolas/nickolashkraus/agent-os/master/scripts/clean_markdown.py \
  --input /tmp/linear-drafts/<issue-id>.md \
  --output /tmp/linear-drafts/clean/
```

## Step 4: Strip internal references

Per `rules/general.md`, external content must never reference internal or
local-only documents. Before sending, scan the cleaned draft and remove any of
the following:

- Paths under `~/nickolashkraus/` or `agent-os/` (e.g., `tasks/009...md`,
  `investigations/...`, `notes/daily/...`, `final.md`).
- File paths that are not in a shared repo readers can open (private scratch
  notes, working docs, manifests).
- Bare references like "the runbook" or "the spec" that only resolve to an
  internal file.

When the underlying detail matters, inline a one-sentence summary in place of
the reference. References to shared repo paths (e.g.,
`enterprise-service/app/...`) are fine; those resolve for teammates.

## Step 5: Fetch the existing issue

Use the `get_issue` tool with the issue identifier to confirm the issue exists.

## Step 6: Update the issue

Use the `save_issue` tool with the `id` parameter to update the issue with:

- **title**: From context.
- **description**: The output from Step 4.

Print the issue identifier when done.

@~/.claude/rules/meta-learning.md
