You are reviewing the Orchestrator's synthesis of all agent
findings for a production bug.

## Your Original Analysis

Read your findings from: {own_findings_path}

## Synthesis

Read the synthesis from: {synthesis_path}

## Instructions

1. Read your own findings file first, then the synthesis.
2. Verify that your findings are accurately represented in
   the synthesis. Flag any mischaracterization.
3. Check that the failure modes are correctly separated. Two
   distinct mechanisms should not be merged into one.
4. Check that the dependency ordering between fix layers is
   correct. If Layer A depends on Layer B, verify the
   rationale.
5. Identify any factual claims you can verify or refute from
   your investigation.
6. Check that the fix layers actually address the failure
   modes they claim to address.

## Output

Write to {output_file}. Structure:

- **Accuracy**: Are your findings correctly represented?
- **Corrections**: Anything the synthesis got wrong.
- **Missing**: Anything the synthesis omitted.
- **Dependency ordering**: Is the layer ordering correct?
- **Verdict**: "Approved" or "Has concerns" with specific
  objections.
