---
name: review
description: >
  Reviews the diff against the default branch for typos, bugs, and
  inconsistencies.
disable-model-invocation: false
allowed-tools: Bash, Edit, Glob, Grep, Read
argument-hint: [--staged]
---

You are reviewing a set of changes. Follow every step in order.

## Step 1: Parse arguments

Check if `$ARGUMENTS` contains `--staged`. If present, only review files that
are already staged.

## Step 2: Determine the default branch

```
git remote show origin | grep 'HEAD branch' | awk '{print $NF}'
```

## Step 3: Get the diff

If `--staged` was passed, diff only staged changes against the default branch
(`git diff --cached`).

Otherwise, diff all changes (staged, unstaged, and untracked) against the
default branch. If there are untracked files, read them in full. You need the
complete context to review.

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

@~/.claude/rules/meta-learning.md
