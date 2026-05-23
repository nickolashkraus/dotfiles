# Function Health

## Operational Runbooks

Runbook content has been moved into on-demand skills to keep this rule
file behavior-focused. Invoke the relevant skill when you need the
procedure:

- **`fh-auth`**: CLI login (Auth0, ConductorOne), API secret-key
  (Fernet) token generation, Cloud Run proxy for internal services,
  Admin App GraphQL token exchange (Okta -> FH JWT).
- **`fh-database`**: Cloud SQL Auth Proxy for Dev/Staging (static
  `POSTGRES_PASSWORD`) and Prod (IAM group auth via ConductorOne).
- **`fh-kubernetes`**: GKE kubeconfig generation for the `dev`, `prod`,
  and `sandbox` clusters.

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
