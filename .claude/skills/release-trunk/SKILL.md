---
name: release-trunk
description: >
  Cut a trunk-based release for a Function Health service whose Prod deploy
  trigger fires on a `release/YYYY-MM-DD.NN` tag push. Determines the deployed
  Prod version, picks the release commit, pushes the tag, creates the GitHub
  Release, and monitors the deploy to completion. TRIGGER when: user says
  "trunk release", "tag release", "push a release tag", or the repo's Prod
  Cloud Build trigger is tag-based. SKIP: repos still on the dev-branch
  cherry-pick model (use `release`).
disable-model-invocation: false
allowed-tools: Bash, Read, Edit, Write, Glob, Grep, Agent, Monitor, mcp__claude_ai_Slack__slack_send_message_draft
argument-hint: "[--date YYYY-MM-DD] [--commit SHA] [--no-op] [--cc USER_IDS_OR_HANDLES]"
---

You are cutting a trunk-based release for a Function Health service. The
Prod deploy is triggered by pushing a Git tag matching
`release/YYYY-MM-DD.NN`; there is no release branch, release PR, or
cherry-picking. Follow every step in order.

All release content must follow `@~/.claude/rules/typography.md` and
`@~/.claude/rules/git.md`.

## Step 1: Determine service, repo, and trigger

Detect the service from the current working directory. Determine
`{owner}/{repo}`:

```
gh repo view --json nameWithOwner --jq '.nameWithOwner'
```

Confirm the Prod deploy trigger and its tag regex. Do not assume the tag
shape; some repos namespace tags (e.g., `release/<service>/YYYY-MM-DD.NN`):

```
gcloud builds triggers describe <service>-deploy-prod \
  --project function-health-prod-env --format=json
```

Verify it fires on `github.push.tag` and note `_MIGRATION_ENABLED`. Save the
trigger `id` for build lookups later. If the trigger is branch-based, stop:
this repo is not on the trunk-based flow (use the `release` skill).

## Step 2: Determine the deployed Prod version

Find the Cloud Run service and its image:

```
gcloud run services list --project function-health-prod-env \
  --format='value(metadata.name)' | grep <service>
gcloud run services describe <prod-service-name> \
  --project function-health-prod-env --region us-central1 \
  --format='value(spec.template.spec.containers[0].image, status.latestReadyRevisionName)'
```

The image tag is `tf_<short-sha>`. Map it to a commit:

**EasyDeploy-managed services** (e.g. ppp-service) serve an
EasyDeploy-owned image digest instead of `tf_<short-sha>`, so this
mapping does not work. Determine the deployed version from the newest
`release/*` tag whose prod deploy build succeeded
(`gcloud builds list` filtered by the trigger ID). Also check the
trigger's `_MIGRATION_ENABLED` substitution: repos that moved
migrations to the DevHub Migrations action pin it `false`, and the
release then only builds the image and applies Terraform.

```
git log -1 --format='%h %ad %s' --date=short <short-sha>
```

## Step 3: Pick the release commit

Show the undeployed delta and flag migrations:

```
git log --oneline <deployed-sha>..origin/main
git diff --stat <deployed-sha>..origin/main -- alembic/versions/
```

- **Normal release**: Tag the tip of `origin/main`. Everything in the delta
  ships; there is no per-PR selection in trunk-based deploys. If the delta
  contains commits that must not ship, stop and surface it.
- **No-op release** (`--no-op`): Tag the currently-deployed commit itself.
  The build, Terraform apply, and migrations job all run, but the image
  reference (`tf_<short-sha>`) is unchanged, so Cloud Run rolls no new
  revision and `alembic upgrade head` has nothing to apply.

Review any migrations in the delta against `@~/.claude/rules/migrations.md`
(runtime against Prod row counts, lock behavior, chunking) before tagging.

## Step 4: Pre-tag checklist

Present a short plan and get explicit confirmation before pushing the tag.
Pushing the tag IS the Prod deploy.

- Release commit and what ships (or "no-op").
- Migrations in the delta and their assessed risk.
- New secrets or env vars in the delta (`os.environ`/`os.getenv` not on the
  deployed SHA); confirm they are set in Prod Secret Manager first.
- CI green on `main` at the release commit.

Determine the tag name: today's date plus the next free two-digit `.NN` for
this repo (check `git ls-remote --tags origin 'release/*'`). Numbering is
per-repo, starting at `.01`.

## Step 5: Tag and release

Create and push the tag, then create the GitHub Release on it:

```
git tag release/<date>.<NN> <release-sha>
git push origin release/<date>.<NN>
gh release create release/<date>.<NN> \
  --title "Release <date>.<NN>" --verify-tag --notes <notes>
```

Release notes: one line per PR in the delta, `<subject> (#NNN)`, matching
the ppp-service convention. For a no-op release use: "No-op release to
exercise the trunk-based release flow. The tag points at the
currently-deployed commit (<short-sha>), so no code, migration, or secret
changes ship."

A bare tag push never creates a GitHub Release; `gh release create` is a
required step, not an optional nicety.

## Step 6: Monitor the deploy

Find the build (poll briefly; it appears within a minute):

```
gcloud builds list --project function-health-prod-env \
  --filter='buildTriggerId="<trigger-id>"' --limit 1 \
  --format='value(id, status, substitutions.TAG_NAME)'
```

Then watch it to a terminal state with a background Bash loop (statuses:
`SUCCESS`, `FAILURE`, `TIMEOUT`, `CANCELLED`, `EXPIRED`). Note that
`gcloud builds list` without `--limit` can hang; always pass `--limit`.

On `SUCCESS`, verify:

1. **Cloud Run revision**: `status.latestReadyRevisionName` advanced and
   serves 100% of traffic. For a no-op release, verify it did NOT change.
2. **Migrations job**: The last execution of
   `prod-<service>-db-migrations` succeeded:

   ```
   gcloud run jobs executions list --job prod-<service>-db-migrations \
     --project function-health-prod-env --region us-central1 --limit 1
   ```

3. **Runtime health**: Tail Prod logs for errors for a few minutes
   (Datadog or `gcloud run services logs read`). Watch error rate and
   5xx on the service's Datadog monitors.

On `FAILURE`, read the build log, diagnose, and surface. Prod keeps running
the previous revision; a failed build does not need a rollback.

## Step 7: Rollback plan

To roll back a bad release: tag the last known-good commit as the next
`.NN` and push it. Never delete or re-point a pushed release tag. If a
migration shipped, assess whether the previous code tolerates the new
schema before rolling back code alone.

## Step 8: Summarize

Print: tag, GitHub Release URL, Cloud Build ID and status, Cloud Run
revision before/after, migrations applied (or none), and any follow-ups.
Update the daily task file in
`~/nickolashkraus/agent-os/tasks/daily/<YYYY>/<MM>/<date>.md` if one exists
for this release.
