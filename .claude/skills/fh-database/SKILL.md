---
name: fh-database
description: >
  Function Health database access via Cloud SQL Auth Proxy. Covers Dev/Staging
  instances (static `POSTGRES_PASSWORD` from Secret Manager) and Prod instances
  (IAM group authentication via ConductorOne entitlements and `gcloud auth
  print-access-token`). TRIGGER when: user wants to query the FH
  Dev/Staging/Prod database, set up Cloud SQL Auth Proxy, or troubleshoot
  Postgres auth for FH.
disable-model-invocation: false
allowed-tools: Bash, Read
---

Function Health database access runbooks. Invoke this skill when you
need to connect to an FH Postgres instance locally: looking up the
Cloud SQL instance, starting the Auth Proxy, and authenticating
(static creds for Dev/Staging, IAM group for Prod).

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

   - `db <env> <instance> ro|rw|adm Group Member` (e.g., `db prod
     production-transaction ro Group Member`).
   - `Cloud SQL Instance User` on the relevant project (e.g., `Function Health
     Prod env`). This is what authorizes the IAM database login. `Cloud SQL
     Client` alone is not enough.

   ```bash
   cone search --query "<instance>" --granted
   cone search --query "Cloud SQL Instance User" --granted
   cone get --query "Cloud SQL Instance User" --justification "<reason>"
   ```

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
