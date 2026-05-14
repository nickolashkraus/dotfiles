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
cc: <@USERID1> <@USERID2>
```

## Formatting rules

- Link PRs using Slack link syntax: `<url|text>`.
- Link the Notion release doc the same way.
- Summarize migrations and secrets in one line. If none, say so.

## cc list

Default cc list (used when `--cc` is not provided): "" (empty)

If `--cc` is provided, replace the default list entirely.
Accepts a comma-separated list of Slack user IDs (`U...`) or `@handles` that
resolve to user IDs via `slack_search_users`. Render each as `<@USERID>`. Pass
`--cc ""` (empty) to omit the cc line entirely.
