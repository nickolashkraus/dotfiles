You investigated this independently. Other agents have now completed their own
investigations. Your role is to identify anything their findings change about
yours.

## Your Findings

Read your findings from: {own_findings_path}

## Other Agents' Findings

Read the other agents' findings from these files: {other_findings_paths}

## Instructions

1. Read your own findings file first, then all other agents' findings files.
2. Identify anything that changes, contradicts, or supplements your original
   analysis.
3. If another agent found something you missed, add it with attribution.
4. If another agent's finding contradicts yours, explain the discrepancy and
   which interpretation you believe is correct.
5. If you have nothing to add, write "No additional findings."

## Output

Append to {output_file} under a `## Convergence` section:

- **New findings**: Anything you missed.
- **Corrections**: Anything you got wrong.
- **Confirmations**: Findings from other agents that you can independently
  verify.
- **Verdict**: "Complete" (nothing to add) or "Has additions" (new findings
  added).
