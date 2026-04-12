---
name: monitor-slack
description: >
  Monitors a Slack thread, channel, DM, or workspace for a topic, triaging
  issues and drafting fixes for bugs.
disable-model-invocation: false
allowed-tools: >
  Bash, Edit, Glob, Grep, Read, Write, Agent,
  mcp__claude_ai_Slack__slack_read_thread,
  mcp__claude_ai_Slack__slack_read_channel,
  mcp__claude_ai_Slack__slack_search_public,
  mcp__claude_ai_Slack__slack_search_public_and_private
argument-hint: >
  <topic>
  --thread <channel_id> <message_ts>
  | --channel <channel_id>
  | --dm <channel_id>
  | --workspace
---

# Monitor Slack

Monitors Slack for messages about a given topic. Triages each message:
non-actionable items (questions, discussions, feature requests) are summarized.
Legitimate bugs get a drafted fix. All proposed Slack responses are queued in
the outbox for review. Nothing is committed, pushed, or posted to Slack without
explicit user approval via `/outbox`.

## Usage

Pair with `/loop` for recurring monitoring:

```
/loop 5m /monitor-slack <topic> --thread <channel_id> <message_ts>
/loop 5m /monitor-slack <topic> --channel <channel_id>
/loop 5m /monitor-slack <topic> --dm <channel_id>
/loop 10m /monitor-slack <topic> --workspace
```

Review and send queued messages with `/outbox`.

### Modes

- `--thread <channel_id> <message_ts>`: Monitor a specific thread.
- `--channel <channel_id>`: Monitor an entire channel.
- `--dm <channel_id>`: Monitor a DM or group DM.
- `--workspace`: Search the entire workspace for the topic.

### Examples

```
/loop 5m /monitor-slack PPP --thread C0ANWC51NH5 1775783009.575449
/loop 5m /monitor-slack "checkout bugs" --channel C0ANWC51NH5
/loop 10m /monitor-slack PPP --workspace
```

## Outbox

The outbox lives at `~/nickolashkraus/agent-os/tasks/outbox/`. Each day's
queued messages are appended to a single daily file (`YYYY-MM-DD.md`). Use
`/outbox` to review, edit, approve, or discard queued messages.

## Step 1: Parse arguments

Parse `$ARGUMENTS` into two parts:

1. **Topic**: The first positional argument (or quoted string). This is the
   subject to watch for (e.g., "PPP", "checkout bugs", "auth errors").
2. **Mode flag**: One of `--thread`, `--channel`, `--dm`, or `--workspace`,
   followed by its required parameters.

If arguments are missing or malformed, print usage instructions and stop.

## Step 2: Load state

Read the state file at `~/nickolashkraus/agent-os/tasks/outbox/.state.json`. If
it exists, extract `last_seen_ts` (the timestamp of the last processed
message). If it does not exist, this is the first run.

## Step 3: Fetch messages

Based on the mode flag, fetch recent messages from Slack.

### --thread

Use `slack_read_thread` with the given `channel_id` and `message_ts`. On the
first run, read the full thread to establish context. On subsequent runs, set
the `oldest` parameter to `last_seen_ts` to fetch only new replies.

### --channel / --dm

Use `slack_read_channel` with the given `channel_id`. Read the latest messages
(limit 10 on first run). Skip any messages with a timestamp at or before
`last_seen_ts`.

### --workspace

Use `slack_search_public_and_private` with the topic as the query. Add a date
filter to limit results to the last hour. Summarize any new matches.

## Step 4: Filter for relevance

Skip messages that do not relate to the topic. Only process messages that
mention the topic directly or discuss related functionality (e.g., error
messages, stack traces, or behavior changes in the topic's domain).

## Step 5: Triage each relevant message

For each new relevant message, classify it:

### Non-actionable (question, discussion, feature request, status update)

Print a one-line summary with the author and timestamp. Example:

```
[Victor, 3:42 PM] Asked when the invoice endpoint will be ready. (question)
```

No outbox entry needed for purely informational items. If the message warrants
a reply (e.g., answering a question you know the answer to), queue a response
in the outbox.

### Actionable bug

When a message describes a legitimate bug (error, incorrect behavior, data
issue):

1. Identify the bug from the message context.
2. Search the codebase for the relevant code.
3. Draft a fix (edit the files, but do not commit).
4. Present the fix to the user with a summary of what changed and why.
5. Queue a Slack response in the outbox describing the fix.

## Step 6: Queue outbox messages

For any Slack message that should be sent, append an entry to today's outbox
file at `~/nickolashkraus/agent-os/tasks/outbox/YYYY-MM-DD.md` (using the
current date).

If the file does not exist, create it with a heading:

```markdown
# YYYY-MM-DD
```

Append each queued message as a checklist item:

```markdown
- [ ] **HH:MM** | `<channel_id>` | thread: `<thread_ts>`
  **Context**: <one-line description of why this message is being sent>
  **From**: <source author> at <source timestamp>
  ```
  <message body to send on Slack>
  ```
```

Do not send the message. Print a confirmation:

```
Queued reply -> agent-os/tasks/outbox/YYYY-MM-DD.md
```

## Step 7: Save state

Write the timestamp of the newest processed message to
`~/nickolashkraus/agent-os/tasks/outbox/.state.json`:

```json
{
  "last_seen_ts": "<newest_message_ts>",
  "updated_at": "<ISO 8601 timestamp>"
}
```

## Step 8: Report status

If there are no new messages, print:

```
No new messages. Monitoring continues.
```

If messages were processed, print a summary of actions taken (summaries
printed, fixes drafted, messages queued).
