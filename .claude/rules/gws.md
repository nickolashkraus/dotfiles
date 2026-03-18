# GWS (Google Workspace CLI)

- ALWAYS check the entire Google Sheet, not just the first X rows.
- ALWAYS use `gws` to access Google Drive files. Do not use MCP tools or other
  methods to read Google Docs, Sheets, or other Drive files.
- ALWAYS use the full `gws <service> <resource> <method>` pattern. Do not omit
  the resource name. For example:
  - `gws docs documents get` (correct), not `gws docs get` (wrong).
  - `gws sheets spreadsheets get` (correct), not `gws sheets get` (wrong).
