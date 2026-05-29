# Git

## General

- Follow @rules/typography.md for all Git content (PR descriptions, commit
  messages).
- Never add a co-authored-by or signature to commits
  (e.g., `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`).
- Branch names should be the Linear issue slug (e.g., `BYB-1337`) if available,
  or a short description (e.g., `some-feature`). Always use the uppercase slug
  verbatim from Linear. Do not lowercase it (`byb-1337` is wrong). The same
  applies to worktree directory names, which mirror the branch.
- Pull request titles should include the Linear issue (if provided) (e.g.,
  `EPD-1337: ...`).
- Always render Linear issue references as Markdown links (e.g.,
  `[EPD-1337](https://linear.app/functionhealth/issue/EPD-1337)`) in PR
  descriptions, not bare slugs like `EPD-1337` or bare URLs. This applies to
  every reference, not just the primary one. Scope: Rendered Markdown surfaces
  where the link resolves (PR descriptions and review comments). Do NOT render
  link syntax in chat replies to the user, commit messages, branch names,
  source code, or any other plain-text context. In those contexts a bare slug
  (BYB-1216) is correct, since reference-style syntax with no definition block
  renders as literal brackets.
- Keep `## References` blocks short. Include only the references a reviewer
  needs to understand or audit the change. That usually means the primary
  Linear issue, the umbrella or parent if the work is part of a larger
  initiative, the direct predecessor PRs whose contracts this change depends
  on, and any spec or design doc that is load-bearing. Do not pad the list with
  every adjacent ticket, every sibling phase, or every issue mentioned in
  passing. A long reference list dilutes the important links and signals that
  the body did not do the work of identifying what actually matters. The bar
  for inclusion is "the reviewer cannot understand the change without this".
  Five entries is typical; ten is almost always too many. If a link is useful
  as context-while-reading but not as a standing reference, inline it in the
  prose instead.
- When a Linear reference is followed by a colon and a description (e.g., in
  a `## References` list in a PR description), use the verbatim Linear issue
  title, not a paraphrase or abbreviation. Paraphrases ("Typed status reducer",
  "Resolver and stripe_price_id") drift from the issue and force the reader to
  open Linear to confirm the mapping. When two issues share a relationship
  annotation, split them onto separate lines rather than grouping under one
  paraphrase, since each has a distinct verbatim title.
- Only add Linear issue references to source code (comments, docstrings, test
  names, regression guards) when absolutely necessary. The code needs to be
  evergreen and stand on its own; once a PR merges, the Linear context goes
  stale while the code persists. Branch names, PR titles, PR descriptions, and
  commit messages remain the right places for Linear refs. If a comment needs
  a Linear link to make sense, the comment is probably restating context that
  belongs in the PR description, not in the source. The bar for inclusion is "a
  future reader cannot reconstruct the rationale from the code, and the ticket
  is the only durable record".
- If a change has interesting or nuanced information, add it to the Git commit
  and PR description.
