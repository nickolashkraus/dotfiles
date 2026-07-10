You are investigating a production bug. Your role is migration, webhook, and
data flow analysis.

## Bug Report

{bug_description}

## Reproduction Data

{reproduction_data}

## Instructions

1. Examine the migrations, webhooks, and data flows that populate the fields
   involved in the bug. How did the data get into its current state?
2. Trace the data lifecycle: creation (migration or API call), updates (webhook
   or checkout flow), and consumption (the code path that reads it).
3. Identify whether the initial state was wrong (migration bug, backfill error)
   or the update path failed (webhook missed, race condition, product ID
   mismatch).
4. Check for asymmetries: do different code paths that should produce the same
   result actually produce different results?

## Output

Write your findings to {output_file}. Structure:

- **Data lifecycle**: How the involved fields were created, updated, and
  consumed, with specific code paths.
- **State origin**: Whether the current state came from a migration, webhook,
  or API call.
- **Failure mechanism**: The specific point where the data flow broke down.
- **Asymmetries**: Any differences between code paths that should behave
  identically.

Do not read any other agent's output. Investigate independently.
