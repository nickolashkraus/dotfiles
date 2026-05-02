---
name: remote
description: >
  Polls for remote tasks submitted via Obsidian (iOS) and executes them
  on macOS. Pair with /loop for continuous polling.
disable-model-invocation: false
allowed-tools: >
  Bash, Edit, Glob, Grep, Read, Write, Agent,
  mcp__claude_ai_Slack__slack_send_message,
  mcp__linear__save_issue,
  mcp__notion__notion-update-page
argument-hint: >
  [poll | list | clean]
---

# Remote

Polls `~/nickolashkraus/agent-os/master/tasks/remote/` for task files
submitted from Obsidian on iOS. Each task is a Markdown file with
a prompt and metadata. Pair with `/loop` for continuous polling.

## Usage

```
/remote              Poll once and execute any pending tasks.
/remote poll         Same as above.
/remote list         List all tasks and their statuses.
/remote clean        Remove completed and failed task files.
```

Continuous polling (self-paced):

```
/loop /remote
```

## Task format

Each task is a Markdown file in `tasks/remote/`. The filename is
the task slug (e.g., `deploy-staging.md`, `fix-typo-in-readme.md`).

```markdown
---
status: pending
created: 2026-04-27T10:30:00
project: nickolashkraus
---

The prompt for Claude goes here. Write it exactly as you would
type it into Claude Code.
```

### Fields

- **status**: `pending`, `in-progress`, `blocked`, `done`, `failed`.
- **created**: ISO 8601 timestamp.
- **project**: The directory name under `~/nickolashkraus/` (or
  `~/Function-Health/`) where the task should be executed.

### Blocked tasks

When an agent needs clarification, it sets `status: blocked` and
appends a `## Blocked` section with the question:

```markdown
---
status: blocked
created: 2026-04-27T10:30:00
project: nickolashkraus
---

The original prompt.

## Blocked

Which database should I run the migration against, Dev or Prod?
```

To unblock, add an `## Answer` section and change the status back
to `pending`:

```markdown
---
status: pending
created: 2026-04-27T10:30:00
project: nickolashkraus
---

The original prompt.

## Blocked

Which database should I run the migration against, Dev or Prod?

## Answer

Dev.
```

The next poll picks it up and continues with the original prompt
plus the Q&A context.

### Result

When a task completes, the skill updates the frontmatter and appends
a result block:

```markdown
---
status: done
created: 2026-04-27T10:30:00
completed: 2026-04-27T10:35:00
project: nickolashkraus
---

The original prompt.

## Result

A concise summary of what was done.
```

Failed tasks get `status: failed` and a `## Result` block explaining
the error.

## Step 1: Parse arguments

Parse `$ARGUMENTS` to determine the subcommand. Default to `poll`
if no arguments are provided.

## Step 2: Execute subcommand

### poll (default)

1. List all `.md` files in `tasks/remote/`.
2. Filter for files with `status: pending` in the frontmatter.
3. Sort by `created` timestamp (oldest first).
4. For each pending task:
   a. Update `status` to `in-progress`.
   b. Read the `project` field to determine the working directory.
      - If `project` starts with `FH:` or `fh:`, use
        `~/Function-Health/<rest>`.
      - Otherwise, use `~/nickolashkraus/<project>/master` (assumes
        worktree layout). If that path does not exist, try
        `~/nickolashkraus/<project>`.
   c. Extract the full file content after the frontmatter closing
      `---`. This includes the original prompt and, for unblocked
      tasks, any `## Blocked` and `## Answer` sections that provide
      additional context.
   d. Execute the task by spawning an Agent in the target project
      directory. Pass the full content to the agent.
   e. If the agent needs clarification and cannot proceed:
      - Set `status` to `blocked`.
      - Append a `## Blocked` section with the question.
      - Do not append a `## Result` section.
   f. When the agent completes, update the task file:
      - Set `status` to `done` (or `failed` if the agent errored).
      - Add `completed: <ISO 8601>` to the frontmatter.
      - Append a `## Result` section with the agent's summary.
5. After all tasks are processed, print a summary.

If no pending tasks exist, print:

```
No pending remote tasks.
```

### list

Read all `.md` files in `tasks/remote/` and print a table:

```
Remote tasks:

  # | Status      | Created              | File
  1 | done        | 2026-04-27T10:30:00  | deploy-staging.md
  2 | blocked     | 2026-04-27T10:45:00  | run-migration.md
  3 | in-progress | 2026-04-27T11:00:00  | fix-typo.md
  4 | pending     | 2026-04-27T11:15:00  | update-deps.md
```

### clean

Delete all task files with `status: done` or `status: failed`.
Print the number of files removed.

## Step 3: Schedule next poll

This skill is designed for `/loop` without a fixed interval
(self-paced). After each poll, use `ScheduleWakeup` with adaptive
timing:

- **Active**: If any task was executed, blocked, or unblocked this
  poll, schedule the next poll in **60 seconds**. There may be
  follow-up work or an answer arriving soon.
- **Idle**: If no tasks were processed (nothing pending, nothing
  newly unblocked), schedule the next poll in **270 seconds**. This
  keeps the cache warm without wasting cycles.

@~/.claude/rules/meta-learning.md
