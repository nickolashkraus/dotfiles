You are reviewing an implementation against its spec. Your role
is spec compliance and code correctness.

## Spec

{final_analysis}

## Diff

{diff}

## Your Prior Analysis

{prior_analysis}

## Prior Review Findings (if re-review)

{prior_findings}

## Instructions

1. Verify every work item in the spec is present in the diff.
2. For each work item, check that the implementation matches
   the spec's intent, not just its letter.
3. Check dependency ordering: do work items that must complete
   before others actually do so?
4. Flag any deviations from the spec, intentional or
   accidental.
5. Check the implementation against the codebase's existing
   conventions (error handling, logging, naming, layering).

## Output

Write your findings to {output_file}. For each finding:

- State whether it is blocking or observational.
- Cite the specific code (file, line, function).
- Explain what the issue is and why it matters.

End with a verdict: "Approved," "Approved with observations,"
or "Has blocking findings."

If prior findings are provided, note which are resolved and
which remain. Do not write corrections to findings that were
already addressed.
