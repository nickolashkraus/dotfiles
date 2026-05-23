# Function Health

## CLI Authentication

- **Auth0**: Authenticate with `auth0 login`.
- **ConductorOne**: Authenticate with
  `cone login https://functionhealth.conductor.one`.

## API (Secret) Key Authentication

Some Function Health services authenticate via `FunctionHealthSecretKey`, which
expects a Fernet-encrypted JSON payload in the `Authorization` header. To
generate a token for a deployed environment:

1. Get the service's secret key from GCP Secret Manager.

   Check the Cloud Run service description for the secret name (often
   `QUEST_FH_SECRET_KEY` or similar, not necessarily `FH_SECRET_KEY`):

   ```bash
   gcloud run services describe <service> --region=us-west1 \
     --format=yaml | grep -A3 FH_SECRET
   gcloud secrets versions access latest --secret=<secret-name>
   ```

2. Get the registered services list to find a valid sender:

   ```bash
   gcloud secrets versions access latest \
     --secret=<SERVICE>_REGISTERED_SERVICES
   ```

3. Generate the token:

   ```python
   from cryptography.fernet import Fernet
   import json
   key = b"<secret-key>"
   payload = json.dumps({"sender": "<registered-sender>"}).encode()
   token = Fernet(key).encrypt(payload).decode()
   ```

## Cloud Run Proxy

Cloud Run services with ingress set to `internal-and-cloud-load-balancing` are
not reachable from the public internet. Use `gcloud run services proxy` to
access them locally:

```bash
gcloud run services proxy <service> --region=<region> \
  --project=<project> --port=8080
```

Then access the service at `http://localhost:8080`.

## Admin App GraphQL Authentication

`admin-app-backend` is the staff (Ops) GraphQL surface (patient lookups, the
`updatePatient` mutation, etc.). Its `IsAuthorized` permission class checks
`auth_handler.current_user`, populated by `jwt.decode(...)` against a Function
Health auth-service public key (`app/core/authorization.py`). It does **not**
accept Okta ID tokens, Auth0 tokens, or NextAuth session cookies directly.
Hitting `/graphql` with any of those returns `"Not authenticated"`.

NextAuth attaches the FH JWT to outgoing GraphQL requests server-side, so the
browser never sees it on `/graphql` Request Headers, and the
`next-auth.session-token` cookie itself is a zlib-compressed encrypted blob (no
dots), not a JWT. The browser-visible artifact is the upstream Okta ID token,
exposed under `accessToken` in the JSON response of `GET /api/auth/session`.
Use that to mint an FH JWT via the exchange below.

To mint one:

1. Sign into the Admin App. DevTools Network -> filter `auth/session` -> click
   the `GET /api/auth/session` request -> Response tab. Copy the `accessToken`
   field. It is an Okta ID token (three dot-separated segments starting with
   `eyJraWQi...`, with `iss=https://functionhealth.okta.com` in the
   base64-decoded payload).
2. Exchange it via `auth-service`'s
   `POST /api/v1/login/okta` endpoint:

   ```bash
   gcloud run services proxy development-auth-service \
     --region=us-central1 --project=function-health-dev-env --port=8092 &
   curl -s -X POST -H "content-type: application/json" \
     -d "{\"token\":\"$OKTA_TOKEN\"}" \
     http://localhost:8092/api/v1/login/okta \
     | jq -r .access_token
   ```

   For Prod, swap in `production-auth-service` and
   `--project=function-health-prod-env`.

3. Use the returned `access_token` as `Authorization: Bearer <token>` against
   admin-app-backend's `/graphql`:

   ```bash
   gcloud run services proxy development-admin-app-backend \
     --region=us-central1 --project=function-health-dev-env --port=8091 &
   curl -s -X POST -H "content-type: application/json" \
     -H "Authorization: Bearer $FH_TOKEN" \
     -d '{"query":"query{ patientByEmail(email:\"alice@example.com\"){ id isEnterprise } }"}' \
     http://localhost:8091/graphql
   ```

Useful queries and mutations:

- `patientByEmail(email: String!)`: Best lookup when you have only an email.
  Returns `id`, `patientIdentifier`, `isEnterprise`, etc.
- `patientByPatientIdentifier(patientIdentifier: String!)`: Lookup by the
  Firebase-style identifier.
- `updatePatient(id: UUID!, patientInput: PatientUpdate)`: Mutation for staff
  edits. `patientInput.isEnterprise: Boolean` is the field for enterprise-flag
  flips. Example:

  ```graphql
  mutation {
    updatePatient(id: "ed102123-e189-4c80-a907-5a479c9cbaf6",
                  patientInput: {isEnterprise: false}) {
      id isEnterprise
    }
  }
  ```

The FH `access_token`'s `permissions` claim controls which mutations are
authorized; a basic `Admin Dev` / `Admin Prod` group membership grants the
common read/write set including `updatePatient`. The token's `exp` is short
(about an hour); re-run the Okta exchange to refresh.

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

## GKE kubeconfig

Function Health GKE clusters live across `function-health-dev-env`,
`function-health-prod-env`, and `function-health-sandbox-env`. To generate or
refresh `~/.kube/function.yaml`, run:

