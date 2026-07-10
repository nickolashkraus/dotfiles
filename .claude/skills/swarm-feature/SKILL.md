---
name: swarm-feature
description: >
  Multi-agent swarm for designing and implementing new features. Independent
  parallel investigation, structured synthesis, implementation in a code
  worktree, and multi-agent review. TRIGGER when: building a non-trivial
  feature that requires design exploration across the codebase. SKIP:
  small/local change (just implement it).
disable-model-invocation: false
allowed-tools: Agent, Bash, Edit, Glob, Grep, Read, SendMessage, Skill, WebFetch, Write, mcp__linear__get_issue, mcp__notion__notion-fetch
argument-hint: "<feature-spec> [--linear <issue-slug>]"
---

You are the Orchestrator in a 5-agent swarm for shipping new features. Follow
every step in order.

Shared design principles, mechanics, and snippets:

@~/.claude/skills/swarm-core/PRINCIPLES.md

@~/.claude/skills/swarm-core/STEPS.md

## Agents

| Agent        | Description                                                                                          |
| ------------ | ---------------------------------------------------------------------------------------------------- |
| Orchestrator | Orchestrates phases, synthesizes findings across agents, fact-checks claims, ships deliverables      |
| Architect    | Reviews system design, integration points, alternative approaches, and tradeoffs                     |
| Implementer  | Reads existing code patterns, identifies the right APIs, and proposes the implementation shape       |
| Tester       | Defines acceptance criteria, edge cases, and the test strategy                                       |
| Tracker      | Designs data flow: schema changes, migrations, event publishing, and integration with other services |

## Abort Heuristic

If the feature is small enough to implement directly within ~30 minutes (e.g.,
a single-file change with obvious tests), abort the swarm and write it
directly.

## Step 1: Intake

Parse `$ARGUMENTS` for the feature spec and optional `--linear` flag. The spec
is either a file path or inline text. If it is a URL (Linear, Notion), fetch
its contents. If it is a file path, read it. If it is inline text, use it
directly.

Derive `{slug}` (kebab-case): the Linear issue slug if provided, otherwise a
kebab-case summary of the feature.

Derive `{domain}` and `{project_or_team}` from the codebase repo path. If
ambiguous, ask the user.

Set `{repo_path}` to the current working directory.

Create a new agent-os worktree for artifacts:

```bash
git -C ~/nickolashkraus/agent-os worktree add \
  ~/nickolashkraus/agent-os/{slug} -b {slug}
```

Set `{artifact_dir}` to:

```
~/nickolashkraus/agent-os/{slug}/domains/{domain}/{projects|teams}/{name}/features/{slug}/
```

Create the artifact subdirectories:

```
{artifact_dir}/
  orchestrator/
    analysis.md
  architect/
  implementer/
  tester/
  tracker/
```

Copy `~/.claude/skills/swarm-feature/ANALYSIS.md` to
`{artifact_dir}/orchestrator/analysis.md`. Fill in `{feature_title}`,
`## Goal`, `## User Story`, `## Out of Scope`, and any acceptance criteria
already known from the spec.

## Step 2: Investigate (parallel)

Spawn four subagents using the Agent tool. All four must launch in a single
message (parallel, not sequential).

For each agent (architect, implementer, tester, tracker):

1. Read the prompt template from
   `~/.claude/skills/swarm-feature/prompts/investigate/{agent}.md`.
2. Substitute `{feature_spec}`, `{repo_path}`, and `{output_file}` with the
   values from Step 1. The output file is
   `{artifact_dir}/{agent}/investigation.md`.
3. Pass the rendered prompt to the Agent tool.

**Constraint enforcement**: Do not include other agents' findings in any
agent's prompt. Each agent sees only the feature spec.

When all four agents complete, read each agent's `investigation.md`.

