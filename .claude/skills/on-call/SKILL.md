---
name: on-call
description: >
  Always-awake on-call responder for the (1) BYBO Escalation path in
  incident.io. Each tick lists live pages, acks any that target Nickolas
  before the ten-minute level timer climbs past him, classifies every page,
  runs a quick outage check, and pushes a notification to Nickolas only for
  a human-declared incident or a clear outage. Pair with `/loop`. TRIGGER
  when: user says "on-call", "start on-call", "watch the pager", "go on
  call", or a /loop run invokes it. SKIP: a one-off "why was I paged" read
  (answer it directly with escalation_list).
disable-model-invocation: false
allowed-tools: >
  Bash, Read, Write, Edit, Agent, Skill, ScheduleWakeup, PushNotification,
  mcp__incident-io__escalation_list,
  mcp__incident-io__escalation_show,
  mcp__incident-io__escalation_respond,
  mcp__incident-io__schedule_list,
  mcp__incident-io__alert_show,
  mcp__incident-io__incident_show,
  mcp__incident-io__incident_update_list,
  mcp__datadog__search_datadog_spans,
  mcp__datadog__search_datadog_logs,
  mcp__datadog__get_datadog_metric,
  mcp__claude_ai_Slack__slack_send_message
argument-hint: "[--role leader|follower] [--dry-run] [--off-shift]"
---

# On-Call

Phase one of the on-call agent: watch, ack, classify, and page Nickolas when
it matters. It posts nothing to Slack or incident.io beyond the ack. The spec,
the decisions, and the shift records live in
`~/nickolashkraus/agent-os/master/domains/function/projects/on-call/`.

## Usage

Run one loop per machine, with distinct roles:

```
/loop /on-call --role leader       # machine A: acts on the first tick
/loop /on-call --role follower     # machine B: acts only if A missed
/loop /on-call --dry-run           # log what would happen, ack nothing
```

The loop is self-paced. Every tick ends with `ScheduleWakeup` at 60 seconds
while Nickolas is on shift (the level timer is ten minutes, and a tick must
never be the reason a page climbs), and 300 seconds otherwise, where the
only work is the liveness check. `--off-shift` forces the 60-second cadence
outside a shift, for drills.

## Constants

| Name            | Value                                  |
| --------------- | -------------------------------------- |
| Path            | `01KNJ8X5TEDYMKF4KHN8PFMWV4` (`EP011`) |
| Schedule        | `01KNJ9SEX49XSC6SB6A47JV50F`           |
| Me              | `01K62P0TBPYTRRP4NHV70VA3RD`           |
| Follower delay  | 90 seconds after `created_at`          |
| Lookback        | 2 hours                                |
| Outage check    | 3 minutes, in a subagent               |
| State directory | `~/.local/state/on-call/`              |

State is machine-local and never committed: `heartbeat` (one line, the last
successful tick in RFC 3339), `pages.jsonl` (one line per page the machine
has seen, with the action it took), and `control` (the current control
verb). incident.io is the only cross-machine truth; never assume the other
machine's state from local files.

## Hard Limits

The agent never nacks, never creates a notification pause or a schedule
override, never declares, updates, or closes an incident, never posts to
any Slack channel or DM other than Nickolas's own, never posts to an
incident channel, never changes a monitor, never deploys,
never merges, and never runs `/swarm-bug`. The only writes are
`escalation_respond` with `ack`, the self-DM, local state, and the shift
log. Anything
else waits for Nickolas, and the page-me notification is how he finds out.

## Tick

Follow every step in order. Keep the whole tick under 30 seconds; anything
slower runs in a subagent that reports back on a later tick.

### Step 1: Control

Read `~/nickolashkraus/agent-os/master/tasks/remote/` for files named
`on-call-*.md` with `status: pending`. The body is one verb:

- **`stand down`**: Stop acking and classifying. Keep the liveness check
  and the heartbeat. Persist `stand-down` to `control`.
- **`resume`**: Clear `control`.
- **`take over`**: Nickolas is at the keyboard. Same as `stand down`, but
  log that he took over so the shift report reads correctly.
- **`page all <N>h`**: For the next N hours, notify on every page regardless
  of class. Persist `page-all until <RFC 3339>` to `control`.

Mark each file `status: done` with a `## Result` line, the same shape
`/remote` uses. The control file wins over everything below.

### Step 2: Liveness

