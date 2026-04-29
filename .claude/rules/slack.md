# Slack

- Follow @rules/typography.md for all Slack content.
- ALWAYS send messages using the `slack_send_message_draft` tool, never
  `slack_send_message`. The user reviews and approves drafts before they
  are sent.

## Tables

When sharing a Markdown table or tabular data in Slack, convert it to TSV
(tab-separated values). Pasted TSV renders as a native formatted table in
Slack.

- Use tabs (`\t`) to separate columns. Do not use literal spaces or
  Markdown pipes.
- Strip Markdown formatting (e.g., `**bold**` becomes `bold`). Slack
  applies its own styling.
- The first row is the column headers.
