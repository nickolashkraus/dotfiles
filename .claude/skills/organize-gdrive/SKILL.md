---
name: organize-gdrive
description: >
  Audit and reorganize a Google Drive: inventory the tree, find dead
  shortcuts and duplicates, file meeting notes into their project or team
  folders, normalize meeting titles, and reconcile agent-os manifests
  against what is actually there. TRIGGER when: user says "organize my
  Drive", "clean up Google Drive", "is my Drive organized", asks to file
  or rename meeting notes, or asks to check that manifest Drive paths are
  current.
disable-model-invocation: false
allowed-tools: Bash, Edit, Glob, Grep, Read, mcp__claude_ai_Google_Drive__*
argument-hint: "[account]"
---

You are auditing and reorganizing a Google Drive. Work in the order below.
Never skip Step 6; a mutation is not done until it is verified through a
path independent of the tool that made it.

## Access Model

Two tools, two jobs. Do not substitute one for the other.

- **Read**: `gws` only, per @~/.claude/rules/gws.md. Pick the profile from
  the account: `GWS_PROFILE=function` for
  `nickolas.kraus@functionhealth.com`, `GWS_PROFILE=personal` for
  `nickolashkraus@gmail.com`.
- **Mutate**: The Google Drive MCP connector. `gws` on the `function`
  profile runs on an ADC token scoped `drive.readonly` and every write
  403s. Do not try to widen that scope; see
  @~/.claude/rules/function-health.md and the standing memory. The
  connector is bound to the FH account and does write.

`gws` is a shell function, not a binary on `PATH`. Call it from Bash. A
Python `subprocess` call to `gws` skips the wrapper, authenticates as
something else, and returns `{"files":[]}` with exit 0, which reads as an
empty folder rather than an error.

What the connector can do:

| Operation          | Tool                          | Available       |
| ------------------ | ----------------------------- | --------------- |
| Move a doc you own | `update_file` with `parentId` | Yes             |
| Rename             | `update_file` with `title`    | Yes             |
| Create a folder    | `create_file`                 | Yes             |
| Trash              | `trash_file`                  | Yes, reversible |
| Create a shortcut  | None                          | No              |

**Shortcut creation is the one gap.** `create_file` rejects
`application/vnd.google-apps.shortcut` ("Only the following first-party
mimetypes are supported for empty files") and exposes no `targetId`. Any
plan that depends on minting a shortcut has to end in a hand-off to the
user.

**Never call `update_file` with `parentId` on a doc you do not own.**
Drive dropped multi-parenting in 2020, so `parentId` replaces the parent
rather than adding one. On someone else's doc that is a move, and it
pulls their document out of their own Drive. Check `ownedByMe` first. A
shortcut is always safe to move, because the shortcut object is yours
even when its target is not.

## Step 1: Inventory

Pull everything the user owns into the scratchpad, then work from the
local copy rather than re-querying:

```bash
GWS_PROFILE=function gws drive files list --page-all --page-limit 50 --params \
  "{\"q\":\"'me' in owners and trashed = false\",\"pageSize\":1000,\"fields\":\"nextPageToken,files(id,name,mimeType,parents,modifiedTime,shortcutDetails)\"}" \
  | grep -v keyring > "$SP/drive.ndjson"
```

Use the double-quoted form. The Drive `q` syntax needs single quotes
around literals, so single-quoting the whole `--params` value turns into
unreadable `'"'"'` escaping.

Strip the `Using keyring backend: file` line on the personal profile
before any JSON parse, or the decode fails at char 0.

Build a path helper from `parents[0]` and print the tree, collapsing any
folder with more than about eight leaf files so the output stays
readable. Folder names contain `/` (`TS/PPP/Checkout`), so join path
segments with ` > ` rather than `/`.

## Step 2: Health Audit

Run every check. Report the clean ones too; "no dead shortcuts" is a
result the user wants.

- **Dead shortcuts**: Resolve every `shortcutDetails.targetId`. A cached
  `targetMimeType` does NOT prove the target still exists, so fetch each
  one.
- **Name drift**: Shortcut name against the live target name, after
  normalizing both with the Step 4 title rule. Shortcuts are renamed on
  purpose, so only a difference in the event name or date is drift.
- **Duplicate names** and **duplicate shortcut targets** (two shortcuts
  to one doc).
- **Empty folders**, **orphans**, **multi-parent items**.
- **External exposure**: Any permission with `type: anyone`, a
  non-company `emailAddress`, or a foreign `domain`.
- **Projects without a local project**: Every folder under `Projects`
  and `Teams` needs an agent-os `manifest.yaml` whose `gdrive.root` is
  that folder (Step 7 runs the match).

For the per-file fan-out, mint a token once and use threads. A raw
`curl`/`urllib` call against `drive.googleapis.com` with an ADC token
needs the quota-project header or every request returns a misleading
`403 SERVICE_DISABLED`:

```bash
TOK=$(GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/adc-function-dev.json \
  gcloud auth application-default print-access-token)
# then send both headers:
#   Authorization: Bearer $TOK
#   x-goog-user-project: function-health-dev-env
```

That 403 is not a permissions problem. Do not report it as one.

Treat a hub doc sharing its folder's name (a `PPP Service` shortcut
inside the `PPP Service` folder) as intentional, not a duplicate.

