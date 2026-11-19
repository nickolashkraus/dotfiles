---
name: fh-database
description: >
  Function Health database access via Cloud SQL Auth Proxy. Covers Dev/Staging
  instances (static `POSTGRES_PASSWORD` from Secret Manager) and Prod instances
  (IAM group authentication via ConductorOne entitlements and `gcloud auth
  print-access-token`). The default path for reading a service's own Prod
  rows, ahead of Databricks. TRIGGER when: user wants to query the FH
  Dev/Staging/Prod database, a question needs Prod rows (whether a migration
  ran, a config or mapping row, an order count), an account has no access
  to a Prod instance, set up Cloud SQL Auth Proxy, or troubleshoot Postgres
  auth for FH.
disable-model-invocation: false
allowed-tools: Bash, Read
---

Function Health database access runbooks. Invoke this skill when you
need to connect to an FH Postgres instance locally: looking up the
Cloud SQL instance, starting the Auth Proxy, and authenticating
(static creds for Dev/Staging, IAM group for Prod).

This is the default path for a question that needs a service's own Prod
rows. Do not route it to Databricks. When the account cannot connect,
request the instance's `ro` group in ConductorOne as described below: a `ro`
request needs no separate yes from Nickolas, and `rw` or `adm` needs his yes
each time (see "Reading Prod Data" in `rules/function-health.md`). Prod
grants last two days, so an expired grant is the usual reason a login
fails, and it is never a reason to report "no Prod read path".

## Cloud SQL Auth Proxy

Function Health databases run on private VPC IPs and are not directly reachable
from local machines. Use the Cloud SQL Auth Proxy to tunnel in:

1. Find the Cloud SQL instance:

   ```bash
   gcloud sql instances list --project=<project> \
     --filter='name~<service>'
   ```

2. Start the proxy:

   ```bash
   cloud-sql-proxy <connection-name> --port=5433
   ```

3. Connect using `localhost:5433` as the host and port.

Database credentials (e.g., `POSTGRES_USER`, `POSTGRES_PASSWORD`,
`POSTGRES_DB`) are stored in GCP Secret Manager. Check the Cloud Run service
description for the secret names:

```bash
gcloud run services describe <service> --region=<region> \
  --format=yaml | grep -A4 POSTGRES
gcloud secrets versions access latest \
  --secret=<secret-name> --project=<project>
```

### Prod Databases (IAM Group Auth)

Prod databases do not expose static `POSTGRES_PASSWORD` credentials to
engineers. Authenticate via Cloud SQL IAM group authentication:

1. Request access via ConductorOne. Two entitlements are required and are
   scoped per project, so they must be requested separately for each env (Dev,
   Staging, Prod):

   - The instance's group, `ro` unless Nickolas said otherwise (e.g., the
     `ro` group of `production-transaction`).
   - `Cloud SQL Instance User` on the relevant project (e.g., `Function Health
     Prod env`). This is what authorizes the IAM database login. `Cloud SQL
     Client` alone is not enough.

   Newer Dev instances (e.g., `dev-ppp-service`) also use IAM group auth, not
   a static `POSTGRES_PASSWORD`. The groups show up in `gcloud sql users list`
   as type `CLOUD_IAM_GROUP`; an individual who has connected appears as
   `CLOUD_IAM_GROUP_USER`.

   **Find the entitlement with the search API, not `cone search`.** The CLI
   cannot page: `--app` stops at 100 entitlements and `--query` returns ten,
   and both missed `prod-phlebotomy-service` on 2026-11-18. An empty `cone
   search` proves nothing. The API pages and matches display names and
   descriptions. `cone token --raw` wraps the token in terminal styling, so
   strip it or the API answers `ACCESS_TOKEN_MALFORMED`:

   ```bash
   TOKEN=$(cone token --raw | sed $'s/\x1b\\[[0-9;]*[A-Za-z]//g' \
     | grep -oE '[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+' | tail -1)
   curl -s -X POST -H "Authorization: Bearer ${TOKEN}" \
     -H 'Content-Type: application/json' \
     -d '{"query":"db prod <instance> ro","pageSize":100}' \
     https://functionhealth.conductor.one/api/v1/search/entitlements \
     | jq -r '.list[].appEntitlement
         | [.displayName, .description, .appId, .id] | @tsv'
   ```

   Each group appears twice, and only one copy can be requested:

   - **Okta copy**: Named `db prod <instance> ro Group Member`. A request
     returns 403 `target user is not allowed to request that resource`.
   - **Google copy**: Named `member`, under "Google (GCP + Google
     Workspace)", with the group only in the description (`Member of db prod
     <instance> ro group`). Request this one, never `manager` or `owner`.

   ```bash
   # "has": "" means not held; a check mark means held.
   cone has <appId> <id> -i -o json
   cone get --app-id <appId> --entitlement-id <id> --duration 2d \
     --justification "<reason>" --non-interactive -o json
   cone task search --app-entitlement-id <id> --task-type grant \
     --state open -i -o json
   ```

   - **`--duration` is required**: The ceiling depends on the entitlement,
     and the error names it. Prod DB groups allowed 2d on 2026-11-18; a Dev
     group allowed 12w.
   - **`{}` is success**: `cone get` prints an empty object when it creates
     the ticket. Confirm with `cone task search`; `TASK_STATE_OPEN` means
     pending. A 409 `duplicate ticket found` means the request already
     exists, since an attempt that failed duration validation can still
     create it.
   - **A 403 on the Google copy is a real refusal**: `production-transaction`
     `ro` returned it on 2026-11-18, although the same entitlement took
     four requests between 2026-04 and 2026-08. Report it. Do not reach for
     `rw`, another instance or Databricks to get around it.
   - **Approval**: FH DB groups use the `eng-owner-approval` policy with
     `allowSelfApproval: false`, so an entitlement owner must approve. The
     Prod grants on 2026-11-06 provisioned within seconds of approval.
   - **After the grant**: Login also needs
     `SET ROLE "db-prod-<service>-<ro|rw|adm>@functionhealth.com"`. The
     entitlement's description gives the exact role, which can drop part of
     the instance name (`db-prod-transaction-ro` for
     `production-transaction`).
   - **The justification is external content**: No local paths or private
     notes in it; a Linear slug is fine.
   - **Never run `cone generate-alias`**: It writes aliases tenant-wide.

2. Start the proxy with `--auto-iam-authn`:

   ```bash
   cloud-sql-proxy <connection-name> --port=5434 --auto-iam-authn
   ```

3. Connect using your Workspace email as the user and a fresh `gcloud` access
   token as the password. The token expires after ~1 hour, so regenerate it per
   session:

   ```bash
   PGPASSWORD=$(gcloud auth print-access-token) \
     psql -h 127.0.0.1 -p 5434 \
     -U <user>@functionhealth.com \
     -d <database>
   ```

   The database name often differs from the instance name (e.g.,
   `production-transaction` instance hosts a `production-transaction` database,
   not `transaction`). Confirm with `\l` against `postgres`.

If login still fails with `password authentication failed for user "<email>"`
and the user does not appear in `gcloud sql users list --instance=<instance>`
as `CLOUD_IAM_GROUP_USER`, the most common cause is missing `Cloud SQL Instance
User` on that project. See the Notion runbook: [How to Request Database Group
Access][1].

[1]: https://www.notion.so/345b0b10ae8c80b7a9ede57ff7975ece
