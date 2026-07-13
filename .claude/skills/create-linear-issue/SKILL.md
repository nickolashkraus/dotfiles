---
name: create-linear-issue
description: >
  Create a Linear issue from context. TRIGGER when: user asks to
  file/open/create a Linear issue or ticket. SKIP: updating an existing issue
  (use `update-linear-issue`).
disable-model-invocation: false
allowed-tools: Bash, Read, mcp__linear__save_issue, mcp__linear__list_projects
argument-hint: "<team> <project>"
---

You are creating a Linear issue from the current conversation context.
Follow @rules/linear.md for all formatting and content conventions.

`$ARGUMENTS` contains one or two space-separated values: `<team>` or
`<team> <project>`.

## Step 1: Parse arguments

Extract the team name (and, if provided, the project name) from `$ARGUMENTS`.

If only `<team>` is provided, list active projects for that team
(`list_projects` with `team=<team>`) and ask the user which to use. Do not
guess. Do not default to a project.

## Step 2: Draft the issue body

Draft the issue body from the current conversation context and write it to
`/tmp/linear-drafts/<short-slug>.md`. If the conversation has no obvious topic
to draft from, ask the user before writing a draft.

Write the draft with unwrapped paragraphs (one line per paragraph and per
bullet). The `lint-outbound.py` hook lints the `/tmp/linear-drafts` Write
itself and rejects hard-wrapped paragraphs, so a <80-column draft never reaches
disk; Step 3's `clean_markdown.py` run then acts as a no-op verification pass.

The `/tmp` draft is required even if a draft already exists elsewhere in the
conversation (e.g., in a working doc). It serves as the canonical pre-creation
artifact and lets the user diff the as-saved description against the as-sent
payload. Do not skip this step.

## Step 3: Unwrap the draft

Linear renders Markdown but treats hard line breaks as `<br>`, so a draft that
hard-wraps at <80 characters renders as a wrapped block on Linear. Before
sending, unwrap paragraphs and list items into single lines.

Run `clean_markdown.py` against the draft and use the cleaned output as the
description payload in Step 6. If the script is not available, unwrap manually:
each paragraph and each bullet must be one unbroken line.

```
python3 ~/nickolashkraus/agent-os/master/scripts/clean_markdown.py \
  --input /tmp/linear-drafts/<slug>.md \
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

## Step 4.5: Typography pre-flight

The `lint-outbound.py` hook rejects `save_issue` payloads with typography
violations, so catch them before sending. Scan the cleaned draft against the
checklist at the top of `rules/typography.md`, especially
capitalize-after-colon. A lowercase word after a label or lead-in colon
(`**Element**: ...`, line-initial links, bold callouts) is a violation unless
the next token is a code span, path, number, or URL; a colon joining two
clauses inside a flowing sentence keeps lowercase. Fix violations in the
cleaned draft, not just the payload, so the on-disk artifact matches what was
sent.

## Step 5: Resolve the project

Use `list_projects` with the project name from Step 1 as the `query` parameter.
If a single result is returned, use it. If multiple results are returned, pick
the best match. If no results are returned, report an error and stop.

Use the matched project's name or slug for the `project` field in Step 6.

## Step 6: Create the issue

Use the `save_issue` tool to create the issue with:

- **title**: From context.
- **description**: The output from Step 4.
- **team**: The team name from the arguments.
- **project**: The resolved project from Step 5.
- **state**: Todo. Exception: Retroactive issues documenting already-shipped
  work use Done (and typically set `assignee` to the PR author and attach the
  PR via `links`).
- **priority**: Always evaluate and set one; never leave No priority. Pick from
  context and surface the rationale in one sentence in the chat reply:
  - **Urgent (1)**: Active member/revenue impact or a blocked release.
  - **High (2)**: Prod defect or noise that degrades monitoring or masks
    regressions, security gaps, or anything time-boxed by an ongoing rollout.
  - **Medium (3)**: Real defect with a workaround or no user-facing impact, and
    standard feature work.
  - **Low (4)**: Cleanup, nice-to-have, documentation.

Print the issue identifier (e.g., EPD-123) when done.
