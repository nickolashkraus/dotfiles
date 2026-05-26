# Swarm Shared Steps

Reusable command snippets and contracts for every swarm skill
(`/swarm-bug`, `/swarm-feature`, `/swarm-investigate`,
`/swarm-research`, `/swarm-verify`). Each swarm's `SKILL.md` may
restate skill-specific context (input parsing, agent roster, exit
criteria), but the snippets below are the canonical source for the
mechanics. Update them here, not in the skill bodies.

## Artifact worktree

Create a new agent-os worktree for the swarm's artifacts:

```bash
git -C ~/nickolashkraus/agent-os worktree add \
  ~/nickolashkraus/agent-os/{slug} -b {slug}
```

## Artifact directory formula

```
~/nickolashkraus/agent-os/{slug}/domains/{domain}/{projects|teams}/{name}/{bucket}/{slug}/
```

`{bucket}` is one of `bugs/`, `features/`, `investigations/`,
`verifications/`, `research/` per the skill (see "Artifacts Live in
agent-os" in PRINCIPLES.md).

## Parallel agent spawn

When spawning the per-role investigation agents in Step 2:

- All agents launch in a **single message** with multiple `Agent` tool
  uses, not sequentially.
- The agent prompt template lives at
  `~/.claude/skills/swarm-<name>/prompts/investigate/<role>.md`.
- Render the template by substituting `{repo_path}`, `{output_file}`,
  and any skill-specific variables.
- **Do not include other agents' findings in any agent's prompt.**
  Independent investigation is the whole point.
- The output file convention is
  `{artifact_dir}/<role>/investigation.md`.

## Convergence round

Use `~/.claude/skills/swarm-core/prompts/convergence.md`. Spawn all
agents again with file references to each other's findings (not the
content inline). Each agent appends under `## Convergence`. Write
`{artifact_dir}/orchestrator/checkpoint.md` after each round capturing
the round number and each agent's verdict. Repeat until all agents
report "complete," capped at 3 rounds.

## Synthesis review round

Use `~/.claude/skills/swarm-core/prompts/synthesis-review.md`. Spawn
the agents in parallel with `{own_findings_path}`, `{synthesis_path}`,
and `{output_file}` (= `{artifact_dir}/<role>/synthesis.md`). Loop
until all approve, capped at 3 rounds per version of synthesis (see
"Material-Rewrite Reset" in PRINCIPLES.md for when the cap resets).

## Typography pass

Run the typography pass from PRINCIPLES.md ("Typography Discipline")
against every artifact file authored in this run. Use
`grep -c '—'` and a smart-quote grep across the artifact tree to
confirm zero matches before advancing to verification or ship.

## Ship: artifact worktree

In the agent-os worktree, commit all artifacts on the worktree's
branch and push:

```bash
git -C ~/nickolashkraus/agent-os/{slug} add -A
git -C ~/nickolashkraus/agent-os/{slug} commit -m "swarm-<name>: {slug}"
git -C ~/nickolashkraus/agent-os/{slug} push -u origin {slug}
```

For Bug and Feature swarms, the code PR happens in the code worktree
(separate from the agent-os artifacts), per the skill body.

## Ship: deliver

Print the absolute path to `{artifact_dir}/orchestrator/final.md` so
the user can pipe it into any downstream skill (`/create-notion-page`,
`/update-linear-issue`, `/outbox`, etc.). For skills that auto-update
a Linear issue (investigate's `--linear` flag), invoke
`Skill(skill: "update-linear-issue", args: "<slug>")` after Ship.
