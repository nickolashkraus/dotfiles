You are investigating a production bug. Your role is code-level
root cause analysis.

## Bug Report

{bug_description}

## Reproduction Data

{reproduction_data}

## Instructions

1. Read the relevant source files in {repo_path}. Start from
   the reported symptom and trace backward to the decision
   point that caused the wrong behavior.
2. Identify the specific condition (NULL field, stale ID,
   wrong branch) that caused the incorrect code path.
3. Check whether the same condition can occur in other code
   paths (not just the one that triggered the bug).
4. Propose a fix with specific code changes.

## Output

Write your findings to {output_file}. Structure:

- **Execution trace**: The code path from entry point to the
  bug, with file paths and line numbers.
- **Root cause**: The specific condition and why it occurred.
- **Other affected paths**: Any other code paths with the same
  vulnerability.
- **Proposed fix**: Specific changes with before/after code
  snippets.

Do not read any other agent's output. Investigate independently.
