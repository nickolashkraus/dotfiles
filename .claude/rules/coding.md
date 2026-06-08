# Coding

## Codebases

- **Function Health**: ~/Function-Health
- **Function Health Terraform Modules**: ~/Function-Health-Terraform-Modules
- **Infrable**: ~/infrable-io
- **Grind**: ~/grind-rip
- **Personal**: ~/nickolashkraus

## Clarifying Before Implementing

For non-trivial implementation directives (schema changes, contracts,
migrations, multi-file refactors, anything that shapes a PR description or
a Linear ticket), do not start writing code immediately. First write back
a tight plan that surfaces:

- The branch, base, and scope of the work.
- Every load-bearing assumption (schema fields, ordering, predicates,
  contracts).
- The one or two clarifying questions whose answers unblock the work.

Push back when the proposed approach doesn't fit invariants you can see, or
when a simpler approach exists that I may not have considered. Diving straight
in ships working but structurally wrong code; surfacing assumptions lets me
redirect before the wrong shape is locked into commit history or PR review.

Trivial tasks (single-file fix, obvious rename, mechanical refactor) do not
need this gate. Do not interpret a prior "go" as covering every downstream
micro-decision; restate the next load-bearing assumption when one surfaces.
The complementary rule is to not ask multiple-choice questions on low-stakes
choices you should just make and surface.

## Production-Scale by Default

Write every change under the assumption that it will run against production
data and production traffic. CI green is necessary but not sufficient. Test
environments with empty or near-empty tables hide O(n) and lock-contention bugs
that are catastrophic at scale.

Before merging any change that touches a table, query, or background job,
answer these questions explicitly:

- How many rows does this run against in Prod? Not in CI fixtures, not in Dev,
  not in Staging.
- What locks does it take, at what level, for how long?
- What queues behind it? Lock queue, connection pool, downstream service,
  Pub/Sub subscriber backlog.
- What is the failure mode under retry, timeout, partial completion, or
  concurrent execution with another release?

A function whose test fixture has 5 rows tells you nothing about its behavior
at 5M rows. When CI alone cannot answer the questions above, measure against
the Prod data shape before merging. The minimum bar is the row count from the
read replica, a query plan from `EXPLAIN (ANALYZE, BUFFERS)`, a runtime
estimate, and the Postgres lock-mode catalog from the docs. "It passed tests"
is not a release signal for any change that scales with table size,
concurrency, or queue depth.

This bar applies broadly:

- Migrations and backfills (see the dedicated section).
- Bulk operations such as exports, reports, scheduled jobs, and cron-driven
  reconcilers.
- New queries that risk missing indexes, accidental sequential scans, or N+1
  patterns inside loops.
- New endpoints whose response size, pagination, downstream fanout, or fan-in
  joins are unbounded.
- New background workers and Pub/Sub subscribers, where idempotency, retry
  semantics, queue backpressure, and dead-letter behavior all matter.

When a behavior degrades non-linearly with row count, concurrency, or queue
depth, the safe assumption is that Prod will exercise the failure mode and CI
will not catch it. Surface the assumption in the PR body and, when feasible,
measure it.

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

See @rules/migrations.md.

## Docker

- Always build Docker images that are not intended to be run locally for
  `linux/amd64` (`--platform linux/amd64`) to ensure compatibility with
  external cloud environments (AWS, Google Cloud, etc.).
