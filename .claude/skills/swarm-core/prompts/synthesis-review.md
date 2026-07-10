You are reviewing the Orchestrator's synthesis of all agent findings.

## Your Original Analysis

Read your findings from: {own_findings_path}

## Synthesis

Read the synthesis from: {synthesis_path}

## Instructions

1. Read your own findings file first, then the synthesis.
2. Verify that your findings are accurately represented in the synthesis. Flag
   any mischaracterization.
3. Check that distinct findings are correctly separated. Two distinct
   mechanisms or considerations should not be merged into one.
4. If the synthesis proposes ordered steps, layers, or dependencies, verify the
   ordering is correct and the rationale holds.
5. Identify any factual claims you can verify or refute from your
   investigation.
6. Check that proposed actions actually address the findings they claim to
   address.

## Output

Write to {output_file}. Structure:

- **Accuracy**: Are your findings correctly represented?
- **Corrections**: Anything the synthesis got wrong.
- **Missing**: Anything the synthesis omitted.
- **Ordering**: If the synthesis proposes ordered steps, is the ordering
  correct?
- **Verdict**: "Approved" or "Has concerns" with specific objections.
