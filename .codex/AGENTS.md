# Codex Harness

These instructions mirror the Claude harness in `.claude/`. Follow them for
Codex sessions so the working style, rules, and operational expectations match
Claude. The model is the only intended difference.

## Rule Sources

The source rule files live in `.codex/rules/` in this dotfiles worktree and
`~/.codex/rules/` when installed globally. The full rule text is included below
so Codex receives it at session start. Path mentions such as
`~/.codex/rules/meta-learning.md` are references, not import directives.

## coding

### Codebases

- **Function Health**: ~/Function-Health
- **Function Health Terraform Modules**: ~/Function-Health-Terraform-Modules
- **Infrable**: ~/infrable-io
- **Grind**: ~/grind-rip
- **Personal**: ~/nickolashkraus

### Comments

- Follow ~/.codex/rules/typography.md for all comments.
- Only add comments where the logic is not self-evident. The code should speak
  for itself.
- Never add decorative section dividers (e.g., `# --- Section ---`, `#
  ========`, `# *** Helpers ***`). Use whitespace and code structure to convey
  organization.
- Never add comments that merely restate the function or variable name (e.g.,
  `# Get the user` above `get_user()`).
- Never add trailing comments that narrate what a line does (e.g., `x
  = 1  # set x to 1`).

### Testing

- Write unit tests when appropriate. Tests should validate behavior and prevent
  regressions, particularly for business logic, edge cases, and functions with
  multiple code paths. Aim for 100% test coverage, but avoid tests for trivial
  code or framework-generated scaffolding. Use your best judgment.

### Migrations

- Separate schema changes (DDL) and data changes (DML) into distinct
  migrations. DDL migrations handle structural changes (`CREATE TABLE`, `ALTER
  TABLE`, `ADD COLUMN`). DML migrations handle data operations (`INSERT`,
  `UPDATE`, `DELETE`). This allows each to land, fail, and roll back
  independently.

### Docker

- Always build Docker images that are not intended to be run locally for
  `linux/amd64` (`--platform linux/amd64`) to ensure compatibility with
  external cloud environments (AWS, Google Cloud, etc.).

## function-health

### CLI Authentication

- **Auth0**: Authenticate with `auth0 login`.
- **ConductorOne**: Authenticate with
  `cone login https://functionhealth.conductor.one`.

### API (Secret) Key Authentication

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

### Cloud Run Proxy

Cloud Run services with ingress set to `internal-and-cloud-load-balancing` are
not reachable from the public internet. Use `gcloud run services proxy` to
access them locally:

```
gcloud run services proxy <service> --region=<region> \
  --project=<project> --port=8080
```

Then access the service at `http://localhost:8080`.

### Cloud SQL Auth Proxy

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

#### Prod Databases (IAM Group Auth)

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

   ```
   cone search --query "<instance>" --granted
   cone search --query "Cloud SQL Instance User" --granted
   cone get --query "Cloud SQL Instance User" --justification "<reason>"
   ```

2. Start the proxy with `--auto-iam-authn`:

   ```
   cloud-sql-proxy <connection-name> --port=5434 --auto-iam-authn
   ```

3. Connect using your Workspace email as the user and a fresh `gcloud` access
   token as the password. The token expires after ~1 hour, so regenerate it per
   session:

   ```
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

### GKE kubeconfig

Function Health GKE clusters live across `function-health-dev-env`,
`function-health-prod-env`, and `function-health-sandbox-env`. To generate or
refresh `~/.kube/function.yaml`, run:

```
generate-fh-kubeconfig --output $HOME/.kube/function.yaml
```

The script lives at
`~/nickolashkraus/bash-scripts/master/generate-fh-kubeconfig` and queries
`gcloud container clusters describe` for each cluster, so it requires
`Kubernetes Engine Admin` (or read-equivalent) on the relevant projects via
ConductorOne.

### Backend Coding Conventions

#### Architecture

Services use a 6-layer pattern: `api/` -> `schemas/` -> `services/` ->
`models/` -> `listeners/` -> `utils/`. Dependencies flow top-down only. Never
import upward (e.g., models must not import services).

#### Transaction Management

The API layer commits; services never call `db.commit()`. This keeps services
composable across multiple calls in one transaction.

#### Error Handling

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

#### Logging

- Structured logging via `extra={"json_fields": {...}}`.
- Cast UUIDs to `str()` inside `json_fields`.
- Use `exc_info=e` (not `exc_info=True`).
- Use pattern strings in logger calls (no f-strings) so identical messages
  aggregate.

#### Database

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

#### Pub/Sub

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

#### GraphQL (Strawberry)

- All mutations require `permission_classes=[permission.IsAuthorized]`.
- Class naming: `MutationEntityName`, `QueryEntityName`.
- `info: "context.Info"` (string annotation with quotes).
- Use `strawberry.UNSET` for optional update fields, not `None`.
- `db` from `info.context.db`; `user` from `info.context.user`.

#### Pagination

- Use `CursorWithTotalPage[T]` from `fastapi-pagination`.
- Always add a default `order_by(models.Item.id)` for cursor stability.
- Ordering convention: `field` (asc), `-field` (desc).

#### Finite State Machines

- Use the `transitions` library with a dedicated state manager class.
- Define a `TERMINAL_STATES` constant.
- Make transitions idempotent (state listed in its own source list).
- Instantiate FSMs in the service layer only, never on models.

#### Constants and TODOs

- `typing.Final` for all constants; immutable collections only (`tuple`,
  `frozenset`), never `list` or `set`.
- TODO format: `# TODO(username): Description.` with a Linear issue on the next
  line (`# FUN-123`). Use `NOBUG-1` for untracked items. `FIXME` is reserved
  for known bugs.

