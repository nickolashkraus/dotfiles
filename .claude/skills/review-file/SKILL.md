---
name: review-file
description: Review a file for typos, bugs, inaccuracies, and inconsistencies.
disable-model-invocation: false
allowed-tools: Bash, Edit, Glob, Grep, Read
argument-hint: <file>
---

You are reviewing a file. The file path is `$ARGUMENTS`.

If `$ARGUMENTS` is a directive like "all unstaged files", "all changed files",
or "all files in the diff", resolve it to a concrete list via `git` (e.g., `git
status --short`, `git diff --name-only`) and review each file in turn. Apply
Steps 1-3 per file and produce a per-file findings report.

## Step 1: Read the file

Read the file in full. You need complete context to review.

Resolve the path relative to the current working directory first. Do not
substitute a same-named file from `~/.claude/` (or any other ancestor location)
just because it exists. If the argument is a relative path like
`.claude/rules/git.md`, prepend the cwd, not `$HOME`. Confirm the resolved path
with the user before reviewing if there is any ambiguity.

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

@~/.claude/rules/meta-learning.md
