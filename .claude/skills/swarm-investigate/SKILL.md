---
name: swarm-investigate
description: >
  Multi-agent swarm for investigating a contemporaneous issue (production
  incident, anomaly, mysterious behavior). Produces a written report; no
  implementation phase. TRIGGER when: live production incident, anomaly,
  mysterious behavior, or "what is going on with X right now". SKIP:
  implementing a known fix (use `swarm-bug` or direct implementation).
disable-model-invocation: false
allowed-tools: Agent, Bash, Edit, Glob, Grep, Read, SendMessage, Skill, WebFetch, Write, mcp__linear__get_issue, mcp__notion__notion-fetch
argument-hint: "<issue-description-or-file> [--linear <issue-slug>]"
---

You are the Orchestrator in a 5-agent swarm for investigating
an issue. The deliverable is a written report, not a code
change. Follow every step in order.

Shared design principles, mechanics, and snippets:

@~/.claude/skills/swarm-core/PRINCIPLES.md

@~/.claude/skills/swarm-core/STEPS.md

## Agents

| Agent        | Description                                                                                          |
| ------------ | ---------------------------------------------------------------------------------------------------- |
| Orchestrator | Orchestrates phases, synthesizes findings across agents, fact-checks claims, ships the report        |
| Implementer  | Reads source code to map the relevant execution paths and identify candidate failure points         |
| Investigator | Queries databases, logs, dashboards, and external systems to confirm runtime state                  |
| Tracker      | Traces data lifecycles and inter-service boundaries to localize where the issue originated         |
| Historian    | Reads git history, migrations, recent deploys, and prior incidents to find what changed and when    |

## Abort Heuristic

If the cause becomes obvious within the first 5 minutes (e.g.,
matches a known pattern, is reproduced trivially), abort the
swarm and write a one-paragraph note instead.

**Obviousness only applies to first-look obviousness.** Do not
apply this heuristic to subsequent "this looks obvious now"
moments after partial investigation. If the synthesis root-cause
section has materially changed between rounds, the cause is not
yet obvious; keep investigating rather than declaring victory.

## Step 1: Intake

Parse `$ARGUMENTS` for the issue input and optional `--linear`
flag. The input is either a file path or inline text. If it is
a URL (Slack, Linear, dashboard, log query), fetch its contents.
If it is a file path, read it. If it is inline text, use it
directly.

Derive `{slug}` (kebab-case): the Linear issue slug if provided,
otherwise a kebab-case summary of the issue.

Derive `{domain}` and `{project_or_team}` from context. If the
issue spans multiple services, pick the team or project most
responsible for triage. If ambiguous, ask the user.

Set `{repo_path}` to the current working directory if a single
codebase is in scope; otherwise leave unset and direct agents
to specific codebases as needed.

Create a new agent-os worktree for artifacts:

```bash
git -C ~/nickolashkraus/agent-os worktree add \
  ~/nickolashkraus/agent-os/{slug} -b {slug}
```

Set `{artifact_dir}` to:

```
~/nickolashkraus/agent-os/{slug}/domains/{domain}/{projects|teams}/{name}/investigations/{slug}/
```

Create the artifact subdirectories:

```
{artifact_dir}/
  orchestrator/
    analysis.md
  implementer/
  investigator/
  tracker/
  historian/
```

Copy `~/.claude/skills/swarm-investigate/ANALYSIS.md` to
`{artifact_dir}/orchestrator/analysis.md`. Fill in
`{investigation_title}`, `## Status`, `## Context`, and
`## Symptom` sections with the raw report data: timestamps,
affected resources, error messages, environment, who reported
it.

## Step 2: Investigate (parallel)

Spawn four subagents using the Agent tool. All four must launch
in a single message (parallel, not sequential).

For each agent (implementer, investigator, tracker, historian):

1. Read the prompt template from
   `~/.claude/skills/swarm-investigate/prompts/investigate/{agent}.md`.
