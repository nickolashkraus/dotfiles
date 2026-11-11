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

>>> 🤖 Agent Notes

>>>
```

- For references, use actual links (GitHub, Linear, Notion, etc.).
- The sections above the notes are for a person and have to be readable in
  under a minute. Keep the overview to a few sentences, the acceptance
  criteria to a handful of short bullets and the implementation details to
  the points a reviewer has to know. Cut everything else from them.
- **Agent Notes** is a collapsed section at the end of the description. It
  holds ALL the remaining relevant information: evidence, numbers and dates,
  code paths, the null option, rejected alternatives and open decisions. Move
  detail there instead of deleting it, as labeled bullets. Linear stores the
  section as `>>> 🤖 Agent Notes`, the content, then `>>>` on its own line,
  and that text round-trips unchanged through `save_issue`.
- `save_issue` can return the previous description after an update. Confirm
  a write with `get_issue`, not with the save response.
