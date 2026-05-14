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
- For methods with a request body (e.g., `gmail messages modify`, `gmail
  messages send`), pass body fields via `--json`, not `--params`. `--params` is
  only for URL/query parameters like `userId` and `id`.

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

## Keyring Backend

The personal `gws` profile must use the file-based keyring backend. Set
`GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND=file` (the export lives in
`dotfiles/.config/shell/exports.sh`). The macOS Keychain backend
intermittently fails with "User canceled the operation," which causes `gws`
to delete `credentials.enc` on every run and break all personal Gmail and
Drive access. When invoking `gws` from a script or subshell, ensure the
env var is set. If personal auth breaks again, re-run `gws auth login`.