2. Substitute `{issue_description}`, `{repo_path}`, and
   `{output_file}` with the values from Step 1. The output
   file is `{artifact_dir}/{agent}/investigation.md`.
3. Pass the rendered prompt to the Agent tool.

**Constraint enforcement**: Do not include other agents'
findings in any agent's prompt.

**Convergence round**: Use
`~/.claude/skills/swarm-core/prompts/convergence.md`. Spawn all
four agents again with file references to each other's findings.
Each agent appends under `## Convergence`. Write
`{artifact_dir}/orchestrator/checkpoint.md` after each round.
Repeat until all four report "complete," capped at 3 rounds. A
later round may be targeted (spawn only the agents whose lens
can settle the remaining disagreement) when the open items are
narrow and the other agents' additions are mutually consistent;
record the rationale in the checkpoint.

Assemble the final agent files into
`{artifact_dir}/orchestrator/analysis.md` under the
corresponding `### Implementer`, `### Investigator`,
`### Tracker`, `### Historian` sections.

## Step 3: Synthesize

Read the full analysis document and write the synthesis under
`## Agent Synthesis`.

The synthesis must include:

- **Executive summary** (at the top of the file, before any other
  section): ~20-30 lines. Root cause or leading hypothesis in 2-3
  sentences, scope of impact, numbered recommended actions with
  one sentence each, open questions, and current approval status.
  This is what the user reads when the full document is too long
  to skim.
- **Root cause (or best hypothesis)**: One paragraph. If the
  cause is not yet certain, state the leading hypothesis and
  the evidence for and against it.
- **Timeline**: Ordered sequence of events with timestamps,
  reconciled across all agents' findings.
- **Scope of impact**: Which systems, members, or transactions
  are affected.
- **Recommended actions**: Numbered list. Each action has a
  scope, a rationale, and an owner suggestion. Distinguish
  immediate mitigations from longer-term fixes.
- **Open questions**: Anything the investigation could not
  resolve.

Use `~/.claude/skills/swarm-core/prompts/synthesis-review.md`.
Spawn the four agents in parallel. Substitute
`{own_findings_path}`, `{synthesis_path}`, and `{output_file}`
(= `{artifact_dir}/{agent}/synthesis.md`).

Read all four verdicts. If any agent has concerns, address them
and re-submit. Loop until all four approve, capped at 3 rounds.
If the root-cause section is materially rewritten between rounds,
apply the "Material-Rewrite Reset" rule from `swarm-core/PRINCIPLES.md`.

Write the final report to `{artifact_dir}/orchestrator/final.md`.

**Typography pass (before verification)**: Run the typography pass from
`~/.claude/skills/swarm-core/PRINCIPLES.md` ("Typography Discipline")
against every artifact file authored in this run.

**Verification gate (standard, not optional)**: Spawn a
dedicated verification agent that reads `final.md` end-to-end
and produces a table (one row per concrete claim) with status
Verified / Wrong / Unverifiable, evidence (file:line / SHA /
URL / DB query result), and a "Material corrections needed"
section listing every Wrong claim with replacement text. Every
concrete factual claim must be checked: code references, PR
numbers, ticket IDs, Slack timestamps, Notion docs, numerical
figures, file:line citations, and quoted snippets. Apply every
correction before presenting the report to the user. Mark
unverifiable claims as "from agent analysis, not independently
verified."

**User gate**: Present the final report to the user. Ask:
"Approve the report, or do you want to adjust the findings or
recommended actions?" Do not proceed until the user approves.

## Step 4: Ship

In the **agent-os worktree**: commit all artifacts on the
`{slug}` branch with message
`"swarm-investigate: {slug}"` and push.

If a Linear issue exists (or `--linear` was provided), update
its description with a link to `{artifact_dir}/orchestrator/final.md`
or paste the report inline using `/update-linear-issue`. If no
Linear issue exists and the user wants one, create it from the
final report using `/create-linear-issue`.

If the recommended actions include code changes, suggest
running `/swarm-bug` (for a single bug fix) or `/swarm-feature`
(for a larger remediation) to drive implementation.
