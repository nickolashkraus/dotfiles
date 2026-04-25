---
name: outbox
description: >
  Review, edit, approve, and send queued Slack messages from the outbox.
disable-model-invocation: false
allowed-tools: >
  Bash, Edit, Glob, Read, Write,
  mcp__claude_ai_Slack__slack_send_message
argument-hint: >
  [list | send <index> | send-all
  | edit <index> | discard <index> | clear]
  [--date YYYY-MM-DD]
---

# Outbox

Review and manage queued Slack messages in
`~/nickolashkraus/agent-os/tasks/outbox/`. Messages are queued by
`/monitor-slack` and other skills. Nothing is sent without your explicit
approval.

## Usage

```
/outbox                  List all pending messages for today.
/outbox list             List all pending messages for today.
/outbox send <index>     Send a specific message by index, then mark it sent.
/outbox send-all         Send all pending messages in order.
/outbox edit <index>     Edit a message before sending.
/outbox discard <index>  Mark a message as discarded without sending.
/outbox clear            Mark all pending messages as discarded.
```

Add `--date YYYY-MM-DD` to any subcommand to operate on a different day's
outbox (defaults to today).

## Outbox format

Each day's outbox is a single file at
`~/nickolashkraus/agent-os/tasks/outbox/YYYY-MM-DD.md`. Messages are checklist
items:

```markdown
# YYYY-MM-DD

- [ ] **HH:MM** | `<channel_id>` | thread: `<thread_ts>`
  **Context**: <why this message is being sent>
  **From**: <source author> at <source timestamp>
  ```
  <message body>
  ```
```

- `[ ]`: Pending.
- `[x]`: Sent.
- `[-]`: Discarded.

## Step 1: Parse arguments

Parse `$ARGUMENTS` to determine the subcommand and optional `--date` flag. If
no subcommand, default to `list`. If `--date` is present, use that date;
otherwise use today's date.

Set the outbox path to
`~/nickolashkraus/agent-os/tasks/outbox/YYYY-MM-DD.md`.

## Step 2: Execute subcommand

### list (default)

Read the outbox file. For each unchecked item (`- [ ]`), print a numbered
summary:

```
Outbox for 2026-04-12 (3 pending):

1. 08:30 | #ppp-testing (thread)
   Context: Replying to Victor's bug report about missing metadata.
   Preview: "Fixed the checkout metadata issue. The uuid field is now..."

2. 09:15 | #ppp-testing (thread)
   Context: Answering Victor's question about the invoice endpoint.
   Preview: "The invoice endpoint is available at..."

3. 10:00 | @santiago (DM)
   Context: Updating Santiago on the Stripe product linking fix.
   Preview: "Updated the PPP bundles to reference the existing..."
```

If no pending messages exist or the file does not exist, print:

```
Outbox is empty.
```

### send

1. Read the outbox file and find the Nth unchecked item (1-indexed).
2. Display the full message for confirmation.
3. Ask: "Send this message? (y/n)"
4. On confirmation, send the message using `slack_send_message` with the
   `channel_id` and `thread_ts` parsed from the checklist item.
5. Change `- [ ]` to `- [x]` in the outbox file.

### send-all

1. Find all unchecked items, in order.
2. For each, display a preview and send it.
3. Mark each as `[x]` after successful delivery.
4. Print a summary: "Sent N messages."

### edit

1. Find the Nth unchecked item.
2. Display its contents.
3. Ask the user what to change.
4. Apply the edits to the message body inside the code fence.

### discard

1. Find the Nth unchecked item.
2. Display the message for confirmation.
3. Ask: "Discard this message? (y/n)"
4. On confirmation, change `- [ ]` to `- [-]`.

### clear

1. Count unchecked items.
2. Ask: "Discard all N pending messages? (y/n)"
3. On confirmation, change all `- [ ]` to `- [-]`.

@~/.claude/rules/meta-learning.md
