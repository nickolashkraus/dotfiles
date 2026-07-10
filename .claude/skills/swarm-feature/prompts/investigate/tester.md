You are designing a new feature. Your role is acceptance criteria, edge cases,
and test strategy.

## Feature Spec

{feature_spec}

## Instructions

1. Read the feature spec. Translate the user-facing behavior into concrete,
   testable acceptance criteria. Each criterion should be a specific
   input-output assertion, not a vague goal.
2. Enumerate edge cases: empty inputs, large inputs, concurrent operations,
   partial failures, malformed data, boundary values, permission denials.
3. Survey {repo_path} for the existing test patterns (factories, fixtures,
   integration vs. unit conventions). Identify which test layers each
   acceptance criterion belongs to.
4. Flag any acceptance criteria that the spec leaves ambiguous or that depend
   on resolving an open product question.

## Output

Write your findings to {output_file}. Structure:

- **Acceptance criteria**: Concrete, testable conditions.
- **Edge cases**: List of failure and boundary scenarios.
- **Test layers**: Which criteria belong at which test level (unit,
  integration, end-to-end).
- **Ambiguities**: Spec gaps that block writing tests.

Do not read any other agent's output. Investigate independently.
