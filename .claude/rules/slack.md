# Slack

- Follow @rules/typography.md for all Slack content.
- ALWAYS send messages using the `slack_send_message_draft` tool, never
  `slack_send_message`. The user reviews and approves drafts before they
  are sent.
  - **Exception**: The `on-call` skill sends its one-line notify straight
    to my own DM (`U09H5CVRGTG`) with `slack_send_message`, since a draft
    never reaches my phone. No other destination and no other skill.

## Search

- **Private channels are invisible by default**: `slack_search_channels`
  defaults to `channel_types: public_channel`, so private channels come
  back empty and read as archived. Pass
  `channel_types: "public_channel,private_channel"` whenever checking
  whether a channel exists or is live.
- **Multi-term queries AND**: A batched stem query like
  `"foo bar baz"` returns nothing. Issue one stem per query.
- **Results cap at 20**: There is no way to raise the limit. A broad stem
  silently truncates and proves nothing about a specific channel; narrow
  the stem until the result set is under the cap.
- **Search visibility proves membership only for private channels**: A
  private-channel hit is positive proof of membership. A public hit only
  proves the channel exists and is unarchived; it says nothing about
  membership. Never treat a public search hit as a membership signal.

## Tables

To render tabular data as a native Slack table, invoke the `slack-table`
skill. Plain-text TSV pasted as text does not render as a table.
