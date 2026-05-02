# Notion Release Document Template

Page title: `<Service Name> (<date>)`

Use the following structure for every release. Omit sections marked
"if applicable" when they do not apply.

```
## Release <date> (<Service Name>)
### Preparation
- [x] Gather all PRs for release.
- [x] Create release branch from `main`.
- [x] Cherry-pick merge commits into release branch.
- [x] Create PR with `release` label.
- [x] Add `AlembicMigration` label to PR #NNNN. (if applicable)
- [x] Add `NewSecret` label to PR #NNNN. (if applicable)
- [x] CI green on PR #NNNN.
### New Secrets/Env Vars (if applicable)
<table of env vars with columns: Env Var, Dev, Prod, Used By>
<checklist of secrets set in Prod>
#### Adding Secrets to Prod
1. Request permission in ConductorOne: Select "Google (GCP + Google
   Workspace)", search "add secret", choose environment, and pick a
   short time window (security prefers 1-12 hours for Prod).
2. Create the secret in GCP Secret Manager via console or the CLI
   script in devops-utility-scripts.
### N. PR #NNNN (`release/<date>.00`): <release-title>
- [ ] CI green.
- [ ] Secrets set in Prod. (if applicable)
- [ ] Merge to `main`.
- [ ] Apply Alembic migration (`<id>`) to Production database.
      (if applicable)
- [ ] Monitor deployment and check Production logs.
### PRs Included
#### <Category>
- #NNNN BYB-NNNN: <title>.
### New Secrets/Env Vars
<table or "None.">
### Alembic Migrations
<migration ID, description, and details, or "None.">
### Rollback Plan
<steps to revert, including migration downgrade if applicable>
### Notes
<one bullet per PR explaining what it does and why>
```