```bash
generate-fh-kubeconfig --output $HOME/.kube/function.yaml
```

The script lives at
`~/nickolashkraus/bash-scripts/master/generate-fh-kubeconfig` and queries
`gcloud container clusters describe` for each cluster, so it requires
`Kubernetes Engine Admin` (or read-equivalent) on the relevant projects via
ConductorOne.

## Backend Coding Conventions

### Architecture

Services use a 6-layer pattern: `api/` -> `schemas/` -> `services/` ->
`models/` -> `listeners/` -> `utils/`. Dependencies flow top-down only. Never
import upward (e.g., models must not import services).

### Transaction Management

The API layer commits; services never call `db.commit()`. This keeps services
composable across multiple calls in one transaction.

### Error Handling

- Services raise custom domain exceptions (`ServiceError`, `NotFoundError`,
  `InvalidTransitionError`, `GraphQLError`, `OptimisticLockingError`), never
  `HTTPException`.
- Custom exceptions take context as a dict in the second positional arg: `raise
  NotFoundError("msg", {"id": val})`. No custom `__init__`.
- The API layer registers exception handlers that convert domain exceptions to
  HTTP responses.
- Never log an error then raise. The global exception handler logs
  automatically. Duplicate logging wastes GCP budget and clutters analysis.
- Always chain exceptions with `from e`.

### Logging

- Structured logging via `extra={"json_fields": {...}}`.
- Cast UUIDs to `str()` inside `json_fields`.
- Use `exc_info=e` (not `exc_info=True`).
- Use pattern strings in logger calls (no f-strings) so identical messages
  aggregate.

### Database

- SQLModel over plain SQLAlchemy.
- Every foreign key must have `index=True`.
- Soft delete via indexed `deleted_at` field, not row removal.
- `AuditMixin` provides `created_at`/`updated_at`/`created_by`.
- Access models through module namespace (`gifting.Patient`, not bare
  `Patient`).
- `SessionDep` type alias lives in `app/utils/dependencies.py`.
- `expire_on_commit=False` on the session factory.
- `get_session_maker()` cached with `@functools.lru_cache(maxsize=1)`.
- Audit trails use SQLAlchemy `after_update` event listeners in
  `app/listeners/audit_trail.py`.

### Pub/Sub

- Push endpoints: route prefix `/api/v1/pubsub/push_subscriptions`; function
  names end with `_subscription`; route constants end with `_EVENT`; OIDC token
  auth; handlers must be idempotent.
- Pull subscriptions: inherit `BaseSubscriptionService[PayloadType]`;
  `_process_event` must not commit or rollback; dead letter after 5 attempts;
  subscription names lowercase-with-hyphens ending `-subscription`.
- Schemas: `PubSubMessage` > `Message` > `MessageAttributes` hierarchy; event
  schemas end in `Event`; `PubSubTopics` class for centralized topic IDs; check
  `GOOGLE_CLOUD_PROJECT` before publishing (silently skip if unset); publish
  then commit DB.

### GraphQL (Strawberry)

- All mutations require `permission_classes=[permission.IsAuthorized]`.
- Class naming: `MutationEntityName`, `QueryEntityName`.
- `info: "context.Info"` (string annotation with quotes).
- Use `strawberry.UNSET` for optional update fields, not `None`.
- `db` from `info.context.db`; `user` from `info.context.user`.

### Pagination

- Use `CursorWithTotalPage[T]` from `fastapi-pagination`.
- Always add a default `order_by(models.Item.id)` for cursor stability.
- Ordering convention: `field` (asc), `-field` (desc).

### Finite State Machines

- Use the `transitions` library with a dedicated state manager class.
- Define a `TERMINAL_STATES` constant.
- Make transitions idempotent (state listed in its own source list).
- Instantiate FSMs in the service layer only, never on models.

### Constants and TODOs

- `typing.Final` for all constants; immutable collections only (`tuple`,
  `frozenset`), never `list` or `set`.
- TODO format: `# TODO(username): Description.` with a Linear issue on the next
  line (`# FUN-123`). Use `NOBUG-1` for untracked items. `FIXME` is reserved
  for known bugs.

### Testing

- pytest with `asyncio_mode = "auto"`.
- `factory_boy` for test data; `pytest-httpx` for HTTP mocking.
- Database fixtures use transaction rollback.
- Unit test files named `{module}_test.py` alongside implementation.

### CI/CD

- Three standard workflows: `pytest.yml`, `ruff.yml`, `type_check.yml`.
- Python 3.12; Poetry with venv caching.
- Shared actions from `Function-Health/actions`.
- Pyright with `skip-unannotated: true`.
- Line-length 100.

### Git Conventions

Follow @rules/git.md.

## Services/Repo-specific

### Service Naming

Service names use either their repo name (`transaction-service`) or Title Case
(Transaction Service), never a hybrid like Transaction-Service.

### Member App Middleware (MAM)

Always review member-app-middleware PRs against the guidelines in
`.github/docs/CONTRIBUTING.md` before submitting.
