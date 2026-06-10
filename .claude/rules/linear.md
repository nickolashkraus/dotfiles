# Linear

- Follow @rules/typography.md for all Linear content.
- Issue titles should use Title Case.
- Issue statuses should default to Todo.
- Remove extra newlines (e.g., if lines use &lt;80 characters for human
  readability). If available, use the `clean_markdown.py` script.
- Add links to GitHub, Notion, etc. when appropriate.
- When creating issue descriptions, do not use explicit file line numbers or
  ranges. Bare file paths are fine (e.g., `` `app/ppp/stripe_service.py` ``, ``
  File: `app/foo/bar.py` ``); only the trailing line qualifiers (`:195-219`, `,
  lines 180-196`, `, around line 38`) are out.

Linear issues should use the following format:

```
## Overview

## Acceptance Criteria

## Implementation Details

## References
```

- For references, use actual links (GitHub, Linear, Notion, etc.).
