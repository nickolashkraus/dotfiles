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
  [topic]
  --thread <channel_id> <message_ts>
  | --channel <channel_id>
  | --dm <channel_id>
  | --workspace
---

# Monitor Slack

Monitors Slack for messages, optionally filtered by topic. Triages each
message: non-actionable items (questions, discussions, feature requests) are
summarized. Legitimate bugs get a drafted fix. All proposed Slack responses are
queued in the outbox for review. Nothing is committed, pushed, or posted to
Slack without explicit user approval via `/outbox`.

## Usage

Pair with `/loop` for recurring monitoring:

```
# With a topic filter:
/loop 5m /monitor-slack PPP --thread C0ANWC51NH5 1775783009.575449
/loop 5m /monitor-slack "checkout bugs" --channel C0ANWC51NH5
/loop 10m /monitor-slack PPP --workspace

# Without a topic (all messages):
/loop 5m /monitor-slack --dm C0ANWC51NH5
/loop 5m /monitor-slack --channel C0ANWC51NH5
/loop 5m /monitor-slack --thread C0ANWC51NH5 1775783009.575449
```

Review and send queued messages with `/outbox`.

### Modes

- `--thread <channel_id> <message_ts>`: Monitor a specific thread.
- `--channel <channel_id>`: Monitor an entire channel.
- `--dm <channel_id>`: Monitor a DM or group DM.
- `--workspace`: Search the entire workspace (requires a topic).

### Channel ID

The `<channel_id>` can be a raw ID (e.g., `C0ANWC51NH5`) or a Slack archive URL
(e.g., `https://functionhealth.slack.com/archives/C0ANWC51NH5`). If a URL is
provided, extract the channel ID from the path.

## Outbox

The outbox lives at `~/nickolashkraus/agent-os/tasks/outbox/`. Each day's
queued messages are appended to a single daily file (`YYYY-MM-DD.md`). Use
`/outbox` to review, edit, approve, or discard queued messages.

## Step 1: Parse arguments

Parse `$ARGUMENTS` into:

1. **Mode flag** (required): One of `--thread`, `--channel`, `--dm`, or
   `--workspace`, followed by its required parameters.
2. **Topic** (optional): Any positional argument before the mode flag. If
   omitted, all messages in the target are processed (no relevance filter).
   `--workspace` mode requires a topic; print an error and stop if missing.

If a Slack URL is provided instead of a channel ID, extract the channel ID from
the URL path (the segment starting with `C`, `D`, or `G`).

If arguments are missing or malformed, print usage instructions and stop.

## Step 2: Load state

Read the state file at `~/nickolashkraus/agent-os/tasks/outbox/.state.json`.
The file is a JSON object keyed by monitor target so that multiple concurrent
monitors do not overwrite each other's timestamps. Derive the key from the
parsed arguments:

- `--channel` / `--dm`: the channel ID (e.g., `C0ASJ80NWBG`).
- `--thread`: `<channel_id>:<message_ts>` (e.g., `C0ANWC51NH5:1775783009.575449`).
- `--workspace`: `workspace:<topic>` (e.g., `workspace:PPP`).

If the file exists, look up the key and extract its `last_seen_ts` and
`watched_threads` (defaults to `{}`). If the key is missing or the file
does not exist, this is the first run for that target.

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

After processing top-level messages, check each entry in `watched_threads` for
new replies. For each watched thread, call `slack_read_thread` with the
thread's `channel_id` and `thread_ts`, setting `oldest` to the thread's
`last_seen_reply_ts`. Triage any new replies the same way as top-level
messages. Update the thread's `last_seen_reply_ts` to the newest reply
timestamp.

### --workspace

Use `slack_search_public_and_private` with the topic as the query. Add a date
filter to limit results to the last hour. Summarize any new matches.

## Step 4: Filter for relevance

If a topic was provided, skip messages that do not relate to the topic. Only
process messages that mention the topic directly or discuss related
functionality (e.g., error messages, stack traces, or behavior changes in the
topic's domain).

If no topic was provided, process all messages.

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

### Watching threads

When a reply is queued to a thread (i.e., the outbox entry has a `thread_ts`),
add that thread to `watched_threads` in the state so future polls pick up new
replies. Also add a thread when a top-level message is triaged as an actionable
bug, since follow-up discussion is likely.

## Step 7: Save state

Read the current state file (or start with `{}`), update the entry for this
monitor's key, and write the file back. This read-modify-write ensures other
monitors' state is preserved.

```json
{
  "<key>": {
    "last_seen_ts": "<newest_message_ts>",
    "updated_at": "<ISO 8601 timestamp>",
    "watched_threads": {
      "<thread_ts>": {
        "last_seen_reply_ts": "<newest_reply_ts>",
        "added_at": "<ISO 8601 timestamp>"
      }
    }
  }
}
```

Prune any `watched_threads` entry whose `added_at` is older than 7 days.

## Step 8: Report status

If there are no new messages, print:

```
No new messages. Monitoring continues.
```

If messages were processed, print a summary of actions taken (summaries
printed, fixes drafted, messages queued).

@~/.claude/rules/meta-learning.md
