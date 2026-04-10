# Git

## General

- Follow @rules/typography.md for all Git content (PR descriptions, commit
  messages).
- Never add a co-authored-by or signature to commits
  (e.g., `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`).
- Branch names should be the Linear issue slug (e.g., `BYB-1337`) if
  available, or a short description (e.g., `some-feature`).
- Pull request titles should include the Linear issue (if provided) (e.g.,
  `EPD-1337: ...`).
- If a change has interesting or nuanced information, add it to the Git commit
  and PR description.

## Worktrees

- Always create worktrees in the root of the bare repo as peer directories
  (e.g., `transaction-service/BYB-934` alongside `transaction-service/dev`).
  Never place them under subdirectories like `.claude/worktrees/`.

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

### Squashing Commits

A pull request should contain a single commit unless each commit represents
a logical grouping of changes. If you commit often during development, squash
before merging.

### Pushing

Always run CI (tests, linting) locally before pushing. Do not push code that
you have not verified passes the project's CI.

After pushing, run `/fix-ci` until all checks pass. Do not consider the job
done while any check is non-passing (including neutral or pending).

### Rebasing

Do not merge master into a branch to integrate upstream changes. Use `git
rebase` instead.

## Pull Requests

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

### Descriptions

Scale the description with the complexity of the change.

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

```
Fixes the following error:
\`\`\`
error: "GcpStorageConfig" is not a known attribute of module "gcp_storage_sdk"
\`\`\`

Basically just makes the module's public API more clear and fixes the pyright error.
```

#### Larger Changes

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
