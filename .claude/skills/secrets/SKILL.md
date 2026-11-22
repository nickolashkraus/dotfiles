---
name: secrets
description: >
  Per-application usage of the Keychain secrets inventoried in
  `rules/secrets.md`: ConductorOne flags, the Statsig header, Stripe key
  selection and scopes (Test, Live read-only, Live webhooks, Live limited
  write), DevHub REST and MCP headers, Datadog, and how to add a secret.
  TRIGGER when: about to call the Stripe, Statsig, DevHub, ConductorOne or
  Datadog API with a Keychain key, choosing which Stripe key to use,
  probing a restricted key's scopes, or adding a Keychain entry.
disable-model-invocation: false
allowed-tools: Bash, Read
---

# Secrets

The retrieval rule and the inventory live in `~/.claude/rules/secrets.md`.
Never write a secret value to a file, embed one as a literal in a command line,
or echo one back in chat. Always retrieve via command substitution at point of
use.

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

- `stripe-test`: Restricted key scoped for agents. Test mode, full access. Use
  for all Test-mode work.
- `stripe-prod`: Restricted key scoped for agents. Live mode, read-only. Never
  use this for write operations.
- `stripe-prod-webhooks`: Restricted key scoped for agents. Live mode, scope
  `webhook_endpoints:write` only. Use exclusively for managing the event
  subscriptions on the transaction-service and ppp-service webhook
  endpoints (the latter is the Dhalia publisher,
  `stripe-dhalia-webhook-publisher.partners.functionhealth.com`); do not
  reach for this when adding Live write capability for any other Stripe
  resource. Mint a separate narrowly-scoped key instead. An update replaces
  `enabled_events` wholesale, so read the endpoint first and send the full
  list plus the additions.
- `stripe-prod-limited-write`: Restricted key scoped for agents. Live mode,
  read plus `subscriptions:write`, `coupons:write`, `promotion_code:write`,
  `products:write`, and `prices:write` (widened 2026-09-25 for the SuppCo offer
  authoring; it previously carried only subscriptions and coupons). Break-glass
  key for Prod subscription remediation, for minting campaign coupons, and for
  partner-offer catalog authoring. The subscriptions scope also covers
  `/v1/subscription_schedules`, which has no separate toggle in the Dashboard.
  `products` and `prices` are separate toggles, and so are `coupons` and
  `promotion_code`: a coupon can be created while the promotion code on it is
  refused, and a product while its price is refused. Confirm the target objects
  and the intended end state before every call, and revoke the key in the
  Dashboard once the work is done rather than leaving Live write capability
  resident.

  Probe a restricted key's scopes without mutating anything by POSTing an empty
  body to the resource: `403` means the scope is absent, `400` (a
  missing-required-param complaint) means it is present.

  ```bash
  KEY=$(security find-generic-password \
    -s stripe-prod-limited-write -a function-health -w)
  curl -s -o /dev/null -w '%{http_code}\n' -u "${KEY}:" \
    -X POST https://api.stripe.com/v1/prices -d ""
  ```

Stripe has no API for minting API keys; `/v1/api_keys` returns a 404. Every key
above is created by hand in the Dashboard under Developers, API keys, Create
restricted key.

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
a user credential in `DD-APPLICATION-KEY`. Only the user credential lives in
the Keychain: `datadog-app` is a personal access token (`ddpat_`), despite the
service name, and it reads more than monitors. The org API key is a Function
Health secret and stays in GCP Secret Manager (`DATADOG_API_KEY` in
`function-health-dev-env`). The org is on the `us5` site. For usage (e.g.,
local monitor-query validation), invoke the `fh-datadog` skill.

## Adding a New Secret

Every entry follows one template:

```bash
security add-generic-password \
  -s <service> \
  -a <account> \
  -D "<kind>" \
  -j "<Vendor> <kind> (<Env>, <scope>) for <consumer>" \
  -U -w
```

- **Service** (`-s`): Lowercase and hyphenated, vendor first, then the
  environment or qualifier (`stripe-prod-webhooks`, `logo-dev-secret`). Never
  rename an existing service, since scripts look it up by name.
- **Account** (`-a`): `function-health` for Function Health credentials and
  `personal` for everything else. The one exception is `workmail`, whose
  account is the login email because `workmail.py` reuses it as the IMAP user.
- **Kind** (`-D`): One of `API key`, `API token`, `restricted key`,
  `access token`, `session token`, `ID token`, `client ID`, `client secret` or
  `password`. Keychain Access shows it in the Kind column.
- **Comment** (`-j`): `<Vendor> <kind> (<Env>, <scope>) for <consumer>`, such
  as `Stripe restricted key (Live, read-only) for agent reads`. Env is Dev,
  Staging or Prod, or Test or Live for Stripe. The consumer is the script or
  skill that reads the key, or `agent calls` when only ad hoc agent calls
  do. Drop the parenthetical when there is no environment or scope. Leave
  out dates, since the Keychain records created and modified times.
- **`-U -w` last**: `-w` with no value prompts for it twice, which keeps the
  value out of argv and shell history. Anything after `-w` becomes the value,
  and a trailing `-U` was once stored as the password. An agent cannot answer
  the prompt, so it gives Nickolas the command to run with the `!` prefix.
  A script pipes the value twice on stdin from a child with no TTY, as
  `scripts/monarch.py` in agent-os does.

To change the kind or comment on an existing entry, run the same command
without `-w`. With `-U` and no `-w`, `security` updates the attributes and
leaves the value untouched (tested 2026-11-19).

After adding a secret, add its row to the Inventory in
`~/.claude/rules/secrets.md`. The Purpose column is the comment, word for word.