#### Testing

- pytest with `asyncio_mode = "auto"`.
- `factory_boy` for test data; `pytest-httpx` for HTTP mocking.
- Database fixtures use transaction rollback.
- unittest files named `{module}_test.py` alongside implementation.

#### CI/CD

- Three standard workflows: `pytest.yml`, `ruff.yml`, `type_check.yml`.
- Python 3.12; Poetry with venv caching.
- Shared actions from `Function-Health/actions`.
- Pyright with `skip-unannotated: true`.
- Line-length 100.

#### Git Conventions

Follow ~/.codex/rules/git.md.

### Services/Repo-specific

#### Service Naming

Service names use either their repo name (`transaction-service`) or Title Case
(Transaction Service), never a hybrid like Transaction-Service.

#### Member App Middleware (MAM)

Always review member-app-middleware PRs against the guidelines in
`.github/docs/CONTRIBUTING.md` before submitting.

## git

### General

- Follow ~/.codex/rules/typography.md for all Git content (PR descriptions,
  commit messages).
- Never add a co-authored-by or signature to commits
  (e.g., `Co-Authored-By: AI Assistant <noreply@example.com>`).
- Branch names should be the Linear issue slug (e.g., `BYB-1337`) if
  available, or a short description (e.g., `some-feature`).
- Pull request titles should include the Linear issue (if provided) (e.g.,
  `EPD-1337: ...`).
- If a change has interesting or nuanced information, add it to the Git commit
  and PR description.

### Worktrees

- Always create worktrees in the root of the bare repo as peer directories
  (e.g., `transaction-service/BYB-934` alongside `transaction-service/dev`).
  Never place them under subdirectories like `.codex/worktrees/`.
- In a bare repo with worktrees, default to the `master` (or default) branch
  worktree for operations like `git log`, `git diff`, and rebasing. Do not
  operate from the bare repo root.

### Commits

#### Commit Messages

- **Subject line** (first line):
  - 50 characters or less
  - Capitalized, imperative mood (e.g., "Fix bug in user login flow")
  - No period at the end
- **Blank line** between subject and body
- **Body** (optional):
  - Wrap lines at 72 characters
  - Explain *what* and *why*, not *how*
- Never use "WIP" or other throwaway messages.
- Use bulleted lists for Git messages, not long, comma-separated items.

#### Squashing Commits

A pull request should contain a single commit unless each commit represents
a logical grouping of changes. If you commit often during development, squash
before merging.

#### Pushing

Always run CI (tests, linting) locally before pushing. Do not push code that
you have not verified passes the project's CI.

After pushing, run `$fix-ci` until all checks pass. Do not consider the job
done while any check is non-passing (including neutral or pending).

#### Retriggering CI

Never close and reopen a pull request to retrigger CI. It rewrites timestamps,
fires PR-lifecycle webhooks with side effects, and leaves the original failed
check as a stuck record (a new check run is created under a different name, so
it does not replace the old one). For transient or infrastructure failures,
follow the documented retry path for that provider (`gh run rerun --failed` for
GitHub Actions, `check-runs/<id>/rerequest` or the provider's native retry API
for external checks). If the failed check is a stale artifact (e.g., Cloud
Build "Couldn't read commit" raced with `gh pr create`), verify it is not in
the branch's required-status-checks ruleset before treating it as blocking. Do
not reach for destructive shortcuts like close/reopen, force-push, or empty
commits to make a failed check go away.

