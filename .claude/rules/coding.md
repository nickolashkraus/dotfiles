# Coding

## Codebases

- **Function Health**: ~/Function-Health
- **Function Health Terraform Modules**: ~/Function-Health-Terraform-Modules
- **Infrable**: ~/infrable-io
- **Grind**: ~/grind-rip
- **Personal**: ~/nickolashkraus

## Comments

- Follow @rules/typography.md for all comments.
- Only add comments where the logic is not self-evident. The code should speak
  for itself.
- Never add decorative section dividers (e.g., `# --- Section ---`, `#
  ========`, `# *** Helpers ***`). Use whitespace and code structure to convey
  organization.
- Never add comments that merely restate the function or variable name (e.g.,
  `# Get the user` above `get_user()`).
- Never add trailing comments that narrate what a line does (e.g., `x
  = 1  # set x to 1`).

## Testing

- Write unit tests when appropriate. Tests should validate behavior and prevent
  regressions, particularly for business logic, edge cases, and functions with
  multiple code paths. Aim for 100% test coverage, but avoid tests for trivial
  code or framework-generated scaffolding. Use your best judgment.

## Docker

- Always build Docker images that are not intended to be run locally for
  `linux/amd64` (`--platform linux/amd64`) to ensure compatibility with
  external cloud environments (AWS, Google Cloud, etc.).
