# Slack Deployment Announcement Template

Channel: `#deployments-planning` (`C07M0QKP75F`)

Send as a **draft** using `slack_send_message_draft`. The user will
review and post it.

```
Planning a release for <Service Name> today. <N> PR(s):
1. <pr-url|PR #NNNN> (`release/<date>.NN`): <PR title>
2. ...
Includes <migration/secret summary or "No migrations or new secrets.">.
Release Doc: <notion-url|Service Name (date)>
cc: <@U05NN4P8LAC> <@U065N71LRB7> <@U029CH9KPDH>
```

## Formatting rules

- Link PRs using Slack link syntax: `<url|text>`.
- Link the Notion release doc the same way.
- Summarize migrations and secrets in one line. If none, say so.
- Always cc Gabi (`U05NN4P8LAC`), Santiago (`U065N71LRB7`), and Max
  (`U029CH9KPDH`).
