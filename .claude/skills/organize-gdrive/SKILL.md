---
name: organize-gdrive
description: >
  Audit and reorganize a Google Drive: inventory the tree, find dead
  shortcuts and duplicates, group recurring meeting notes into per-event
  folders, and reconcile agent-os manifest Drive IDs against what is
  actually there. TRIGGER when: user says "organize my Drive", "clean up
  Google Drive", "is my Drive organized", asks to file meeting notes, or
  asks to check that manifest Drive paths are current.
disable-model-invocation: false
allowed-tools: Bash, Edit, Glob, Grep, Read, mcp__claude_ai_Google_Drive__*
argument-hint: "[account]"
---

You are auditing and reorganizing a Google Drive. Work in the order below.
Never skip Step 5; a mutation is not done until it is verified through a
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
readable.

## Step 2: Health Audit

Run every check. Report the clean ones too; "no dead shortcuts" is a
result the user wants.

- **Dead shortcuts**: Resolve every `shortcutDetails.targetId`. A cached
  `targetMimeType` does NOT prove the target still exists, so fetch each
  one.
- **Name drift**: Shortcut name against the live target name.
- **Duplicate names** and **duplicate shortcut targets** (two shortcuts
  to one doc).
- **Empty folders**, **orphans**, **multi-parent items**.
- **External exposure**: Any permission with `type: anyone`, a
  non-company `emailAddress`, or a foreign `domain`.

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

## Step 3: Group Recurring Meetings

The organizing rule: **one folder per recurring event, named with the
event name, living inside the project or team folder that owns it.**

Group by the series name with the trailing date, time, and
`Notes by Gemini` / `Recording` suffix stripped. Then apply:

- **Include** a series with **three or more distinct dates**. Below that
  a folder is noise.
- **Count distinct dates, not items.** Notes plus Recording of one
  meeting is one date and is not a series. A duplicate shortcut in two
  folders is also one date.
- **Merge title variants.** The same standing meeting drifts across
  titles (`... (Bi-Weekly)`, `... (Bi-Weekly) - Amit hosting`, and the
  bare name). Fold them together and name the folder after the dominant
  title.
- **Exclude** Gemini's generic `Meeting started ...`, which is one title
  covering unrelated meetings.
- **Leave standing hub docs at the project level.** A `Notes - <Event>`
  running-notes doc is not a dated instance; burying it among the
  instances makes it harder to find.
- **Skip** a series already in its own folder.

Surface every judgment call in the final report, especially the series
you excluded and why.

## Step 4: Execute

Create folders first, then move. Issue `update_file` calls several per
message so they run concurrently; the connector has no batch endpoint and
a large regrouping runs to dozens of calls.

Before the first move, confirm the whole move set is objects the user
owns. Dump the id-to-destination list to the scratchpad so a crash
mid-run is recoverable.

## Step 5: Verify

Never trust the connector's own response echo. Re-read through `gws` or
the Drive API and assert two things:

1. Each destination folder holds the expected count.
2. Each moved ID has the intended `parents[0]` and is not trashed.

Report the ratio (`80 / 80 landed`), not a claim that it worked.

## Step 6: Reconcile agent-os Manifests

Each team and project under `~/nickolashkraus/agent-os/master/domains/`
has a `manifest.yaml` whose `gdrive` block carries a `root` folder ID,
an optional `folders` list, and `docs`/`sheets` entries. Discover them:

```bash
find domains -name manifest.yaml
```

Extract every long ID from the `gdrive` block of each manifest, resolve
each against the live Drive, and report anything that 404s or comes back
trashed. Then:

- Repoint a `root` whose folder was trashed or renamed away.
- Delete keys pointing at files that no longer exist.
- Add a `folders:` entry for each new event folder from Step 3, with a
  one-line `note` giving the date range.

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
judgment calls. Name what you deliberately did not do. Do not trash
anything the user did not ask you to trash; surface it and offer.

`Meeting Notes` and `Google Meet` are auto-drop folders that Gemini and
Meet write into and recreate. An empty `Google Meet` is not a leftover.
