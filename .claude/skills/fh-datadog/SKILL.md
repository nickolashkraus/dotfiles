---
name: fh-datadog
description: Function Health Datadog runbooks. Covers API authentication (org API key from GCP Secret Manager, user Application key from the Keychain, `us5` site) and local monitor-query validation via the `/monitor/validate` endpoint. TRIGGER when the user wants to validate a Datadog monitor query locally, hit the Datadog API for FH, or troubleshoot Datadog auth or a "does not match" monitor error.
disable-model-invocation: false
allowed-tools: Bash, Read
---

Function Health Datadog runbooks. Invoke this skill when you need to call
the Datadog API for FH or validate a monitor query locally before a CI push.

## Authentication

Datadog's API needs two credentials, and they live in different stores (see
@~/.claude/rules/secrets.md):

- **`DD-API-KEY`**: Org-level API key. A Function Health secret in GCP Secret
  Manager (`DATADOG_API_KEY` in `function-health-dev-env`).
- **`DD-APPLICATION-KEY`**: User-scoped Application key, scoped to monitors.
  Lives in the macOS Keychain as `datadog-app`.

The org is on the `us5` site, so the API base is `api.us5.datadoghq.com`.

## Validating a Monitor Query

Validate a monitor query locally, without a CI push:

```bash
curl -sS -X POST https://api.us5.datadoghq.com/api/v1/monitor/validate \
  -H "DD-API-KEY: $(gcloud secrets versions access latest --secret=DATADOG_API_KEY --project=function-health-dev-env)" \
  -H "DD-APPLICATION-KEY: $(security find-generic-password -s datadog-app -a function-health -w)" \
  -H "Content-Type: application/json" \
  -d '{"name":"t","type":"query alert","query":"<query>","message":"m","options":{"thresholds":{"critical":30,"warning":15}}}'
```

An empty `{}` response means the query is valid. The `critical` value in
`options.thresholds` must match the threshold in the query, or Datadog returns
a misleading "does not match" error that is not a grammar problem.
