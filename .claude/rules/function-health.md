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
- **`fh-databricks`**: Workspace URLs, CLI OAuth profiles, the
  birthright vs ConductorOne access trap, the persona/data-reader
  two-gate model, and headless SQL via the statement execution API.
- **`fh-datadog`**: Datadog API authentication (`us5` site) and local
  monitor-query validation via `/monitor/validate`.
- **`fh-kubernetes`**: GKE kubeconfig generation for the `dev`, `prod`,
  and `sandbox` clusters.

## My User

Identifiers for my personal Function Health user, per environment. The
email is the same across environments; the UUID and patient ID differ.

### Dev

- **Email**: `nickolas.kraus@functionhealth.com`
- **UUID**: `d089c262-1870-4ba1-a27e-cd143ebf7ffb`
- **Patient ID**: `QFnSbFxRxrYCHKJ3`

### Prod

- **Email**: `nickolas.kraus@functionhealth.com`
- **UUID**: `9ea69134-f7a1-41fc-b79b-63b5b0158fa6`
- **Firebase UID**: `xToN9OwB5ISaLhYtcDI1M39g8zR2`
- **Patient ID**: TODO. The `patient_identifier` lives only in the
  PHI-gated `patient` table in the Prod monolith, which my
  non-PHI DB role cannot read.

## My Dev QA Accounts

Personal QA/test users in Function Health Dev, keyed by plus-addressed
email on my `nickolashkraus`/`nickolas.kraus` bases. The `UUID` is
`patient.id`, `Patient ID` is `patient.patient_identifier`, and
`Firebase UID` is `patient.patient_firebase_id`.

| Email                                         | Name                                 | UUID                                   | Patient ID         | Firebase UID                   | Joined     |
| --------------------------------------------- | ------------------------------------ | -------------------------------------- | ------------------ | ------------------------------ | ---------- |
| `nickolashkraus+ppp-qa-1@gmail.com`           | PPP QA One                           | `27d8c597-6107-4523-ad99-f5ea4f695be1` | `dcXCWfAxaiCW7fGi` | `b1rgf9giWVcGsmp0jlZiHSqOIAU2` | 2026-07-09 |
| `nickolashkraus+ppp-qa-3@gmail.com`           | PPP QA Three                         | `1e4eeb1f-236c-48fb-97b9-6856514346dd` | `ZFPywmGtsqZyNY2E` | `2kFO2d48NaTy9MpnpIHCCwaTJJR2` | 2026-07-09 |
| `nickolashkraus+ppp-qa-5@gmail.com`           | PPP QA Five                          | `86dafb7b-5395-4ad3-bb45-66145a5d39bb` | `tToBAfu8Q6KQijuW` | `kRWshaqvyYbWwaMWVupCuDbqAdv1` | 2026-07-09 |
| `nickolashkraus+ppp-qa-7@gmail.com`           | PPP QA Seven                         | `d486f334-3773-48a7-9a5e-9bfd971faf30` | `gtqf6rUG4WGgkUwL` | `5Y59Sl4gwxXLcModR6tRK2WYvit1` | 2026-07-10 |
| `nickolashkraus+ppp-qa-9@gmail.com`           | PPP QA Nine                          | `93b6d57d-cb5a-4765-908d-b515d4ca711a` | `Vtx9q5yppstztzMM` | `luWBdpo3FGNfYIWcbdwiKVxRHTA3` | 2026-07-10 |
| `nickolashkraus+ppp-qa-10@gmail.com`          | PPP QA Ten                           | `b2f0ee37-0e9c-4919-ae63-6519f6051f55` | `RhJe2eTNCom99MPV` | `X1QMdEunZnVuNoHKgCbpRoX7HK42` | 2026-07-10 |
| `nickolas.kraus+ppp-qa-p1@functionhealth.com` | QA PPPTester                         | `9191e8ce-e980-4fec-a6bc-74f699c57096` | `rCYtAjmszJVeQXXD` | `qBSSXF3EhGNXUarjjWgczTiZbU33` | 2026-07-09 |
| `nickolas.kraus+byb1896@functionhealth.com`   | Nickolas-Enterprise Kraus-Enterprise | `ed102123-e189-4c80-a907-5a479c9cbaf6` | `75YjXkozkA5MM4an` | `ig7IRk1dCFhkdc0vS5XhIiaQMfr2` | 2026-05-22 |
| `nickolas.kraus+family-qa@functionhealth.com` | Nickolas Kraus                       | `f4e5f658-e8a4-4f13-a740-02f5f31a28c0` | `NbTSntea9HhdFRz2` | `gNWOjRRtXRbyQMTJmJqUJUnCws43` | 2026-08-14 |
| (none)                                        | PPPLink QAThrowaway                  | `73d67832-1cc2-443c-953b-c928369436a1` | `k9naSNSmRBJHivX4` | (none)                         | 2026-07-10 |

Notes:

- The `byb1896` account is my enterprise test user (BYB-1896). The
  `family-qa` account is for family-plan QA.
- The `PPPLink QAThrowaway` row has no contact email or Firebase UID,
  so it cannot be attributed by email; it is almost certainly my PPP
  payment-link throwaway based on name and creation date.
- To rediscover accounts, sweep the Dev monolith `patient` table by
  name (`lname ilike '%kraus%'`, plus the `PPP`/`PPPTester` fname
  patterns) and cross-check Firebase Auth, not just
  `patient_contact_info.email`. Fresh accounts can have a `patient`
  row before any contact-info email row exists, so an email-only scan
  misses them.

## Dev Member App DevTools

The Dev member app exposes a `/devtools` page that gets and sets member
values (useful for QA account setup and state manipulation):

- URL: https://development-members-app-2jv3ndpkoa-ue.a.run.app/devtools

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