#### Rebasing

Do not merge master into a branch to integrate upstream changes. Use `git
rebase` instead.

### Stacked PRs

For dependent changes, stack PRs by targeting each PR against its parent branch
(e.g., `BYB-1053` targets `BYB-891`, `BYB-1054` targets `BYB-1053`). This keeps
each review focused on only the relevant delta. When a parent branch merges
and is deleted, GitHub automatically retargets the child PR to the default
branch.

### Pull Requests

#### General Rules

- Lead with the "what" using a declarative verb ("Adds", "Removes",
  "Determines", "Retrieves"). Do not write "This PR does..." or "In this PR,
  I...".
- Explain the "why" when the change is not self-evident.
- Use blockquotes when quoting documentation or specs.
- Use footnotes for detailed technical asides.
- Include code snippets for commands, examples, API usage, or error messages.
- Use `**NOTE**` blocks for important context that is secondary to the main
  change.
- Do not add boilerplate sections (e.g., "## Summary", "## Test plan") when the
  change does not warrant them.
- Do not use hard line breaks within paragraphs. Markdown renderers handle
  wrapping, so each paragraph should be a single unwrapped line.
- When adding PR review comments, attach them to the specific line or line
  range in the diff where the issue occurs.

#### Descriptions

Scale the description with the complexity of the change.

##### Trivial Changes

Use a single declarative sentence or leave the body empty.

```
Service should not be publicly available.
```

```
Determines document upload status from Google Cloud Storage.
```

##### Small to Medium Changes

Open with a brief declarative summary (no header needed). Include code
snippets, error messages, or links to related code when they add clarity.

Use `**NOTE**` or `**NOTE**:` for important asides or to call out secondary
decisions (e.g., refactoring done alongside the main change).

```
Fixes the following error:
\`\`\`
error: "GcpStorageConfig" is not a known attribute of module "gcp_storage_sdk"
\`\`\`

Basically just makes the module's public API more clear and fixes the pyright error.
```

##### Larger Changes

Use `## Overview` as the primary header with a concise summary. Add additional
sections as needed:

- `## Implementation Details` for how it works, with commands or code examples.
- `## Testing` for a checklist of verification steps.
- `## References` for links to documentation, related issues, or specs.

```
## Overview

Adds authentication to the MCP server using Auth0.

## Implementation Details

This adds authentication to the MCP server for protected MCP tool calls.

Run the MCP server:

\`\`\`bash
poetry run uvicorn ai_chat.apps_sdk.server.main:app --host 0.0.0.0 --port 8000
\`\`\`
```

## gws

- ALWAYS check the entire Google Sheet, not just the first X rows.
- ALWAYS use `gws` to access Google Drive files. Do not use MCP tools or other
  methods to read Google Docs, Sheets, or other Drive files.
- ALWAYS use the full `gws <service> <resource> <method>` pattern. Do not omit
  the resource name. For example:
  - `gws docs documents get` (correct), not `gws docs get` (wrong).
  - `gws sheets spreadsheets get` (correct), not `gws sheets get` (wrong).
- ALWAYS use `--page-all` to fetch all items from paginated endpoints. When
  using `--params` with a `fields` mask, include `nextPageToken` in the mask.
  Without it, `gws` cannot detect additional pages and silently returns only
  the first page.
- For methods with a request body (e.g., `gmail messages modify`, `gmail
  messages send`), pass body fields via `--json`, not `--params`. `--params` is
  only for URL/query parameters like `userId` and `id`.

### Account Switching

- Determine the profile from the working directory:
  - `~/Function-Health/*`: Use `function` profile.
  - Everything else: Use `personal` profile.
- For `gws`, always inline the profile since env vars do not
  persist across Bash calls:
  `GWS_PROFILE=function gws ...`
  `GWS_PROFILE=personal gws ...`
- For `gcloud`, activate the matching configuration:
  `gcloud config configurations activate function-dev`
  `gcloud config configurations activate personal`

## linear

- Follow ~/.codex/rules/typography.md for all Linear content.
- Issue titles should use Title Case.
- Issue statuses should default to Todo.
- Remove extra newlines (e.g., if lines use &lt;80 characters for human
  readability). If available, use the `clean_markdown.py` script.
