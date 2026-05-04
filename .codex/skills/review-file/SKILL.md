---
name: review-file
description: Review a file for typos, bugs, inaccuracies, and inconsistencies.
---

You are reviewing a file. The file path is the user-provided skill input.

## Step 1: Read the file

Read the file in full. You need complete context to review.

## Step 2: Review the file

Go through the entire file. Check for:

- **Typos**: Misspelled words, wrong variable names, copy/paste errors.
- **Bugs**: Logic errors, off-by-one mistakes, null/undefined risks, missing
  error handling, race conditions, resource leaks.
- **Inaccuracies**: Incorrect comments, misleading names, stale references,
  wrong values or constants.
- **Inconsistencies**: Naming conventions that break from the rest of the file,
  mismatched types, formatting that diverges from surrounding code, style
  violations.

Read surrounding files when needed to understand intent or verify correctness.

If the file is explicitly raw (e.g., `Scratch.md`, dump files, working notes
with `TBD`/`TODO` markers throughout), apply only typography rules that don't
change meaning (escape `<>`/`$`, replace em dashes, header levels, missing `#`
titles). Skip prose rewraps and period normalization that would amount to
re-writing.

## Step 3: Report findings

Present findings grouped by category. For each issue:

- State the line number and the problematic text.
- Explain what is wrong.
- Suggest the fix.

If you find issues, fix them directly. If the fix is ambiguous, prompt the user
for input. Lean more toward just fixing the issue.

If the file is clean, say so.

~/.codex/rules/meta-learning.md