## Step 3: Place Meetings

Every dated meeting item has exactly one home:

| Meeting                                | Home                                          |
| -------------------------------------- | --------------------------------------------- |
| Series with 3+ distinct dates          | `<Project or Team>/<Event>` folder            |
| One-off that belongs to a project/team | Directly in that project or team folder       |
| One-off with no project (1:1s, ad hoc) | `Google Meet/Meeting Notes`                   |

Group by the series name with the date, the time, the `- 1`/`- 2`
same-day label, and the `Notes by Gemini`/`Recording` suffix stripped.
Then apply:

- **Count distinct dates, not items.** Notes plus Recording of one
  meeting is one date and is not a series. A duplicate shortcut in two
  folders is also one date.
- **Merge title variants.** The same standing meeting drifts across
  titles (`... (Bi-Weekly)`, `... (Bi-Weekly) - Amit hosting`, and the
  bare name). Fold them together and name the folder after the dominant
  title.
- **`Meeting started ...` is not a series.** Gemini uses that one title
  for unrelated meetings. Rename each one (Step 4), then place it as a
  one-off.
- **Leave standing hub docs at the project level.** A `Notes - <Event>`
  running-notes doc is not a dated instance; burying it among the
  instances makes it harder to find.
- **Skip** a series already in its own folder in the right project.
- **Flatten one-off meeting folders.** A folder holding a single
  meeting's notes and recording is clutter: move its items up into their
  home and trash the emptied folder.
- **Empty Meet's auto folders.** Meet creates
  `Google Meet/<Event> (recurring)` and per-meeting folders and drops new
  shortcuts there. Move every item out to its home, then trash each
  emptied subfolder. Meet recreates one when the next meeting runs. Never
  trash `Google Meet` itself or `Google Meet/Meeting Notes`.
- **Duplicate shortcuts**: Keep the copy in the item's home per the table
  above and trash the other.

Surface every judgment call in the final report, especially the series
you excluded and why, and any one-off whose project was a guess.

## Step 4: Normalize Meeting Titles

Rename every dated meeting item the user owns (shortcuts, Gemini notes
docs and recordings) to `<Event> - YYYY/MM/DD`, and
`<Event> - YYYY/MM/DD - Recording` for a recording:

- **Drop**: The time, the time zone (including `GMT-03:00` offsets, so
  match `GMT[+-]HH:MM` before a bare `[A-Z]{2,5}` zone), and
  `Notes by Gemini` in either the `- Notes by Gemini` or
  `[Notes by Gemini]` form.
