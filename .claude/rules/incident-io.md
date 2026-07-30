# incident.io

## Closing Incidents

- Never accept an incident (move it out of Triage into an active status)
  without asking first, even when acceptance looks like the only path to the
  requested end state. Accepting fires the accepted-at lifecycle, posts status
  updates, and makes the incident look like it had an active response it never
  had. Only accept when there is a real active response to run.
- incident.io rejects a direct Triage to Closed transition
  (`triage_not_resolvable`). From Triage, the terminal options are Declined
  ("doesn't need incident response") or Canceled ("false alarm"), both of
  which take a summary.
- When asked to close out a stale incident sitting in Triage, set the summary
  and move straight to Declined in one `incident_update` call. If Declined or
  Canceled seems wrong for the situation, surface the lifecycle constraint and
  let the user choose between Declined, Canceled, or accept-then-close.