Call `schedule_list` with `user: "me"`. This is the authenticated read: a
failure means the OAuth token behind the MCP is gone, and the agent cannot
ack anything. On failure, notify once ("on-call: incident.io auth failed,
re-login needed"; notify is defined in Step 6), log it, and skip to Step 7
with a 60-second wakeup. Do not send the notification again until a tick succeeds.

From the result, record whether Nickolas is on shift now (a
`user_current_shift` on the BYBO Responders schedule) and which rotation.
Write the heartbeat.

### Step 3: Read

Call `escalation_list` with `escalation_path: [path]`, `created_after` set
to now minus the lookback, `status: ["pending", "triggered", "acked",
"pending_repeat"]`, and `page_size: 50`. Resolved and canceled pages are
history, not work, so leave them out. Diff the result against
`pages.jsonl`: anything not seen before is new, anything seen whose status
changed is an update.

Do not use `incident_list` or `incident_show` in the hot path; both have
failed schema validation on some days. `escalation_list` has not.

### Step 4: Ack

For each page where `you.paged` is true, `you.acked` is false, and `status`
is `triggered`:

- **Leader**: Call `escalation_respond` with `ack` now.
- **Follower**: Call it only if `created_at` is more than the follower delay
  in the past and the page is still `triggered` on a fresh `escalation_show`.
  A page the leader already acked shows `acked` and is skipped.
- **Dry run**: Log `would-ack` and do nothing.

Record the result, including an error, in `pages.jsonl` and the shift log.
If `escalation_respond` errors on a page that still targets Nickolas, retry
once on this tick, then notify him: an unacked page is the one failure this
skill exists to prevent.

Under `stand-down` or `take over`, skip this step entirely.

### Step 5: Classify

Classify every new page on the path, not only the ones that paged Nickolas,
so the shift log is a complete record. The class comes from `created_by`
and the title:

- **`human`**: `created_by.type` is `user`, or it is `workflow` (the Pillar
  1 Workflow pages the path when someone declares an incident). These carry
  an `incident_reference`.
- **`known-noise`**: An alert whose title matches the noise set below.
- **`alert`**: Every other alert.

Noise set (from the BYBO Alert Tuning project):

| Pattern                                                 | Why                                   |
| ------------------------------------------------------- | ------------------------------------- |
| `[No data]` on `MEMORYSTORE REDIS` (member-ingest)      | Metric gaps on a Tier 2 cache         |
| `[No data]` on any Tier 2 monitor                       | Same                                  |
| `[Warn]` severity on any monitor                        | Warn states should not page           |
| `CLOUD RUN HIGH LATENCY` with a single-minute window    | One slow request on a quiet service   |

`MAM Checkout 5xx error count` is not in the noise set. It pages often, but
each firing is a real burst of failed checkouts until the outage check says
otherwise.

### Step 6: Decide

Decide once per new page, in this order:

1. **`page-all` is active**: Notify on everything.
2. **`human`**: Notify now. Message: `on-call: INC-NNNN <title> declared by
   <name>`. A human already in the incident is the one case the agent must
   never sit on.
3. **`known-noise`**: Log and watch. If the same monitor pages three times
   inside an hour, notify once with the count; recurrence is the signal,
   not the firing.
4. **`alert`**: Start the outage check in a subagent (below) and move on.
   When it reports back, notify only on `outage`. On `not-outage` or
   `unknown`, log the finding. An `unknown` that is still `triggered` on the
   next tick after ten minutes from `created_at` is notified as "could not
   classify", because the requirement is to page on failure to classify,
   not to stay quiet.

Notify means two sends of the same line, under 200 characters, leading
with the incident reference or the service: a `PushNotification` with
`status: proactive`, and a Slack DM to Nickolas himself (`channel_id`
`U09H5CVRGTG`) through `slack_send_message`. Nickolas turned off incident.io
push on his phone on 2026-10-22, so Slack push is the channel that reaches
him; the "Sent using Claude" line the MCP appends is fine in a self-DM.
The self-DM is the only Slack destination this skill may write to. One
notify per page. Log every decision with its reason.

#### Outage check

Spawn an `Agent` (general-purpose) with the page title, the alert ID, the
service, and this brief. It has three minutes and returns one word plus one
line of evidence: `outage`, `not-outage`, or `unknown`.

An outage is one of:

- Checkout 5xx ratio above 50% for five minutes (`transaction`,
  `POST /stripe/create_payment_intent` or `purchase_invoice` resources).
- `STRIPE ENDPOINTS 5xx` or `STRIPE THROTTLING` firing on real traffic
  (more than ten requests in the window).
- Cloud Run 5xx on `prod-membership-service`, `prod-ppp-service`, or
  `production-transaction-service` above 5% of requests for five minutes.
- `DB CONNECTION SATURATION` or `DB CONNECTIONS WAITING` on
  `production-transaction` with waiting connections still climbing.
- A `REQUESTS SLO BURN RATE` fast burn with 5xx spans present.

The evidence comes from Datadog: spans with `env:production
service:<apm-service> @http.status_code:[500 TO 599]` over the page window
first, then logs on the same window for the error text. The APM service tag
is `transaction`, not the Cloud Run name. When APM shows no 5xx but the SLO
still burns, read the Cloud Run `run.googleapis.com/request_count` metric
with `response_code_class="5xx"`. Ten retries from one member against an
already-succeeded PaymentIntent is `not-outage`; that exact shape produced
a "75% 5xx on checkout" page on 2026-09-22.

The check decides whether to wake Nickolas, nothing more. It does not
investigate root cause; that is phase three.

### Step 7: Log and schedule

Append to the shift log at
`~/nickolashkraus/agent-os/master/domains/function/projects/on-call/shifts/<shift-start-date>.md`,
one line per event:

```
- 2026-11-03T18:04:11Z 01M5FNWPPYA7N0VCGXSXAPK7XW alert "DB IDLE-IN-TRANSACTION (production-transaction)" acked 41s outage-check=not-outage (3 spans, one cron caller)
```

Outside a shift, log only liveness failures and control changes. Then call
`ScheduleWakeup`: 60 seconds on shift or with `--off-shift`, 300 seconds
otherwise, `noop: true` when nothing was acked, classified, or notified.

## Shift Report

When Step 2 shows the shift has ended (the previous tick was on shift and
this one is not), write a `## Report` section at the end of the shift log:
pages by class, pages acked with the ack latency, notifications sent and
why, anything still `triggered` or `acked` without a resolution, and any
liveness failures. Add a one-paragraph summary to the day's
`notes/daily` file.

## Known Gaps

- `escalation_respond` acts for the authenticated user, so pages that do
  not target Nickolas cannot be acked here. Whether incident.io accepts an
  ack from a non-target is untested.
- Phase two adds the Slack carve-out (templated triage notes in Nickolas's
  voice, with a second agent checking the voice) and the heartbeat
  watchdog. The Slack MCP appends a "Sent using Claude" line to every
  message, so the notes need a different transport before that phase
  starts.