- **Insert** ` - ` before the date when Gemini left it out
  (`PPP Service | EasyDeploy 2026/08/19`).
- **Same-day meetings**: When two meetings of one series fall on the same
  day, label them `<Event> - YYYY/MM/DD - 1` and `- 2` in time order.
  Read the order from the old titles' times, or from `createdTime` when a
  title has none.
- **Generic titles**: Rename `Meeting started ...` to a descriptive event
  name taken from the notes' summary.

Before renaming, check the plan for collisions within one folder; a
collision is a same-day pair that needs the `- 1`/`- 2` label.

Renaming a doc the user owns changes its title for every attendee;
renaming a shortcut changes only the user's Drive. Both are approved.
Meet keeps writing new items with the time, so run this on every pass.

## Step 5: Execute

Create folders first, then move, then rename, then trash. Issue
`update_file` calls about 20 per message so they run concurrently; the
connector has no batch endpoint.

Before the first call, confirm the whole move set is objects the user
owns. Dump the id-to-change lists (moves, renames, trashes) to the
scratchpad so a crash mid-run is recoverable.

Each connector call echoes the full file object, so a run past about 40
calls floods the context. Hand the remaining list to a background agent
with the scratchpad file path, the exact tool and arguments allowed
(`fileId` plus `title`, or `fileId` plus `parentId`), and a results file
to append to. Verify its work yourself in Step 6.

Trash only what Step 3 marks for trash, and only after re-listing the
folder and confirming it is empty.

## Step 6: Verify

Never trust the connector's own response echo. Re-read through `gws` or
the Drive API and assert:

1. Each destination folder holds the expected count.
2. Each moved ID has the intended `parents[0]` and is not trashed.
3. Each renamed ID has the intended title, and no owned item still
   carries a time or `Notes by Gemini`.
4. Each trashed ID reports `trashed: true`.

Report the ratio (`80 / 80 landed`), not a claim that it worked.

## Step 7: Reconcile agent-os Manifests

Each team and project under `~/nickolashkraus/agent-os/master/domains/`
has a `manifest.yaml` whose `gdrive` block carries a `root` folder ID,
an optional `folders` list, and `docs`/`sheets` entries. Discover them:

```bash
find domains -name manifest.yaml
```

Extract every Drive ID from the `gdrive` block of each manifest, resolve
each against the live Drive, and report anything that 404s or comes back
trashed. Skip the `local:` keys, which hold repo paths that can look
like IDs. Then:

- Repoint a `root` whose folder was trashed or merged away.
- Delete keys pointing at files that no longer exist.
- Add a `folders:` entry for each new event folder from Step 3, with a
  one-line `note` giving the date range.
- Report every `Projects` or `Teams` folder that no manifest's
  `gdrive.root` points at, and offer to create the local project. Do not
  create one unasked.

Leave a manifest `name:` that mirrors a doc someone else owns as it is;
only the user's shortcut to it was renamed, so the doc's real title still
carries the time.

**A 404 on the `function` profile does not mean the ID is dead.** Check
the entry's `profile:` key first. A `profile: personal` resource lives in
the personal account and resolves only under `GWS_PROFILE=personal`.
Validate on both profiles before calling anything broken, and fix the
report rather than the manifest if it turns out to be a false positive.

Afterwards, confirm every manifest still parses:

```bash
python3 -c "
import glob,yaml
for p in glob.glob('domains/**/manifest.yaml',recursive=True): yaml.safe_load(open(p))
print('ok')"
```

Manifest edits made through Bash bypass the outbound linter hook, so run
it by hand on each changed file (see the linting note in
`agent-os/master/.claude/skills/recurring/SKILL.md`).

## Reporting

Lead with the counts and the clean checks, then the findings, then the
judgment calls. Name what you deliberately did not do.

The trashes in Step 3 (emptied Meet subfolders, flattened one-off
folders, duplicate shortcuts) are standing approvals. Anything else, such
as an empty project folder or a stale doc, is surfaced and offered, never
trashed unasked.