- Single-quoted heredocs (`<<'EOF'`) preserve backticks, `$`, and `\` literally.
  Never escape these characters defensively inside the body. Escaped backticks
  render as literal `` \` `` in the output and escaped `$` as `\$`. Only escape
  inside an unquoted heredoc (`<<EOF`), where shell expansion is active.
- Always use the GitHub username (e.g., `nickolashkraus`) for `TODO` owner tags
  in source code, in every repo. Do not use an email address, a short first
  name, or any other handle. The format is:
  ```
  # TODO(<github-username>): <description>
  ```
  Add a `See: <linear-issue-url>` follow-up line only when the TODO depends on
  external work that the description cannot summarize inline.

## Worktrees

- Always create worktrees in the root of the bare repo as peer directories
  (e.g., `transaction-service/BYB-934` alongside `transaction-service/dev`).
  Never place them under subdirectories like `.claude/worktrees/`.
- In a bare repo with worktrees, default to the `master` (or default) branch
  worktree for operations like `git log`, `git diff`, and rebasing. Do not
  operate from the bare repo root.

## Commits

### Commit Messages

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
- When the branch maps to a Linear issue, the subject is `SLUG: Exact Issue
  Title` (e.g., `BYB-1345: Membership Upgrade Creates Duplicate Active
  Subscriptions in Stripe`). Use the verbatim Linear issue title, not
  a paraphrase.
- When there is no Linear issue, use a clean imperative subject. Never
  fabricate a placeholder slug like `BYB-NOBUG:`, `NOBUG:`, `NOBUG-1:`, or
  `EPD-NONE:`. The `NOBUG` convention is for in-source TODO tags only, never
  commit subjects.

### Squashing Commits

A pull request should contain a single commit unless each commit represents
a logical grouping of changes. If you commit often during development, squash
before merging.

### Pushing

Always run CI (tests, linting) locally before pushing. Do not push code that
you have not verified passes the project's CI.

Run the **full** repo lint and test suite, not file-scoped invocations. For
Python repos that means `ruff format --check .` and `ruff check .` across the
whole repo, plus the full pytest suite (e.g., `poetry run python -m pytest
--no-cov`), and `poetry run pyright` where it applies. Narrow invocations like
`ruff format <changed_files>` miss reformat-needed files that the editor never
surfaced, and the CI lint baseline may still flag them. If the local
environment is broken (missing DB password, services down), fix it before
pushing rather than skipping verification.

After pushing, run `/fix-ci` until all checks pass. Do not consider the job
done while any check is non-passing (including neutral or pending).

### Retriggering CI

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

### Rebasing

Do not merge master into a branch to integrate upstream changes. Use `git
rebase` instead.

### Release Branches

Release branches (`release/*`) accept only pure cherry-picked merge or squash
commits from the default branch. Never push a manually-edited, hand-crafted,
or in-place fix commit to a release branch or release PR, even if a bot leaves
a review on the release PR. The merge-commit-only invariant is what makes the
release line auditable back to a merged dev PR.

When a bot or human leaves a review on a release PR, two valid responses:

1. The finding is stale (commit force-pushed away or no longer on the release
   tip): reply inline explaining and move on.
2. The finding is real on the release tip: do not fix it on the release
   branch. Either reply inline noting that the finding is being carried into
   the follow-up release/remediation PR, or fix it on the default branch via
   a normal PR, get it merged, and cherry-pick that merge commit onto the
   release branch.

"Address this review inline" while you are on a release PR means "reply
inline," not "fix in code and push." Confirm before any code edit.

## Stacked PRs

For dependent changes, stack PRs by targeting each PR against its parent branch
(e.g., `BYB-1053` targets `BYB-891`, `BYB-1054` targets `BYB-1053`). This keeps
each review focused on only the relevant delta. When a parent branch merges
and is deleted, GitHub automatically retargets the child PR to the default
branch.

## Pull Requests

### Merging

Never merge a pull request unless the user has explicitly said to merge it.
"Deploy to X", "ship it", or "land it" do not count as merge approval, even
when the PR targets a deployment branch and merging would trigger the deploy.
Ask first. Merging is hard to reverse, fires deploy webhooks, and collapses the
commit history; do not infer it from adjacent instructions.

Before merging any PR, including an intra-stack one that does not need human
review, check for open bot reviews and bot review comments. Run:

```
gh pr view <pr-number> --json reviews,comments
```

If any bot (CodeRabbit, Cursor Bugbot, Cursor Security Review, Seer Code
Review, sre-terraform-review-bot, etc.) has posted a review with state
`CHANGES_REQUESTED` or has left unresolved review comments with actionable
suggestions, do not merge. Address the comment or file a follow-up and note
inline why it is being deferred. CI rollup being green is not a substitute.
The "no-human-review-intra-stack" rule applies only to human reviewers; bot
reviews still gate the merge.

### General Rules

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
- Never add `Closes: <Linear issue>` (or `Fixes:`, `Resolves:`) to a PR
  description. The Linear issue is already linked elsewhere in the body, and
  GitHub does not auto-close Linear issues from these keywords. The line is
  redundant noise.

### Descriptions

Scale the description with the complexity of the change.

For any non-trivial PR body, write the Markdown to a temp file (e.g.,
`/tmp/pr-<N>-body.md`) and pass it via `gh pr create --body-file` or
`gh pr edit <N> --body-file`. Do not inline the body via
`--body "$(cat <<'EOF' ... EOF)"`. Defensive escapes inside an inline heredoc
have a way of leaking through as literal `` \` `` and `\$` in the rendered
description. The same rule applies to `gh issue create` and `gh pr comment`
for any body longer than a single short line.

#### Trivial Changes

Use a single declarative sentence or leave the body empty.

```
Service should not be publicly available.
```

```
Determines document upload status from Google Cloud Storage.
```

#### Small to Medium Changes

Open with a brief declarative summary (no header needed). Include code
snippets, error messages, or links to related code when they add clarity.

Use `**NOTE**` or `**NOTE**:` for important asides or to call out secondary
decisions (e.g., refactoring done alongside the main change).

````
Fixes the following error:
```
error: "GcpStorageConfig" is not a known attribute of module "gcp_storage_sdk"
```

Basically just makes the module's public API more clear and fixes the pyright error.
````

#### Larger Changes

Use `## Overview` as the primary header with a concise summary. Add additional
sections as needed:

- `## Implementation Details` for how it works, with commands or code examples.
- `## References` for links to documentation, related issues, or specs.

Do not add a `## Testing`, `## Tests`, or `## Test plan` section. Tests are
visible in the diff and CI; restating them in prose adds noise without adding
context the reviewer can't already see.

````
## Overview

Adds authentication to the MCP server using Auth0.

## Implementation Details

This adds authentication to the MCP server for protected MCP tool calls.

Run the MCP server:

```bash
poetry run uvicorn ai_chat.apps_sdk.server.main:app --host 0.0.0.0 --port 8000
```
````
