# Secrets

Personal API keys and credentials live in the macOS Login Keychain. Use the
`security` CLI to retrieve them. Never write a secret value to a file, embed
one as a literal in a command line, or echo one back to the user in chat
output. Always retrieve via command substitution at point of use.

## Retrieval

Retrieve a secret with:

```
security find-generic-password -s <service> -a <account> -w
```

The `-w` flag prints only the password to stdout. Pipe it into the consuming
tool via command substitution. For example:

```
curl -u "$(security find-generic-password -s stripe-test -a function-health -w):" \
  https://api.stripe.com/v1/customers?limit=1
```

The first time a non-Apple binary reads an entry, macOS may prompt for
permission. Click "Always Allow" once. Subsequent reads are silent as long as
the Login Keychain is unlocked.

## Inventory

Each Purpose is the entry's Keychain comment (`-j`) word for word, so change
both together. New entries follow the creation template in the `secrets`
skill.

### `function-health`

| Service                      | Purpose                                                                               |
| ---------------------------- | ------------------------------------------------------------------------------------- |
| `conductorone-client-id`     | ConductorOne PCC client ID for the cone CLI                                           |
| `conductorone-client-secret` | ConductorOne PCC client secret for the cone CLI                                       |
| `datadog-app`                | Datadog personal access token (us5) for monitor validation                            |
| `devhub`                     | DevHub (EasyDeploy) personal API key (read, mutate) for REST and MCP calls            |
| `dx-api`                     | DX (getdx.com) API token for engineering metrics                                      |
| `fh-dev-member-token`        | Member app Firebase ID token (Dev, about one hour) for MAM calls                      |
| `fh-github-token`            | GitHub personal access token for fh-sync and system-update                            |
| `incident-io`                | incident.io user API key for the on-call script                                       |
| `statsig-console`            | Statsig Console API key for agent calls                                               |
| `stripe-prod`                | Stripe restricted key (Live, read-only) for agent reads                               |
| `stripe-prod-limited-write`  | Stripe restricted key (Live, read plus limited write) for break-glass remediation     |
| `stripe-prod-webhooks`       | Stripe restricted key (Live, webhook_endpoints:write) for webhook event subscriptions |
| `stripe-test`                | Stripe restricted key (Test, full access) for agent calls                             |

### `personal`

| Service                      | Purpose                                                                               |
| ---------------------------- | ------------------------------------------------------------------------------------- |
| `elevenlabs-api`             | ElevenLabs API key for podcast.py                                                     |
| `logo-dev`                   | logo.dev publishable key (pk_) for the logo image CDN                                 |
| `logo-dev-secret`            | logo.dev secret key (sk_) for brand search                                            |
| `monarch-token`              | Monarch API session token for monarch.py                                              |
| `openai-api`                 | OpenAI API key for agent calls                                                        |
| `ppp-qa-p7-dev`              | Member app password (Dev, throwaway) for PPP QA persona P7                            |
| `workmail`                   | AWS WorkMail password for workmail.py                                                 |

`workmail` is listed here, but its account is the login email, which
`workmail.py` also uses as the IMAP user.

## Per-Application Usage

Header shapes, key scopes and the procedure for adding a secret live in the
`secrets` skill. Invoke it before the first call to ConductorOne, Statsig,
Stripe, DevHub or Datadog with one of these keys, and before adding an
entry. Two rules hold even without it:

- `stripe-prod` is read-only. Never use it for write operations.
- The Live write keys (`stripe-prod-webhooks` and
  `stripe-prod-limited-write`) are narrowly scoped. Confirm the target
  objects and the intended end state before every call.

## When Not to Use the Keychain

- **Function Health service secrets**: Service-to-service credentials live in
  GCP Secret Manager. Fetch via
  `gcloud secrets versions access latest --secret=<name>`. See
  @rules/function-health.md.
- **Ephemeral tokens**: Short-lived tokens (e.g.,
  `gcloud auth print-access-token`) should be generated inline, not cached.
  The one exception is `fh-dev-member-token`: an agent cannot sign in as
  a member, so Nickolas caches that token for it (see the `fh-auth` skill).