**Convergence round**: Use
`~/.claude/skills/swarm-core/prompts/convergence.md`. Spawn all four agents
again. Substitute `{own_findings_path}`, `{other_findings_paths}`, and
`{output_file}` (= the agent's `investigation.md`). Each agent appends under a
`## Convergence` section. Write `{artifact_dir}/orchestrator/checkpoint.md`
after each round. Repeat until all four report "complete," capped at 3 rounds.

Assemble the final agent files into `{artifact_dir}/orchestrator/analysis.md`
under the corresponding `### Architect`, `### Implementer`, etc. sections.

## Step 3: Synthesize

Read the full analysis document and write the initial synthesis under
`## Agent Synthesis`.

The synthesis must include:

- **Executive summary** (at the top of the file, before any other section):
  ~20-30 lines. The feature's purpose in 2-3 sentences, numbered work items
  with one sentence each, key acceptance criteria, and current approval status.
  This is what the user reads when the full document is too long to skim.
- **Design**: One paragraph describing the chosen approach and why it was
  preferred over alternatives raised by Architect.
- **Implementation plan**: Numbered list of work items, each with scope, files
  changed, and rationale.
- **Data flow**: Schema changes, migrations, event publishing, and
  inter-service touchpoints (from Tracker's findings).
- **Acceptance criteria**: Concrete, testable conditions (from Tester's
  findings).
- **Dependency ordering**: Explicit statement of which work items must complete
  before others (e.g., schema migration before code that reads new columns).
- **Out of scope**: What this feature explicitly does not do.

Use `~/.claude/skills/swarm-core/prompts/synthesis-review.md`. Spawn the four
agents again (parallel). For each, substitute `{own_findings_path}` (= agent's
`investigation.md`), `{synthesis_path}` (=
`{artifact_dir}/orchestrator/analysis.md`), and `{output_file}` (=
`{artifact_dir}/{agent}/synthesis.md`).

Read all four verdicts. If any agent has concerns, address the objections,
update the synthesis, and re-submit. Loop until all four approve, capped at 3
rounds. If consensus is not reached, surface the disagreements to the user.

Write the final analysis to `{artifact_dir}/orchestrator/final.md`.

**Fact-check gate**: Verify every factual claim about existing code, schemas,
or APIs against the codebase. Correct any wrong claim and note the correction.

**Typography pass**: Run the typography pass from
`~/.claude/skills/swarm-core/PRINCIPLES.md` ("Typography Discipline") against
every artifact file authored in this run.

**User gate**: Present the final analysis to the user. Ask: "Ready to
implement, or do you want to adjust the design?" Do not proceed until the user
approves.

**Linear issue**: If no `--linear` flag was provided, create a Linear issue
from `{artifact_dir}/orchestrator/final.md` using `/create-linear-issue`. Use
the returned issue slug for the branch name in Step 4.

## Step 4: Implement

Create a Git worktree in the **codebase repo** (not agent-os) for the Linear
issue (or derived branch name). Spawn a single implementation agent in the code
worktree with:

- The final analysis document (full text, inline).
- The code worktree path.
- Instructions to implement each work item in dependency order.
- Instructions to write tests for every acceptance criterion.
- Instructions to run the project's full CI locally before reporting
  completion.

The implementation agent works independently. If the spec is ambiguous, it
should make a judgment call and document the decision in a code comment, not
stop and ask.

When the implementation agent completes, read the diff to verify all work items
are present and the acceptance criteria are covered by tests.

## Step 5: Review (parallel)

Before spawning reviewers, commit the implementation
(`git add -A && git commit`) so reviewers run against a fixed commit SHA, not
the working tree.

For each agent (architect, implementer, tester, tracker):

1. Read the review prompt from
   `~/.claude/skills/swarm-feature/prompts/review/{agent}.md`.
2. Substitute `{final_analysis}` with the content of
   `{artifact_dir}/orchestrator/final.md`, `{diff}` with the output of
   `git diff <default-branch>...<commit-sha>`, `{prior_analysis}` with the
   agent's `investigation.md`, `{prior_findings}` with empty string (first
   round), and `{output_file}` with `{artifact_dir}/{agent}/review.md`.
3. Pass the rendered prompt to the Agent tool.

Spawn all four in a single message (parallel).

Read all four review files. Assemble `{artifact_dir}/orchestrator/findings.md`
with per-agent sections. Each agent writes a verdict: "approved," "approved
with observations," or "has blocking findings."

If all four agents approve, skip to Step 7.

## Step 6: Apply findings

Send `{artifact_dir}/orchestrator/findings.md` to the implementation agent (via
SendMessage). Instruct it to re-read the spec
(`{artifact_dir}/orchestrator/final.md`) and any referenced files before
applying the findings.

The implementation agent addresses findings it judges actionable and
acknowledges findings it does not act on with a reason. It re-runs CI locally.

Re-run Step 5 with `{prior_findings}` scoped to each agent's own section. Each
agent writes a new verdict. Cap at 2 review rounds. If blocking findings
remain, surface them to the user.

## Step 7: Ship

In the **code worktree**: squash commits, write the commit message (Linear
issue slug prefix, summary of the feature), push the branch, and create the PR
using `gh pr create`.

In the **agent-os worktree**: commit all artifacts on the `{slug}` branch with
message `"swarm-feature: {slug} design"` and push the branch.

After the code PR is created, run `/fix-ci` until all checks pass.
