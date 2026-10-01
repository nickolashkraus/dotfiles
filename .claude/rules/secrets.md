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

## Per-Application Usage

### ConductorOne (`cone`)

Pass both `client_id` and `client_secret` as flags:

```
cone \
  --client-id "$(security find-generic-password -s conductorone-client-id -a function-health -w)" \
  --client-secret "$(security find-generic-password -s conductorone-client-secret -a function-health -w)" \
  whoami
```

Alternatively, configure them once via `cone login` and omit the flags.

### Statsig

Statsig's Console API authenticates via the `STATSIG-API-KEY` header:

```
curl \
  -H "STATSIG-API-KEY: $(security find-generic-password -s statsig-console -a function-health -w)" \
  -H "Content-Type: application/json" \
  https://statsigapi.net/console/v1/gates
```

### Stripe

Stripe uses HTTP basic auth with the API key as the username and an empty
password (note the trailing colon):

```
KEY=$(security find-generic-password -s stripe-test -a function-health -w)
curl -u "${KEY}:" https://api.stripe.com/v1/...
```

- `stripe-test`: Restricted key scoped for agents. Test mode, full access.
  Use for all Test-mode work.
- `stripe-prod`: Restricted key scoped for agents. Live mode, read-only.
  Never use this for write operations.
- `stripe-prod-webhooks`: Restricted key scoped for agents. Live mode, scope
  `webhook_endpoints:write` only. Use exclusively for managing
  transaction-service webhook endpoint subscriptions; do not reach for this
  when adding Live write capability for any other Stripe resource. Mint
  a separate narrowly-scoped key instead.
- `stripe-prod-limited-write`: Restricted key scoped for agents. Live mode,
  read plus `subscriptions:write`, `coupons:write`, `promotion_code:write`,
  `products:write`, and `prices:write` (widened 2026-09-25 for the SuppCo
  offer authoring; it previously carried only subscriptions and coupons).
  Break-glass key for Prod subscription remediation, for minting campaign
  coupons, and for partner-offer catalog authoring. The subscriptions scope
  also covers `/v1/subscription_schedules`, which has no separate toggle in
  the Dashboard. `products` and `prices` are separate toggles, and so are
  `coupons` and `promotion_code`: a coupon can be created while the promotion
  code on it is refused, and a product while its price is refused. Confirm the
  target objects and the intended end state before every call, and revoke the
  key in the Dashboard once the work is done rather than leaving Live write
  capability resident.

  Probe a restricted key's scopes without mutating anything by POSTing an
  empty body to the resource: `403` means the scope is absent, `400` (a
  missing-required-param complaint) means it is present.

  ```bash
  KEY=$(security find-generic-password \
    -s stripe-prod-limited-write -a function-health -w)
  curl -s -o /dev/null -w '%{http_code}\n' -u "${KEY}:" \
    -X POST https://api.stripe.com/v1/prices -d ""
  ```

Stripe has no API for minting API keys; `/v1/api_keys` returns a 404. Every
key above is created by hand in the Dashboard under Developers, API keys,
Create restricted key.

### DevHub (EasyDeploy)

One key, two endpoints, two different headers. This is the trap: the REST API
rejects `Authorization: Bearer` with `"Bearer authentication is not
configured"`, which reads like a bad key rather than a wrong header.

- **REST** (`/api/apps/easydeploy/v1/...`): `x-api-key`.
- **MCP** (`/api/mcp`): `Authorization: Bearer`.

```bash
KEY=$(security find-generic-password -s devhub -a function-health -w)
curl -s -H "x-api-key: ${KEY}" \
  https://devhub.svc.functionhealth.com/api/apps/easydeploy/v1/services
```

The key carries `read` and `mutate` scopes, so it can start deploys through
REST even though the MCP server's write tools are disabled behind its
`EXPOSED_TOOLS` allowlist. Server-side RBAC still applies, so it never has more
authority than the Okta groups behind it (`dev-hub-prod-writer` for Prod
actions). Minted by hand in the DevHub UI under avatar menu, Settings, MCP API
key; it cannot be created from the API. For the procedures it unlocks, invoke
the `devhub` skill.

### Datadog

Datadog's API needs two credentials: an org-level API key (`DD-API-KEY`) and
a user-scoped Application key (`DD-APPLICATION-KEY`). Only the Application key
(`datadog-app`, scoped to monitors) lives in the Keychain; the org API key is
a Function Health secret and stays in GCP Secret Manager (`DATADOG_API_KEY` in
`function-health-dev-env`). The org is on the `us5` site. For usage (e.g.,
local monitor-query validation), invoke the `fh-datadog` skill.

## Adding a New Secret

```
security add-generic-password \
  -s "<service-name>" \
  -a "<account>" \
  -w "<value>" \
  -j "<one-line description of what this secret is for>" \
  -U
```

The `-U` flag updates the entry if it already exists. Naming conventions:

- **Service**: Lowercase, hyphenated. Use `<vendor>-<purpose>` or
  `<vendor>-<env>-<purpose>`. Examples: `conductorone-client-id`,
  `stripe-test`.
- **Account**: The owning context. Use `function-health` for Function Health
  credentials and `personal` for personal accounts.
- **Comment** (`-j`): A short human-readable description.

After adding a secret, update the Inventory table in this file.

## When Not to Use the Keychain

- **Function Health service secrets**: Service-to-service credentials live in
  GCP Secret Manager. Fetch via
  `gcloud secrets versions access latest --secret=<name>`. See
  @rules/function-health.md.
- **Ephemeral tokens**: Short-lived tokens (e.g.,
  `gcloud auth print-access-token`) should be generated inline, not cached.
