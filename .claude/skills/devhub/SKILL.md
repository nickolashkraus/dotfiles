---
name: devhub
description: Drive Function Health DevHub (EasyDeploy) headlessly over its REST API to read service state, preview a deploy, scan a repo, or deploy a service
---

You are operating DevHub (EasyDeploy) over its REST API instead of its web UI.
Use this for reading deploy state, previewing a deploy, scanning a repo, and
deploying a service.

## Auth

```bash
KEY=$(security find-generic-password -s devhub -a function-health -w)
BASE=https://devhub.svc.functionhealth.com/api/apps/easydeploy/v1
```

One key, two endpoints, two headers, and getting this wrong wastes a cycle:

- **REST** (`$BASE/...`): `x-api-key: $KEY`. Sending `Authorization: Bearer`
  returns 401 `"Bearer authentication is not configured"`, which looks like a
  revoked key and is not.
- **MCP** (`/api/mcp`): `Authorization: Bearer $KEY`. The REST path above is
  preferred, because the MCP server exposes reads only: `start_deploy` and the
  rest of the write catalog are implemented but disabled behind its
  `EXPOSED_TOOLS` allowlist. The key itself carries `read` and `mutate`, so REST
  can write what MCP will not.

Dev is `https://devhub.svc.dev.functionhealth.com`, and a key is minted per
environment. RBAC is server-side: Prod actions need the `dev-hub-prod-writer`
Okta group, granted through the **Dev Hub Prod** app in ConductorOne.

If the key is missing from the Keychain, it cannot be created from the API. Ask
for it to be minted in the UI (avatar menu, Settings, MCP API key) and stored
per @~/.claude/rules/secrets.md. Do not fall back to browser automation without
saying so first.

## Reads

| Purpose                 | Request                                                 |
| ----------------------- | ------------------------------------------------------- |
| Service catalog         | `GET $BASE/services`                                    |
| Per-environment state   | `GET $BASE/services/<name>/state?env=<env>`             |
| Deploy preview          | `GET $BASE/services/<name>/deploys/preview?env=<env>`   |
| Deploy history          | `GET $BASE/services/<name>/deploys`                     |
| One deploy              | `GET $BASE/services/<name>/deploys/<deploy_id>`         |
| Last repo scan          | `GET $BASE/repos/sync/latest`                           |

The state response is keyed by environment, and an absent key means that
environment has never been deployed through EasyDeploy. Do not read a missing
key as an error.

## Read the preview before deploying, always

`deploys/preview` is the one call that answers whether a deploy will be
refused, and why. Check three fields:

- **`locks`**: A non-empty list blocks the deploy. Admission returns 409
  `EASYDEPLOY_PROD_DEPLOY_LOCKED`. Locks are named, reasoned, audited, and
  releasable by anyone, so report the reason rather than working around it.
- **`migration_ordering`**: Non-null means a migration has to run first. A
  deploy never rolls new code onto an un-migrated schema.
- **`diff_text`** and **`changed`**: What the deploy actually alters, usually
  sizing. Read this before Prod: it is the cheapest check that the manifest and
  the service's Terraform agree.

`has_previous: false` means no prior deploy in that environment, so there is
nothing to roll back to.

## Writes

Scan a repo, which registers `easydeploy.yml` into the catalog:

```bash
curl -s -X POST -H "x-api-key: $KEY" "$BASE/repos/sync"
```

Scan whenever a service's `easydeploy.yml` changed, and whenever the catalog
disagrees with the manifest. A stale catalog is real: a service can carry an
enabled `migrations` job the manifest no longer declares.

Start a deploy:

```bash
curl -s -X POST -H "x-api-key: $KEY" -H 'Content-Type: application/json' \
  -d '{"env":"<env>","...":"..."}' "$BASE/services/<name>/deploys"
```

Confirm the request body against the live API before sending it; this skill does
not pin a schema it has not verified. Related endpoints:
`deploys/<id>/confirm` (only engages when a manual deploy's post-promotion
health check returns `unhealthy` or `error`), and `redeploy-previous`.

## Prod deploys need explicit approval

A Prod deploy is an outward-facing, hard-to-reverse action. Never start one
without the user saying to, in chat, for that deploy. Reading and previewing
need no approval.

When the environment is Prod, say these before asking:

- The image digest being deployed, and the digest currently serving. These
  often differ: Terraform pins a bootstrap digest while Dev has since moved on,
  so "promote what Dev serves" and "deploy what Prod already runs" are
  different actions with different blast radius.
- What `diff_text` changes.
- Anything in `locks` or `migration_ordering`.

## Terraform is not always EasyDeploy's lane

`terraform_enabled` on a service does not mean EasyDeploy applies its
Terraform. Some services apply Prod Terraform from a tagged release in their own
repo, and EasyDeploy owns only the image after the service exists. Check which
lane the service uses before reaching for a Terraform action, and never assume
the tab's existence implies ownership.

## Auto-release

Dev auto-release is a per-service toggle, and only the `easydeploy-<sha>` merge
build is eligible. Prod auto-release defaults off
(`auto_release_prod_enabled`), is shadow-first, and is limited by
`auto_release_prod_service_allowlist`, whose default is `devhub` alone. So for
every other service, a Prod deploy is manual by design, and the
`vX.Y.Z-devhub` tag is no longer a Prod release path.
