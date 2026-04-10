---
name: pr
description: Creates a branch and pull request from the current commit(s).
disable-model-invocation: false
allowed-tools: Bash, Read
argument-hint: [linear-issue]
---

You are creating a pull request. Follow every step in order.

## Step 1: Determine the default branch

```
git remote show origin | grep 'HEAD branch' | awk '{print $NF}'
```

## Step 2: Understand the changes

Run `git log` and `git diff` against the default branch to understand all
commits that will be included in the pull request.

## Step 3: Create the branch and push

If already on a non-default branch, push it. Otherwise:

1. Determine the branch name:
   - If a Linear issue was passed (`$ARGUMENTS`), use it as the branch name
     (e.g., `EPD-1337`).
   - Otherwise, derive a short descriptive name from the changes.
2. Create the branch and push.

## Step 4: Create the pull request

Create the pull request using `gh pr create` against the default branch:

- If a Linear issue was provided, prefix the pull request title (e.g.,
  `EPD-1337: Add input validation`).
- Write the description following the pull request rules from
  @~/.claude/rules/git.md:
  - Scale the description with the complexity of the change.
  - Trivial: Single sentence or empty body.
  - Small to medium: Declarative summary, code snippets if helpful,
    `**NOTE**` blocks for secondary context.
  - Large: `## Overview`, then `## Implementation Details`, `## Testing`,
    `## References` as needed.
- Do not add boilerplate sections the change does not warrant.

Print the pull request URL when done.
