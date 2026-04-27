---
name: swarm
description: >
  Multi-agent swarm with independent parallel investigation followed by
  structured synthesis, implementation, and multi-agent review.
disable-model-invocation: false
allowed-tools: Agent, Bash, Edit, Glob, Grep, Read, Skill, Write
argument-hint: <bug-report> [--linear <issue-slug>]
---

You are the Orchestrator in a 5-agent swarm for fixing hard
bugs. Follow every step in order.

Read `~/.claude/skills/swarm/PRINCIPLES.md` for the design
principles and lessons that inform this workflow.

## Agents

| Agent        | Description                                                                                     |
| ------------ | ----------------------------------------------------------------------------------------------- |
| Orchestrator | Orchestrates phases, synthesizes findings across agents, fact-checks claims, ships deliverables |
| Implementer  | Reads source code to trace execution paths, identify root causes, and map failure modes         |
| Tester       | Reproduces bugs, writes regression tests, validates edge cases and fix completeness             |
| Investigator | Queries databases, Stripe, and external systems to audit runtime state and data integrity       |
| Tracker      | Traces data through webhooks, migrations, event handlers, and inter-service boundaries          |

## Abort Heuristic

If the root cause becomes obvious within the first 5 minutes of
reading the bug report, abort the swarm and fix it directly.

## Step 1: Intake

Parse `$ARGUMENTS` for the bug report and optional `--linear`
flag. If the bug report is a URL (Slack, Linear, GitHub), fetch
its contents. If it is a file path, read it. If it is inline
text, use it directly.

Create the artifact directory:

```
agent-os/domains/<domain>/projects/<project>/bugs/<slug>/
  orchestrator/
    analysis.md
  implementer/
  tester/
  investigator/
  tracker/
```

Where `<slug>` is the Linear issue slug if provided, or a
kebab-case summary derived from the bug report. Derive
`<domain>` and `<project>` from the repo path using the
existing `agent-os/domains/` directory structure as the mapping
(e.g., `Function-Health/transaction-service` maps to
`domains/function/projects/pricing-packaging-payments-service`).
If the mapping is ambiguous, ask the user.

Set `{repo_path}` to the current working directory. This is the
codebase agents will investigate.

Copy `~/.claude/skills/swarm/ANALYSIS.md` to
`orchestrator/analysis.md`. Fill in `{bug_title}` and the
`## Description` section with reproduction data: member IDs,
customer IDs, subscription IDs, timestamps, environment.

## Step 2: Investigate (parallel)

Spawn four subagents using the Agent tool. All four must launch
in a single message (parallel, not sequential). Investigation
agents read the codebase but do not write code, so they run
against the main working directory (no worktree needed).

For each agent (implementer, tester, investigator, tracker):

1. Read the prompt template from
   `~/.claude/skills/swarm/prompts/investigate/{agent}.md`.
2. Substitute `{bug_description}`, `{reproduction_data}`,
   `{repo_path}`, and `{output_file}` with the values from
   Step 1. The output file is
   `<artifact_dir>/{agent}/investigation.md`.
3. Pass the rendered prompt to the Agent tool.

**Constraint enforcement**: Do not include other agents'
findings in any agent's prompt. Each agent sees only the bug
report.

When all four agents complete, read each agent's
`investigation.md`.

**Convergence round**: Read the convergence prompt from
`~/.claude/skills/swarm/prompts/convergence.md`. Spawn all
four agents again. Substitute `{own_findings_path}` with the
agent's `investigation.md` path, `{other_findings_paths}` with
the other three agents' paths, and `{output_file}` with the
agent's `investigation.md`. Each agent reads the files and
appends under a `## Convergence` section. Write
`orchestrator/checkpoint.md` after each round with the round
number and each agent's verdict. Repeat until all four report
"complete," capped at 3 rounds.

Assemble the final agent files into
`orchestrator/analysis.md` under the corresponding
`### Implementer`, `### Tester`, etc. sections.

## Step 3: Synthesize

Read the full analysis document (all four agent sections) and
write the initial synthesis under `## Agent Synthesis`.

The synthesis must include:

- **Root cause**: One paragraph describing the compounding
  failure chain.