- Add links to GitHub, Notion, etc. when appropriate.
- When creating issue descriptions, do not use explicit file line numbers or
  ranges.

Linear issues should use the following format:

```
## Overview

## Acceptance Criteria

## Implementation Details

## References
```

- For references, use actual links (GitHub, Linear, Notion, etc.).

## notion

- Follow ~/.codex/rules/typography.md for all Notion content.
- Remove extra newlines (e.g., if lines use &lt;80 characters for human
  readability). If available, use the `clean_markdown.py` script.

## secrets

Personal API keys and credentials live in the macOS Login Keychain. Use the
`security` CLI to retrieve them. Never write a secret value to a file, embed
one as a literal in a command line, or echo one back to the user in chat
output. Always retrieve via command substitution at point of use.

### Retrieval

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

### Inventory

All entries below use the account `function-health`.

| Service                      | Purpose                        |
| ---------------------------- | ------------------------------ |
| `conductorone-client-id`     | ConductorOne PCC client ID     |
| `conductorone-client-secret` | ConductorOne PCC client secret |
| `statsig-console`            | Statsig Console API key        |
| `stripe-test`                | Stripe restricted key (Test)   |
| `stripe-prod`                | Stripe restricted key (Live)   |

### Per-Application Usage

#### ConductorOne (`cone`)

Pass both `client_id` and `client_secret` as flags:

```
cone \
  --client-id "$(security find-generic-password -s conductorone-client-id -a function-health -w)" \
  --client-secret "$(security find-generic-password -s conductorone-client-secret -a function-health -w)" \
  whoami
```

Alternatively, configure them once via `cone login` and omit the flags.

#### Statsig

Statsig's Console API authenticates via the `STATSIG-API-KEY` header:

```
curl \
  -H "STATSIG-API-KEY: $(security find-generic-password -s statsig-console -a function-health -w)" \
  -H "Content-Type: application/json" \
  https://statsigapi.net/console/v1/gates
```

#### Stripe

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

### Adding a New Secret

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

### When Not to Use the Keychain

- **Function Health service secrets**: Service-to-service credentials live in
  GCP Secret Manager. Fetch via
  `gcloud secrets versions access latest --secret=<name>`. See
  ~/.codex/rules/function-health.md.
- **Ephemeral tokens**: Short-lived tokens (e.g.,
  `gcloud auth print-access-token`) should be generated inline, not cached.

## slack

- Follow ~/.codex/rules/typography.md for all Slack content.
- ALWAYS send messages using the `slack_send_message_draft` tool, never
  `slack_send_message`. The user reviews and approves drafts before they
  are sent.

### Tables

When sharing a Markdown table or tabular data in Slack, convert it to TSV
(tab-separated values). Pasted TSV renders as a native formatted table in
Slack.

- Use tabs (`\t`) to separate columns. Do not use literal spaces or
  Markdown pipes.
- Strip Markdown formatting (e.g., `**bold**` becomes `bold`). Slack
  applies its own styling.
- The first row is the column headers.

## typography

- Never use em dashes.
- Never use smart quotes, only straight quotes.
- Add a period to the end of bulleted lists. Exception: do not add
  periods to single-word or short-phrase list items (e.g., field
  name enumerations like "Name", "Price", "Description").
- Keep lines &lt;80 characters for human readability. Break lines at the last
  word boundary before column 80, maximizing line length. Use the Vim `gq`
  formatting behavior.
- For lists, use the format (when appropriate):

  ```markdown
  - **Element**: A short description
  ```

- In bulleted or numbered lists, use a colon after the lead-in element, not
  a dash. For example:
  `` `GET /foo`: Does something ``
  not
  `` `GET /foo` - Does something ``

- When formatting Markdown tables, use the following format:

  | Column 1 | Column 2 | Column 3 |
  | -------- | -------- | -------- |
  | x        | y        | z        |

  Pad all columns to equal width with a 1-space buffer on each side. When
  modifying a table, always reformat the entire table to maintain even spacing.

- Use backticks for inline code, file names, commands, resource names, and
  configuration values (e.g., `python`, `app.py`, `GET /api/users`).
- For Markdown files, use HTML escape characters (&lt;, &gt;, etc.). Escape \$.
  These characters break syntax highlighting in Vim, except when inside
  backticks (`<br>`).
- Markdown reference links should use `[text][label]`. Do not use the
  `[label][]` shorthand or bare `[label]` form, even when the text and label
  are the same.
