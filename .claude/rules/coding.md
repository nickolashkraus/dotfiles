# Coding

## Codebases

- **Function Health**: ~/Function-Health
- **Function Health Terraform Modules**: ~/Function-Health-Terraform-Modules
- **Infrable**: ~/infrable-io
- **Grind**: ~/grind-rip
- **Personal**: ~/nickolashkraus

## Comments

- Follow @rules/typography.md for all comments.
- Only add comments where the logic is not self-evident. The code should speak
  for itself.
- Never add decorative section dividers (e.g., `# --- Section ---`, `#
  ========`, `# *** Helpers ***`). Use whitespace and code structure to convey
  organization. Existing dividers in a file do not authorize adding more. If
  a group genuinely needs grouping, extract a sub-module, class, or function
  rather than label a region with a comment.
- Never add comments that merely restate the function or variable name (e.g.,
  `# Get the user` above `get_user()`).
- Never add trailing comments that narrate what a line does (e.g., `x
  = 1  # set x to 1`).

## Testing

- Write unit tests when appropriate. Tests should validate behavior and prevent
  regressions, particularly for business logic, edge cases, and functions with
  multiple code paths. Aim for 100% test coverage, but avoid tests for trivial
  code or framework-generated scaffolding. Use your best judgment.

## Testing Changes

For any non-trivial fix, reproduce the failure locally and verify the fix
locally before opening or updating a PR. CI passing is not the same as the
fix actually working at runtime. This applies especially to:

- Startup or lifespan bugs (run the app, watch it boot).
- Middleware-ordering bugs (run a real request through the stack).
- Async or concurrency bugs (exercise the actual code path).
- Anything where the deploy log says "container failed to start".

The procedure: run the failing code path, confirm the failure reproduces,
apply the fix, run the path again, confirm it now succeeds. Only then push.
If you cannot reproduce locally, say so explicitly in the PR body (e.g.,
"Could not reproduce locally because <reason>; please verify in <env>")
rather than presenting an unverified guess as a fix.

## Migrations

- Separate schema changes (DDL) and data changes (DML) into distinct
  migrations. DDL migrations handle structural changes (`CREATE TABLE`, `ALTER
  TABLE`, `ADD COLUMN`). DML migrations handle data operations (`INSERT`,
  `UPDATE`, `DELETE`). This allows each to land, fail, and roll back
  independently.

## Docker

- Always build Docker images that are not intended to be run locally for
  `linux/amd64` (`--platform linux/amd64`) to ensure compatibility with
  external cloud environments (AWS, Google Cloud, etc.).
