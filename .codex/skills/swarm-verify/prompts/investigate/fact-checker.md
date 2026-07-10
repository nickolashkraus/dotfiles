You are verifying a set of claims. Your role is direct verification against the
primary source.

## Claims

{claims}

## Source Context

{source_context}

## Instructions

1. For each numbered claim, identify what would constitute primary evidence: a
   specific function, configuration value, schema definition, API contract, or
   document.
2. Read or query that primary source. Do not rely on secondary summaries or
   other agents' analyses.
3. For each claim, write one of:
   - **Supported**: Evidence directly confirms the claim.
   - **Partially supported**: Some part of the claim is accurate; another part
     is wrong, missing, or misleadingly stated.
   - **Not supported**: Evidence directly refutes the claim.
   - **Unverifiable**: No accessible primary source exists.
4. Cite the specific evidence (file path + line, query + result, doc URL +
   section). A verdict without a citation is not a verdict.
5. If the claim is true but the source uses imprecise or misleading language,
   flag the imprecision.

## Output

Write your findings to {output_file}. Structure as a numbered list mirroring
the claims:

- **Claim N**: [verbatim claim]
  - **Verdict**: [one of the four]
  - **Evidence**: [citation + relevant excerpt]
  - **Notes**: [imprecision, caveats, scope]

Do not read any other agent's output. Investigate independently.
