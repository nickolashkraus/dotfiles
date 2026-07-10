# Swarm Design Principles

These principles apply to every swarm skill (`$swarm-bug`, `$swarm-feature`,
`$swarm-investigate`, `$swarm-verify`, `$swarm-research`). Skill-specific
lessons live in each skill's own `PRINCIPLES.md`.

## Independence Before Synthesis

Agents investigate before reading each other's work. Anchoring on the first
analysis causes the swarm to converge prematurely. Wrong findings from
independent investigation are more valuable than correct findings derived from
another agent's work, because the synthesis step reconciles divergence into a
more complete model.

## Different Lenses, Not Redundant Work

Each agent has a distinct investigation approach. If all agents read the same
files and reached the same conclusion, the swarm would add latency without
value. The agent roster for each skill is chosen so that the lenses diverge:
source-code reading, runtime state, data lifecycle, history, design tradeoffs,
etc.

## The Output Is the Contract

Every swarm produces a final document. For Bug and Feature, that document is
the spec the implementation agent translates into code, and it must be detailed
enough that the implementation agent never needs to ask "what should this do?"
For Investigate, Verify, and Research, that document is the deliverable itself.
In both cases the synthesis must stand alone without the investigator's
context.

## Review Catches What Tests Cannot

Tests verify code correctness. Review catches structural issues: dependency
ordering across code paths, asymmetries between similar fallback mechanisms,
observability gaps in error handling, and inconsistencies between constants and
their usage. Multi-agent review with different lenses finds more issues than a
single reviewer.

## Consensus Through Iteration

Each phase that involves multiple agents loops until all agents explicitly
approve. Investigation loops until no agent has new findings. Synthesis loops
until all agents confirm the model is accurate. Review loops until all agents
report no blocking findings. Consensus is explicit: each agent writes a verdict
("approved" or "has concerns") and the Orchestrator only advances when all
verdicts are "approved." Cap at 3 rounds per phase to prevent unbounded
iteration. If consensus is not reached, the Orchestrator surfaces the remaining
disagreements to the user.

## Context Management

The Orchestrator runs the entire workflow. Without management, its context
grows unboundedly: raw findings from four agents, synthesis drafts, review
rounds, implementation diffs. Three strategies keep context viable:

1. **File references over inline content.** Convergence and review rounds pass
   file paths, not inline content. Subagents read files themselves. This caps
   the Orchestrator's outgoing prompt size regardless of how large the findings
   are, and lets subagents read selectively.
2. **Phase handoffs via files.** Each phase produces a file
   (`orchestrator/analysis.md`, `orchestrator/final.md`,
   `orchestrator/findings.md`). The next phase reads the file. The Orchestrator
   does not need prior phases in context once the output file is written.
3. **Checkpoints at phase boundaries.** The Orchestrator writes
   `orchestrator/checkpoint.md` at each phase transition: completed phases,
   decisions made, file locations, next steps. If compaction occurs, the
   Orchestrator re-reads the checkpoint to recover orchestration state.

Compaction is safe between phases. Within a phase (e.g., between convergence
rounds), the checkpoint file makes round state recoverable.

## Fact-Check Claims Before Shipping

Analyses make claims about system behavior ("the legacy checkout always creates
a new customer"). These claims must be verified against the actual code before
they enter the final document. An incorrect claim in the spec produces an
incorrect fix; an incorrect claim in a report misleads the reader.

## Artifacts Live in `agent-os`

Every swarm run creates a new worktree of the bare repo at
`~/nickolashkraus/agent-os` for its artifacts. The worktree branch name is the
slug derived from the input. Inside the worktree, artifacts live under
`domains/<domain>/<projects|teams>
/<name>/<bucket>/<slug>/`. The bucket is determined by skill:

| Skill                | Bucket            |
| -------------------- | ----------------- |
| `$swarm-bug`         | `bugs/`           |
| `$swarm-feature`     | `features/`       |
| `$swarm-investigate` | `investigations/` |
| `$swarm-verify`      | `verifications/`  |
| `$swarm-research`    | `research/`       |

Bug and Feature additionally create a code worktree in the target codebase for
implementation. Investigate, Verify, and Research are read-only on the codebase
and need no code worktree.
