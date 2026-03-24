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
