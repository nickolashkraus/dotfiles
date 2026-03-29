# Function Health

## API (Secret) Key Authentication

Some Function Health services authenticate via `FunctionHealthSecretKey`, which
expects a Fernet-encrypted JSON payload in the `Authorization` header. To
generate a token for a deployed environment:

1. Get the service's secret key from GCP Secret Manager.

   Check the Cloud Run service description for the secret name (often
   `QUEST_FH_SECRET_KEY` or similar, not necessarily `FH_SECRET_KEY`):

   ```
   gcloud run services describe <service> --region=us-west1 \
     --format=yaml | grep -A3 FH_SECRET
   gcloud secrets versions access latest --secret=<secret-name>
   ```

2. Get the registered services list to find a valid sender:

   ```
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

```
gcloud run services proxy <service> --region=<region> \
  --project=<project> --port=8080
```

Then access the service at `http://localhost:8080`.

## Cloud SQL Auth Proxy

Function Health databases run on private VPC IPs and are not directly reachable
from local machines. Use the Cloud SQL Auth Proxy to tunnel in:

1. Find the Cloud SQL instance:

   ```
   gcloud sql instances list --project=<project> \
     --filter='name~<service>'
   ```

2. Start the proxy:

   ```
   cloud-sql-proxy <connection-name> --port=5433
   ```

3. Connect using `localhost:5433` as the host and port.

Database credentials (e.g., `POSTGRES_USER`, `POSTGRES_PASSWORD`,
`POSTGRES_DB`) are stored in GCP Secret Manager. Check the Cloud Run service
description for the secret names:

```
gcloud run services describe <service> --region=<region> \
  --format=yaml | grep -A4 POSTGRES
gcloud secrets versions access latest \
  --secret=<secret-name> --project=<project>
```

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
- unittest files named `{module}_test.py` alongside implementation.

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