- **Failure modes**: Numbered list, each with a trigger
  condition, symptom, and affected code path.
- **Fix layers**: Ordered by dependency. Each layer has a
  scope, rationale, and files changed.
- **Dependency ordering**: Explicit statement of which layers
  must execute before others and why.

Read the synthesis review prompt from
`~/.claude/skills/swarm/prompts/synthesis-review.md`. Spawn
the four agents again (parallel). For each, substitute
`{own_findings_path}` with the path to the agent's
`investigation.md`, `{synthesis_path}` with the path to
`orchestrator/analysis.md`, and `{output_file}` with
`<artifact_dir>/{agent}/synthesis.md`.

Read all four verdicts. If any agent has concerns, address the
objections, update the synthesis, and re-submit for review.
Loop until all four agents approve, capped at 3 rounds. If
consensus is not reached, surface the remaining disagreements
to the user.

Write the final analysis to `orchestrator/final.md`.

**Fact-check gate**: Before finalizing, verify every factual
claim in the synthesis against the codebase. For each claim:

- If it references a specific function or behavior, grep for
  the function and read the relevant code.
- If it references database state, note it as "unverified,
  from agent analysis" unless you can query the database.
- If a claim is wrong, correct it and note the correction.

**User gate**: Present the final analysis to the user. Ask:
"Ready to implement, or do you want to adjust the fix plan?"
Do not proceed until the user approves.

**Linear issue**: If no `--linear` flag was provided, create a
Linear issue from `orchestrator/final.md` using
`/create-linear-issue`. Use the returned issue slug for the
branch name in Step 4.

## Step 4: Implement

Create a Git worktree for the Linear issue (or derived branch
name). Spawn a single implementation agent in the worktree
with:

- The final analysis document (full text, inline).
- The worktree path.
- Instructions to implement each layer in dependency order.
- Instructions to write tests for every new code path.
- Instructions to run the project's full CI locally before
  reporting completion.

The implementation agent works independently. If the spec is
ambiguous, it should make a judgment call and document the
decision in a code comment, not stop and ask.

When the implementation agent completes, read the diff to
verify all layers are present.

## Step 5: Review (parallel)

Before spawning reviewers, commit the implementation
(`git add -A && git commit`) so reviewers run against a fixed
commit SHA, not the working tree.

For each agent (implementer, tester, investigator, tracker):

1. Read the review prompt from
   `~/.claude/skills/swarm/prompts/review/{agent}.md`.
2. Substitute `{final_analysis}` with the content of
   `orchestrator/final.md`, `{diff}` with the output of
   `git diff <default-branch>...<commit-sha>`,
   `{prior_analysis}` with the agent's `investigation.md`
   content, `{prior_findings}` with empty string (first
   round), and `{output_file}` with
   `<artifact_dir>/{agent}/review.md`.
3. Pass the rendered prompt to the Agent tool.

Spawn all four in a single message (parallel).

Read all four review files. Assemble
`orchestrator/findings.md` with per-agent sections. Each agent
writes a verdict: "approved," "approved with observations," or
"has blocking findings."

If all four agents approve, skip to Step 7.

## Step 6: Apply findings

Send `orchestrator/findings.md` to the implementation agent
(via SendMessage to the existing agent, not a new spawn). The
message must instruct the implementation agent to re-read the
spec (`orchestrator/final.md`) and any files referenced in the
findings before applying them. The implementation agent's
context may have been compressed between Step 4 and Step 6, so
the findings payload alone is not sufficient.

The implementation agent addresses findings it judges
actionable and acknowledges findings it does not act on with a
reason. It re-runs CI locally.

Re-run Step 5: all four agents review the updated
implementation. `{prior_findings}` is scoped to the individual
agent's own section from `orchestrator/findings.md`, not the
full document. Each agent sees only its own prior findings.
Each writes a new verdict. The cycle repeats until all four
agents approve, capped at 2 review rounds. If blocking findings
remain after 2 rounds, surface them to the user.

## Step 7: Ship

Squash commits, write the commit message (Linear issue slug
prefix, summary of the fix), push the branch, and create the
PR using `gh pr create`.

After the PR is created, run `/fix-ci` until all checks pass.

@~/.claude/rules/meta-learning.md
