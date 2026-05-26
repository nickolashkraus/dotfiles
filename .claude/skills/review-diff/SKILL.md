---
name: review-diff
description: >
  Review the diff against the default branch for typos, bugs, and
  inconsistencies. TRIGGER when: user says "review my changes / diff", before
  commit or push, after substantive edits. SKIP: single file at a known path
  (use `review-file`); PR review (use the built-in `review` plugin).
disable-model-invocation: false
allowed-tools: Bash, Edit, Glob, Grep, Read
argument-hint: "[--staged]"
---

You are reviewing the diff against the default branch (not a single file).
Follow every step in order.

## Step 1: Parse arguments

Check if `$ARGUMENTS` contains `--staged`. If present, only review files that
are already staged.

## Step 2: Determine the default branch

```
git remote show origin | grep 'HEAD branch' | awk '{print $NF}'
```

## Step 3: Get the diff

If `--staged` was passed, diff only staged changes against the default branch
(`git diff --cached <default-branch>`).

Otherwise, diff all changes (staged, unstaged, and untracked) against the
default branch. If there are untracked files, read them in full. You need the
complete context to review.

If the total review surface is large (e.g., >1500 lines or >5 files), delegate
to an Explore sub-agent. When delegating typography fixes, specify that em dash
replacement is contextual (`:`, `;`, `,`, `(...)`, or sentence break depending
on the surrounding clause); never bulk-replace with a single character. Require
the sub-agent to report a sample of replacements for spot-check.

## Step 4: Review the diff

Go through every changed file. For each file, check for:

- **Typos**: Misspelled words, wrong variable names, copy/paste errors.
- **Bugs**: Logic errors, off-by-one mistakes, null/undefined risks, missing
  error handling, race conditions, resource leaks.
- **Inconsistencies**: Naming conventions that break from the rest of the file,
  mismatched types, formatting that diverges from surrounding code.
- **Security**: Injection risks, hardcoded secrets, overly broad permissions.

Read surrounding context in each file when needed to understand intent.

If you find issues, fix them directly. Do not just list them.

After fixing, re-run the diff to confirm your fixes are correct.

If the diff is clean, say so and move on.

Run CI (formatting, linting, tests, etc.) to ensure the changes will pass.