- Use double space instead of `<br>` for newlines in Markdown.
- Capitalize environment names: Dev, Staging, Prod. Treat them as proper nouns.
- Capitalize the first word after a colon when it begins a complete sentence or
  independent clause.
- Always put colons outside of bold text (e.g., **Bold**:).
- For YAML strings, follow these conventions:
  - Use unquoted strings by default when the value contains no special
    characters.
  - Use double quotes when the value contains special characters or
    YAML-special characters (e.g., `:`, `#`, `{`, `}`, `[`, `]`, `,`, `&`, `*`,
    `!`, `|`, `>`, `'`, `"`, `%`, `@`, `` ` ``). This includes escape sequences
    (e.g., `\n`, `\t`, `\\`).
  - Use literal block scalars (`|`) for multi-line strings that must preserve
    newlines.
  - Use folded block scalars (`>`) for multi-line strings that should be joined
    into a single line.
- Always put periods outside double quotes unless the quote actually contains
  a period.
- Place footnote markers after all punctuation (e.g., `sentence.[^1]`, not
  `sentence[^1].`).
- Use a comma before "but" when it joins two independent clauses.

## writing

This guide codifies the writing style used by Nickolas Kraus. Follow these
conventions when writing or editing blog posts, articles, and essays.

### Voice and Tone

- Write in active voice. Reserve passive voice for describing system behavior
  where the acting agent is the infrastructure itself.
- Be direct and confident. State assertions plainly without hedging or
  over-qualifying.
- Maintain a professional but approachable tone. Not stiff academic prose, not
  casual slang.
- Inject personality through dry humor, self-aware asides, and footnotes rather
  than through the main body text.
- Do not apologize for complexity. Present technical information
  matter-of-factly with the expectation that the reader can follow along.
- Vary register by content type: use precise, economical language for technical
  posts; allow richer, more literary vocabulary for personal essays and
  reviews.

### Person

- Use "I" freely for personal experience, methodology, decisions, and opinions.
- Use "we" when walking the reader through a shared exercise or describing team
  efforts.
- Use "you" and imperative mood for instructions ("Create the required
  directories", "Mount the root partition").
- Do not use "I think" or "in my opinion" as softeners. State opinions as
  convictions.

### Sentence Structure

- Keep sentences short to medium length (10-25 words on average).
- Favor declarative statements. Follow a short declarative sentence with
  a longer explanatory one for rhythm.
- Use rhetorical questions as structural transitions: "First, what is a FIT
  file?"
- Use semicolons to join related independent clauses when appropriate, but do
  not overuse them.

### Paragraphs

- Keep paragraphs short: 1-4 sentences for technical content, up to 5-6 for
  essays.
- Use single-sentence paragraphs for transitional or summary statements.
- Always use a single introductory sentence before a code block. Do not launch
  into a code block without context.

### Structure and Headers

- Use `##` (H2) as the primary structural divider, `###` for subsections,
  `####` for sub-subsections.
- Use descriptive, action-oriented headers, not clever or vague ones.
- Use the "Problem / Solution" structure for posts that solve a specific issue.
- Use numbered "Step N:" headers for tutorial walkthroughs.
- Use "## Overview" to open longer posts when appropriate.
- Use "## Conclusion" or "## Summary" sparingly and only in longer posts. Keep
  it to 1-3 sentences.
- Use Title Case for section headers.

### Openings

- Lead with personal context or a concrete statement, then state the article's
  purpose: "In the course of building an MCP server, I became somewhat of an
  expert on..."
- For tutorials, a direct declarative statement restating the purpose is
  acceptable: "This article details the steps for creating and hosting a static
  website on AWS."
- For opinion or narrative posts, open in medias res with a concrete statement
  or anecdote: "Today, my team fired an engineer who was obviously OE."
- Cross-reference previous work when building on a prior article: "In
  a previous article, I detailed the steps for..."
- Never open with a generic "In this article, we will..." without first
  providing personal context.

### Closings

- For tutorials, use the signature "You now have..." pattern: "You now have
  your own static website hosted on AWS!"
- For opinion posts, close with a reflective or philosophical statement.
- Point readers to the relevant code repository when applicable.
- Do not use formulaic sign-offs like "Thanks for reading" or "Let me know in
  the comments."
- It is acceptable to simply end when the content is complete, without a formal
  conclusion.

### Introducing Technical Concepts

- Name the thing, then define it in one to two sentences: "Hugo is a static
  site generator. The purpose of a static site generator is to render content
  into HTML files *before* the request for the content is made..."
- Expand acronyms on first use.
- Use blockquotes for official documentation excerpts, citing the source.
- Frame complex topics around a problem the reader likely faces, followed by
  the solution.
- When explaining multiple sub-components, define each individually before
  showing how they compose together.

### Code Examples

- Always precede a code block with a short introductory sentence ending in
  a colon: "Generate RSA key pair:"
- Place the filename as inline code on its own line before the code block when
  showing file contents:
  ```
  `template.yaml`
  ```
- Use fenced code blocks with language identifiers (`bash`, `python`, `yaml`,
  `hcl`, `json`, etc.).
- Use the `$` prompt prefix for shell commands that show expected output. Use
  bare commands for commands the reader should execute.
- Follow code with a **NOTE** in bold or a bulleted breakdown when further
  explanation is needed.
- Use "has the following form:" when introducing resource or schema
  definitions.

### Lists

- Use numbered lists for sequential steps and ordered procedures.
- Use bulleted lists for non-sequential items, features, or options.
- Introduce lists with a colon at the end of the preceding sentence: "The
  following are the characteristics of security group rules:"
- Keep lists short (3-6 items). Avoid deeply nested lists.

### Formatting Conventions

- Use `**NOTE**:` callouts for supplementary information, caveats, and tips.
- Use `**WARNING**:` for critical caveats.
- Use backticks for inline code, file names, commands, resource names, and
  configuration values.
- Use bold for labels and key terms, not for general emphasis.
- Use italics for emphasis on specific words, for introducing terms, and for
  book titles.
- Use footnotes for tangential commentary, retrospective observations, humor,
  and self-corrections. Footnotes are the pressure valve for personality.

### Punctuation

- Never use em dashes. Use commas, parentheses, or rewrite the sentence.
- Never use smart quotes. Use straight quotes only.
- Use colons to introduce code blocks, lists, and explanations.
- Use parenthetical asides for brief clarifications and acronym expansions:
  "(i.e., nickolaskraus.io)".
- Use exclamation marks sparingly, only in congratulatory closings ("Done!",
  "You now have...!").
- Use ellipsis sparingly.

### Markdown Conventions

- Use reference-style links (`[text][label]` with `[label]: URL` at the bottom
  of the file). Never use inline links.
- Hard-wrap lines at approximately 80 characters.
- Use fenced code blocks, never indented code blocks.

### Transitions

- Use functional, understated transitions: "First,", "Next,", "However,",
  "Additionally,", "Furthermore,", "In addition,".
- Use "This is where..." to pivot from problem to solution.
- Use "It should be noted that..." for important qualifications.
- Use "Simply" to signal ease: "Simply pass the exception..."
- Avoid decorative or flowery transitions.

### Analogies and Allusions

- Use extended analogies to clarify complex technical concepts, developing them
  fully rather than as throwaway comparisons.
- Cultural, literary, and historical allusions are welcome when they serve the
  point.
- Keep analogies out of purely reference-style posts.

### Content-Type Adaptation

- **Tutorials**: Numbered steps, **NOTE** callouts, code-heavy, personal
  narrative framing, "You now have..." closing.
- **Reference posts**: Impersonal, structured, heavy on tables and lists,
  minimal narrative.
- **Opinion posts**: Assertive, prescriptive, blunt, with clear
  recommendations. Personal experience as evidence.
- **Reviews**: Literary register, richer vocabulary, thematic structure.
- **Curated notes**: Organized distillation of another source, minimal original
  prose, heavy code examples.

### What to Avoid

- Filler introductions, unnecessary recaps, and artificial length.
- SEO padding or motivational preambles.
- Hedging language and excessive qualifiers.
- Deeply nested lists or dense walls of text.
- Generic sign-offs or calls to action.
- Exclamation marks outside of congratulatory closings.

## meta-learning

After completing a skill, review how the run went. Only proceed if at least one
of the following occurred:

- You had to deviate from the skill's instructions to succeed.
- The instructions were ambiguous and you had to guess.
- The user corrected your approach mid-run.

If none of these occurred, skip this step entirely.

### Propose a Skill Update

1. Identify which step or instruction was insufficient.
2. Draft the minimal edit to the relevant file that would prevent the
   same issue next time.
3. Present the proposed change as a diff (old text vs. new text) and explain
   why.
4. Do not apply the edit. Wait for the user to approve or reject it.

Any files (other skills, rules files, `CLAUDE.md`, etc.) are in scope.
