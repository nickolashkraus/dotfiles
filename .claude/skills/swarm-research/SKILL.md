---
name: swarm-research
description: >
  Multi-agent swarm for deep-dive analysis on a topic, system, or proposed
  direction. Produces a long-form research document; no implementation phase.
  TRIGGER when: open-ended research question requiring history + architecture +
  tradeoffs synthesis, "deep dive on X", "what should we do about Y". SKIP:
  looking up a specific fact (use `fact-check`).
disable-model-invocation: false
allowed-tools: Agent, Bash, Edit, Glob, Grep, Read, SendMessage, Skill, WebFetch, Write, mcp__linear__get_issue, mcp__notion__notion-fetch
argument-hint: "<topic-or-file>"
---

You are the Orchestrator in a 5-agent swarm for deep-dive
research. The deliverable is a long-form analysis document that
captures the current state of a system, the history of how it
got there, the design tradeoffs, and recommended directions.
Follow every step in order.

Shared design principles, mechanics, and snippets:

@~/.claude/skills/swarm-core/PRINCIPLES.md

@~/.claude/skills/swarm-core/STEPS.md

## Agents

| Agent        | Description                                                                                       |
| ------------ | ------------------------------------------------------------------------------------------------- |
| Orchestrator | Orchestrates phases, synthesizes findings, fact-checks claims, ships the research document      |
| Implementer  | Maps the current code: what exists, how it composes, what the surfaces and contracts look like  |
| Historian    | Reads git history, prior docs, RFCs, and migrations to reconstruct how the system got here       |
| Architect    | Surveys design alternatives, related patterns elsewhere, and tradeoffs the current shape implies |
| Synthesizer  | Tracks open questions and convergence: what is settled, what is contested, what is unknown      |

## Abort Heuristic

If the topic is narrow enough that a single agent can answer it
in 15 minutes (e.g., "what does function X do?"), abort the
swarm and answer directly.

## Step 1: Intake

Parse `$ARGUMENTS` for the research topic. The topic is either
a file path or inline text. If it is a URL, fetch its contents.
If it is a file path, read it. If it is inline text, use it
directly.

Derive `{slug}` (kebab-case): a short summary of the topic
("bundle-coupons", "pubsub-vs-streams").

Derive `{domain}` and `{project_or_team}` from the topic. If
the research is cross-cutting, pick the team or project most
likely to act on it.

Set `{repo_path}` to the current working directory if a single
codebase anchors the research.

Create a new agent-os worktree for artifacts:

```bash
git -C ~/nickolashkraus/agent-os worktree add \
  ~/nickolashkraus/agent-os/{slug} -b {slug}
```

Set `{artifact_dir}` to:

```
~/nickolashkraus/agent-os/{slug}/domains/{domain}/{projects|teams}/{name}/research/{slug}/
```

Create the artifact subdirectories:

```
{artifact_dir}/
  orchestrator/
    analysis.md
  implementer/
  historian/
  architect/
  synthesizer/
```

Copy `~/.claude/skills/swarm-research/ANALYSIS.md` to
`{artifact_dir}/orchestrator/analysis.md`. Fill in
`{research_title}`, `## Topic`, `## Scope`, and `## Questions`.
Decompose the topic into a numbered list of specific research
questions. Vague topics ("how does our payment system work?")
become specific questions ("how are subscription state
transitions modeled?", "what happens when a webhook arrives
out of order?", "how does the idempotency layer work?"). The
question list shapes every agent's investigation.

**User gate**: Present the question list to the user. Ask:
"Approve these questions, or adjust the decomposition?" Do not
spawn the parallel investigators until the user approves. The
question list shapes 4 parallel agents plus a convergence round
(8 agent calls minimum), so getting it right before spending the
budget is cheap.

## Step 2: Investigate (parallel)

Spawn four subagents using the Agent tool. All four must launch
in a single message (parallel, not sequential).

For each agent (implementer, historian, architect, synthesizer):

1. Read the prompt template from
   `~/.claude/skills/swarm-research/prompts/investigate/{agent}.md`.
2. Substitute `{topic}`, `{questions}`, `{repo_path}`, and
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
corresponding `### Implementer`, `### Historian`,
`### Architect`, `### Synthesizer` sections.

## Step 3: Synthesize

Read the full analysis document and write the long-form
synthesis under `## Agent Synthesis`. Unlike Bug or Feature,
the synthesis here IS the deliverable, so write it as a
document the user would actually read end-to-end, not as a
fix plan.

The synthesis should include:

- **Executive summary** (at the top of the file, before any other
  section): ~20-30 lines. Current state in 2-3 sentences, the
  most consequential tradeoffs, numbered recommendations with one
  sentence each, what is settled vs. contested, and current
  approval status. This is what the user reads when the full
  document is too long to skim, and what gets cited or excerpted
  when sharing the research with others.
- **Current state**: What exists today, written so a reader
  unfamiliar with the system can follow.
- **History**: How the system got to its current shape, with
  inflection points and the reasons behind them.
- **Tradeoffs**: The choices baked into the current design,
  what they buy, and what they cost.
- **Alternatives considered**: Patterns elsewhere or earlier
  proposals, with comparison to the current shape.
- **Open questions**: What is settled, what is still contested
  among stakeholders, and what is genuinely unknown.
- **Recommendations**: Concrete directions the user could
  pursue, ordered by leverage. Each recommendation has a
  scope, a rationale, and a rough cost/benefit framing.

Use `~/.claude/skills/swarm-core/prompts/synthesis-review.md`.
Spawn the four agents in parallel. Substitute
`{own_findings_path}`, `{synthesis_path}`, and `{output_file}`
(= `{artifact_dir}/{agent}/synthesis.md`).

Read all four verdicts. If any agent has concerns, address them
and re-submit. Loop until all four approve, capped at 3 rounds.

Write the final document to
`{artifact_dir}/orchestrator/final.md`.

**Fact-check gate**: Verify factual claims about the current
system against the codebase, and historical claims against
git history or the cited primary source. Note unverified
claims explicitly.

**Typography pass**: Run the typography pass from
`~/.claude/skills/swarm-core/PRINCIPLES.md` ("Typography Discipline")
against every artifact file authored in this run.

**User gate**: Present the final document to the user. Ask:
"Approve the research, or do you want to adjust the synthesis
or recommendations?" Do not proceed until the user approves.

## Step 4: Ship

In the **agent-os worktree**: commit all artifacts on the
`{slug}` branch with message `"swarm-research: {slug}"` and
push.

If the user wants the document in Notion, run
`/create-notion-page` against `final.md`. If a Linear issue
should track follow-up, suggest creating one with
`/create-linear-issue`.
