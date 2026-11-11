# GWS (Google Workspace CLI)

- ALWAYS check the entire Google Sheet, not just the first X rows.
- ALWAYS use `gws` to access Google Drive files. Do not use MCP tools or other
  methods to read Google Docs, Sheets, or other Drive files.
- Before the first `gws` call in a session, invoke the `gws` skill. It holds
  the command pattern, pagination, the profile for each working directory
  and the keyring fix, and the CLI fails silently when any of them is wrong.
