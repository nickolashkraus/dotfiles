# GWS (Google Workspace CLI)

- ALWAYS check the entire Google Sheet, not just the first X rows.
- ALWAYS use `gws` to access Google Drive files. Do not use MCP tools or other
  methods to read Google Docs, Sheets, or other Drive files.
- ALWAYS use the full `gws <service> <resource> <method>` pattern. Do not omit
  the resource name. For example:
  - `gws docs documents get` (correct), not `gws docs get` (wrong).
  - `gws sheets spreadsheets get` (correct), not `gws sheets get` (wrong).
- ALWAYS use `--page-all` to fetch all items from paginated endpoints. When
  using `--params` with a `fields` mask, include `nextPageToken` in the mask.
  Without it, `gws` cannot detect additional pages and silently returns only
  the first page.

## Account Switching

- Determine the profile from the working directory:
  - `~/Function-Health/*`: Use `function` profile.
  - Everything else: Use `personal` profile.
- For `gws`, always inline the profile since env vars do not
  persist across Bash calls:
  `GWS_PROFILE=function gws ...`
  `GWS_PROFILE=personal gws ...`
- For `gcloud`, activate the matching configuration:
  `gcloud config configurations activate function-dev`
  `gcloud config configurations activate personal`
