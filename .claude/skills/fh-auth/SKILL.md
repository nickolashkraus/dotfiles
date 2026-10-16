---
name: fh-auth
description: >
  Function Health authentication runbooks: CLI login (Auth0, ConductorOne), API
  secret-key (Fernet) token generation, Cloud Run proxy for internal services,
  Admin App GraphQL token exchange (Okta -> FH JWT) for staff operations
  like `updatePatient`, and the member app Firebase ID token for
  member-facing MAM calls. TRIGGER when: user mentions FH auth failure,
  Auth0/ConductorOne login, Okta -> FH JWT exchange, GraphQL 401, a member
  app or MAM 401, needing a Firebase ID token for a member, Cloud Run
  proxy for an internal FH service, or needs a Fernet API key.
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

## Member App Firebase ID Token

`member-app-middleware` authenticates members with a Firebase ID token in the
`Authorization` header (`tokens.validate_token` resolves it through
`FirebaseUserIDDep`). Nothing mints one from a service identity: it is a member
credential, so it comes from a member sign-in.

MAM's own login route is the headless path. It proxies to Firebase
`signInWithPassword` and returns the token.

The response carries `idToken`, `refreshToken` and `expiresIn`
(`FirebaseLoginSuccessResponseModel`). Three details that cost a retry
otherwise:

- **`POST /api/v1/login`** is the email and password route
  (`user_email_password_login`, taking `FirebaseLoginCredentialsModel`).
- **`/api/v1/login/credentials` is not it.** That route takes
  `signed_challenge` and `challenge` (`CredentialsLoginModel`), the device
  credential flow, and answers a `KeyError: 'idToken'` shaped failure when
  posted an email and password. Reading
  `_authenticate_user_with_email_password` and assuming the nearest route in
  the file owns it is how that mistake gets made; check the
  `add_api_route` binding.
- **`fe-app-version`**: Marks the caller a web client. Without it,
  `raise_if_mobile_version_blocked` can answer 426 whenever Statsig has a
  minimum mobile version configured.

`POST /api/v1/login/mcp` takes the same body and additionally returns
`patientId`, which is worth using when the point is to confirm the token maps
to the member you expect.

**Nickolas signs in himself, in a separate terminal.** The password is
a member credential on a deployed service, so an agent never handles it. Never
run this through the `!` prefix, which adds the command and its output to the
conversation. The password is read without echo, sent on stdin rather than
the command line, and the token goes straight into the Keychain unprinted:

```bash
read -r -p 'Email: ' email && read -rs -p 'Password: ' password && echo
token=$(jq -n --arg e "${email}" --arg p "${password}" \
    '{email: $e, password: $p}' \
  | curl -s -X POST \
      https://development-member-app-mid-2jv3ndpkoa-ue.a.run.app/api/v1/login \
      -H 'content-type: application/json' -H 'fe-app-version: qa' -d @- \
  | jq -r .idToken)
security add-generic-password -s fh-dev-member-token -a function-health \
  -w "${token}" -j "Dev member app Firebase ID token" -U
unset password token
```

The agent then reads it at point of use:

```bash
curl -s -H "Authorization: $(security find-generic-password \
  -s fh-dev-member-token -a function-health -w)" \
  https://development-member-app-mid-2jv3ndpkoa-ue.a.run.app/api/v1/pending-schedules
```

An ID token lasts about an hour. `POST /api/v1/token/refresh` mints a new one
from the `refreshToken`, so a long run does not need a second sign-in.

Browser alternative: sign into the Dev member app, then DevTools, Network, any
MAM request, and copy the `Authorization` header.

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
