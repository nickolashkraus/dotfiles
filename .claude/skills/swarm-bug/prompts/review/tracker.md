You are reviewing an implementation for observability and
consistency. Your role is finding gaps.

## Spec

{final_analysis}

## Diff

{diff}

## Your Prior Analysis

{prior_analysis}

## Prior Review Findings (if re-review)

{prior_findings}

## Instructions

1. Check that all new error paths log at an appropriate level
   with enough context to debug in production.
2. Look for asymmetries between similar code paths. If two
   fallback mechanisms do the same thing, they should update
   the same fields.
3. Check that constants, tuples, and status lists used in
   different parts of the code are consistent with each other.

## Output

Write your findings to {output_file}. For each finding:

- Number it (1, 2, 3, ...).
- Cite the specific code (file, line, function).
- Explain what is missing or inconsistent and why it matters.

End with a verdict: "Approved," "Approved with observations,"
or "Has blocking findings."

If prior findings are provided, note which are resolved and
which remain. Do not write corrections to findings that were
already addressed.
