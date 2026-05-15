# Notion

- Follow @rules/typography.md for all Notion content.
- Remove extra newlines (e.g., if lines use &lt;80 characters for human
  readability). If available, use the `clean_markdown.py` script.

## MCP Serialization Artifacts

When reviewing Notion pages via `mcp__notion__notion-fetch`, the output is
enhanced Markdown. Three patterns come back as artifacts and render correctly
in the actual Notion page. Do not flag them as formatting bugs:

- `\$` and `\~`: literal `$` and `~` get Markdown-escaped to suppress
  auto-formatting.
- `**text ****`code`**** more text**`: bold runs around inline code come back
  as toggle-off-toggle-on around the code span.
- `****` adjacent to code spans: same serialization artifact.

Focus a formatting review on em dashes (U+2014), smart quotes (U+2018/2019/
201C/201D), broken table rows, stray backticks, malformed links, and title
casing. If unsure whether a pattern is real, ask the user to spot-check the
rendered page before reporting.
