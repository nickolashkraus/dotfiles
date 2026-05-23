---
name: fh-auth
description: >
  Function Health authentication runbooks: CLI login (Auth0,
  ConductorOne), API secret-key (Fernet) token generation, Cloud Run
  proxy for internal services, and Admin App GraphQL token exchange
  (Okta -> FH JWT) for staff operations like `updatePatient`.
disable-model-invocation: false
allowed-tools: Bash, Read
---

Function Health authentication runbooks. Invoke this skill when you
need to authenticate against an FH service: CLI login, secret-key
token generation, Cloud Run internal-service access, or Admin App
GraphQL staff mutations.

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
