---
name: fh-databricks
description: >
  Function Health Databricks runbooks: workspace URLs, CLI OAuth setup,
  requesting access through ConductorOne (and when not to), the two-gate
  persona/data-reader access model, and running SQL headlessly via the
  statement execution API. TRIGGER when: user wants to query a Databricks
  catalog, verify that a table or column tag landed, check whether they
  have Databricks access, request a Databricks role, or troubleshoot
  masked/redacted query results.
disable-model-invocation: false
allowed-tools: Bash, Read
---

Function Health Databricks runbooks. Invoke this skill when you need to
reach a Databricks workspace, confirm access, or query a catalog.

Databricks is the GCP-hosted lakehouse: Unity Catalog governance over a
medallion (bronze, silver, gold) model. It is a Tier 0 service owned by
the Data Platform pillar. Support lives in #ask-data-platform.

## Workspaces

Four workspaces share one Unity Catalog metastore:

- **dev-adhoc**: Exploratory work on Dev data.
  `https://1970369403119004.4.gcp.databricks.com`
- **prod-adhoc**: Exploratory work on Prod data. Day-to-day queries,
  dashboards, and Genie spaces live here.
  `https://2216712436023510.0.gcp.databricks.com`
- **development**: Sandbox and pre-prod validation, read-only on Prod
  data.
- **production**: The only workspace that writes Prod catalogs. Access
  is restricted to admins and CI/CD service principals; engineers can
  read job status and restart jobs.

Adhoc workspaces expose gold, silver, and scratch catalogs but not
bronze. Verifying that a Fivetran bronze landing succeeded needs the
`development` or `production` workspace, or the Fivetran console.

## CLI Setup and Authentication

The CLI ships from a third-party tap, so the formula needs a one-time
trust before Homebrew will load it:

```bash
brew tap databricks/tap
brew trust --formula databricks/tap/databricks
brew install databricks
```

Authenticate per workspace with OAuth. The flow reuses the existing Okta
browser session, so it completes without an interactive prompt:

```bash
databricks auth login \
  --host https://2216712436023510.0.gcp.databricks.com --profile prod-adhoc
databricks auth login \
  --host https://1970369403119004.4.gcp.databricks.com --profile dev-adhoc
```

Databricks sits behind Okta device trust, so this only works from the
managed Mac. There is no mobile or unmanaged-device path.

## Confirming Access

The workspace is the system of record, not ConductorOne. Read the
`groups` array:

```bash
databricks current-user me -p prod-adhoc -o json
```

Group names map directly onto the ConductorOne role names
(`databricks-prod-engineers`, `databricks-dev-engineers`, and so on).

## Requesting Access (ConductorOne)

**Every engineer already holds `Prod Engineers` as a birthright grant**
via the Okta group `databricks-prod-engineers`. ConductorOne cannot see
that grant, so `cone has` reports it as ungranted and lies. Requesting
it through ConductorOne is worse than useless: an approved request
downgrades a permanent birthright to a rolling 90-day approval, which is
why such requests get denied. Confirm with `databricks current-user me`
before requesting any persona role.

Departments with automatic roles: Engineering gets Prod Engineers, Data
gets Prod and Dev Engineers, Executive/Product/Growth/PMBO get Prod
Users, Medical Intelligence Lab gets Prod MIL, Dev MIL, and Dev GPU POC.
Everything else is requested.

Two CLI gotchas when a request is genuinely needed:

- **`cone search --query databricks` finds the wrong thing**. It matches
  display names, and the workspace roles are named `Dev Engineers`, not
  `Databricks Dev Engineers`. That query returns only the 19 GCP-project
  roles for `function-health-databricks-dev`, `fh-databricks-staging`,
  and `fh-databricks-prod`, which grant GCP console and Cloud Build
  access, not workspace access. Use `cone search --app "Databricks"`
  (appId `38zIiglO39BasC4DxDPwPLVVaLr`, 27 roles), or
  `cone search --not-granted --app "Databricks"`.
- **`cone get` requires `--duration`** for these. Omitting it fails with
  a max-provision-time error rather than defaulting. The ceiling is
  `12w6d`.

```bash
cone get --app-id 38zIiglO39BasC4DxDPwPLVVaLr \
  --entitlement-id <id> --duration 6w --justification "<why>" -i
```

Approvers are Amit Gaur, Zack Shapiro, and Siva Pandeti. Most grants
expire after 90 days. Full runbook: Notion "Requesting Databricks
Access" (`234b0b10ae8c80fd9da1d6f9e3aa36f0`).

## Access Is Two Independent Gates

A persona role (Consumers, Users, Engineers, MIL, Data Platform
Engineers) gets you into a workspace. A data reader role unmasks
columns. Holding the first without the second means queries run and
return masked values.

Masking is silent for non-text columns. Text comes back as
`redacted <sensitivity> <category>`, but numbers come back as `0`, dates
as `1970-01-01`, and booleans as `false`, with no error and no warning.
An implausible column of zeros is a masking symptom before it is a data
symptom.

The six reader roles pair a sensitivity (`internal`, `restricted`) with
a category (`pii`, `health`, `financial`). Restricted subsumes internal,
so never request both tiers of one category. One reader grant covers
both Dev and Prod.

Verifying that a column tag exists does not need a reader role, since
tags are metadata rather than values.

## Running Queries

There is no `databricks sql` subcommand. Use the statement execution
API with a warehouse ID (`prod-default-warehouse` is
`5d3741e4acd5ca7e`, `dev-default-warehouse` is `ce0d0f754eb27942`):

```bash
cat > /tmp/q.json <<'JSON'
{
  "warehouse_id": "5d3741e4acd5ca7e",
  "statement": "SELECT current_user()",
  "wait_timeout": "30s"
}
JSON
databricks api post /api/2.0/sql/statements -p prod-adhoc --json @/tmp/q.json
```

**A catalog's own `information_schema` is unqueryable.** Selecting from
`prod_silver.information_schema.<anything>` fails outright with
`COLUMN_MASKS_FEATURE_NOT_SUPPORTED.VIEWS`, because column-mask policies
cannot apply to views. This breaks the `column_tags` lookup that the
Notion runbook recommends verbatim.

Query the metastore-wide `system.information_schema` instead. It carries
no masks and covers every catalog:

```sql
SELECT schema_name, table_name, column_name, tag_name, tag_value
FROM system.information_schema.column_tags
WHERE catalog_name = 'prod_silver'
  AND table_name = '<table>'
```

Tag rows come back one per `tag_name`, with `category` (`pii`, `health`,
`financial`, `none`) and `sensitivity` (`internal`, `restricted`) as the
two that drive masking. Reading tags needs no data reader role.

To enumerate objects, prefer the Unity Catalog REST API over SQL:

```bash
databricks catalogs list -p prod-adhoc
databricks schemas list prod_silver -p prod-adhoc
databricks tables list prod_silver <schema> -p prod-adhoc
```

`databricks tables get <full_name>` returns column names and types but
**not** tags, so it is not a substitute for the `column_tags` query.
