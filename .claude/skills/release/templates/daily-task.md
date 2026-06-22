# Daily Task File Template

Path: `~/nickolashkraus/agent-os/tasks/daily/<YYYY>/<MM>/<date>.md`

```
# <date>

## Release <date> (<Service Name>)

### Preparation

- [x] Gather all PRs for release.
- [x] Create release branch from `main`.
- [x] Cherry-pick merge commits into release branch.
- [x] Create PR with `release` label.
- [x] Add `AlembicMigration` label to PR #NNNN. (if applicable)
- [x] Add `NewSecret` label to PR #NNNN. (if applicable)
- [ ] CI green on PR #NNNN.

### [PR #NNNN][pr-NNNN] (`release/<date>.00`): <release-title>

- [ ] CI green.
- [ ] Secrets set in Prod. (if applicable)
- [ ] Merge to `main`.
- [ ] Apply Alembic migration (`<id>`) to Production database.
      (if applicable)
- [ ] Monitor deployment and check Production logs.

### Notion Release Document

- [ ] Create release document in Notion.

### Announcement

- [ ] Post release announcement in `#deployments-planning`.

[pr-NNNN]: https://github.com/<owner>/<repo>/pull/NNNN
```
