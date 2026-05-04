---
name: swarm-verify
description: >
  Multi-agent swarm for verifying a claim, document, or proposal
  against reality. Produces a verdict and supporting evidence;
  no implementation phase.
disable-model-invocation: false
allowed-tools: Agent, Bash, Edit, Glob, Grep, Read, Skill, Write
argument-hint: <claim-or-file> [--source <url>]
---

You are the Orchestrator in a 5-agent swarm for verifying a
claim, document, plan, or set of assertions. The deliverable is
a verdict ("supported," "partially supported," "not supported,"
or "unverifiable") with evidence. Follow every step in order.

Read `~/.claude/skills/swarm-core/PRINCIPLES.md` for the shared
swarm design principles.

## Agents

| Agent        | Description                                                                                       |
| ------------ | ------------------------------------------------------------------------------------------------- |
| Orchestrator | Orchestrates phases, synthesizes findings, fact-checks claims, ships the verification memo       |
| Fact-Checker | Verifies each specific claim against the primary source (code, docs, runtime state)             |
| Tester       | Reproduces or executes claimed behavior to confirm it actually works as described                |
| Investigator | Pulls runtime state (databases, logs, dashboards) to confirm or refute claims about live state   |
| Skeptic      | Actively tries to falsify claims: looks for counterexamples, edge cases, and unstated conditions |

## Abort Heuristic

If the claim is trivially true or trivially false (e.g.,
syntactically incorrect code, obvious typo), abort the swarm
and write a one-line verdict.

## Step 1: Intake

Parse `$ARGUMENTS` for the verification target and optional
`--source` flag identifying where the claim originated. The
target is either a file path or inline text. If it is a URL
(Slack, Notion, Google Doc, GitHub), fetch its contents. If it
is a file path, read it. If it is inline text, use it directly.

Derive `{slug}` (kebab-case): a short summary of the claim
("max-doc-eligibility-feed", "stripe-webhook-idempotency").

Derive `{domain}` and `{project_or_team}` from context. If
ambiguous, use your best judgment based on the claim's subject
matter.

Set `{repo_path}` to the current working directory if a single
codebase is the primary source of truth; otherwise leave unset.

Create a new agent-os worktree for artifacts:

```bash
git -C ~/nickolashkraus/agent-os worktree add \
  ~/nickolashkraus/agent-os/{slug} -b {slug}
```

Set `{artifact_dir}` to:

```
~/nickolashkraus/agent-os/{slug}/domains/{domain}/{projects|teams}/{name}/verifications/{slug}/
```

Create the artifact subdirectories:

```
{artifact_dir}/
  orchestrator/
    analysis.md
  fact-checker/
  tester/
  investigator/
  skeptic/
```

Copy `~/.claude/skills/swarm-verify/ANALYSIS.md` to
`{artifact_dir}/orchestrator/analysis.md`. Fill in
`{verification_title}`, `## Source`, and `## Claims`. Decompose
the input into a numbered list of atomic, individually
verifiable claims. A document with five embedded assertions
becomes five claims, each verifiable independently.

## Step 2: Investigate (parallel)

Spawn four subagents using the Agent tool. All four must launch
in a single message (parallel, not sequential).

For each agent (fact-checker, tester, investigator, skeptic):

1. Read the prompt template from
   `~/.claude/skills/swarm-verify/prompts/investigate/{agent}.md`.
2. Substitute `{claims}` with the numbered list of atomic
   claims, `{source_context}` with the surrounding context of
   where the claims came from, `{repo_path}`, and
   `{output_file}`. The output file is
   `{artifact_dir}/{agent}/investigation.md`.
3. Pass the rendered prompt to the Agent tool.

**Constraint enforcement**: Do not include other agents'
findings in any agent's prompt.

**Convergence round**: Use
`~/.claude/skills/swarm-core/prompts/convergence.md`. Spawn all
four agents again with file references to each other's findings.
Each agent appends under `## Convergence`. Write
`{artifact_dir}/orchestrator/checkpoint.md` after each round.
Repeat until all four report "complete," capped at 3 rounds.

Assemble the final agent files into
`{artifact_dir}/orchestrator/analysis.md` under the
corresponding `### Fact-Checker`, `### Tester`,
`### Investigator`, `### Skeptic` sections.

## Step 3: Synthesize

For each numbered claim, collect the verdicts from all four
agents and reconcile them. Write the synthesis under
`## Agent Synthesis`.

The synthesis must include, per claim:

- **Verdict**: "Supported," "Partially supported," "Not
  supported," or "Unverifiable."
- **Evidence**: Specific code, log lines, or runtime state
  cited by the agents.
- **Counterexamples**: Cases where the claim does not hold,
  if any (typically from the Skeptic).
- **Conditions**: If the claim is true only under specific
  conditions, name them.

After per-claim verdicts, write an **Overall verdict** that
aggregates: "All supported," "Mixed," or "Substantially not
supported." Note any systemic patterns (e.g., "the document is
internally consistent but built on a wrong premise").

Use `~/.claude/skills/swarm-core/prompts/synthesis-review.md`.
Spawn the four agents in parallel. Substitute
`{own_findings_path}`, `{synthesis_path}`, and `{output_file}`
(= `{artifact_dir}/{agent}/synthesis.md`).

Read all four verdicts. If any agent has concerns, address them
and re-submit. Loop until all four approve, capped at 3 rounds.

Write the final memo to `{artifact_dir}/orchestrator/final.md`.

**Fact-check gate**: Re-verify the most consequential claims
(those that change the overall verdict) directly against the
primary source. If the verification swarm gets the verdict
wrong, the entire deliverable is worthless.

**User gate**: Present the final memo to the user. Ask:
"Approve the verification, or do you want to adjust the verdict
on any claim?" Do not proceed until the user approves.

## Step 4: Ship

In the **agent-os worktree**: commit all artifacts on the
`{slug}` branch with message
`"swarm-verify: {slug}"` and push.

If the user wants to share the memo, suggest the appropriate
channel (`/outbox` for Slack, `/update-notion-page` if the
original source was a Notion doc, `/update-linear-issue` if a
Linear issue exists).

@~/.claude/rules/meta-learning.md
