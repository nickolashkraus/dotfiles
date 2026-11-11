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

All entries below use the account `function-health`.

| Service                      | Purpose                                           |
| ---------------------------- | ------------------------------------------------- |
| `conductorone-client-id`     | ConductorOne PCC client ID                        |
| `conductorone-client-secret` | ConductorOne PCC client secret                    |
| `statsig-console`            | Statsig Console API key                           |
| `stripe-test`                | Stripe restricted key (Test)                      |
| `stripe-prod`                | Stripe restricted key (Live, read-only)           |
| `stripe-prod-webhooks`       | Stripe restricted key (Live, webhooks:write)      |
| `stripe-prod-limited-write`  | Stripe restricted key (Live, limited write)       |
| `dx-api`                     | DX (getdx.com) metrics API key                    |
| `datadog-app`                | Datadog app key (us5), monitor validation         |
| `fh-github-token`            | GitHub PAT for fh-sync and system-update          |
| `devhub`                     | DevHub (EasyDeploy) personal API key              |
| `fh-dev-member-token`        | Dev member app Firebase ID token (about one hour) |
| `incident-io`                | incident.io user key; the `on-call` script acks   |

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
