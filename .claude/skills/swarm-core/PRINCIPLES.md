# Swarm Design Principles

These principles apply to every swarm skill (`/swarm-bug`, `/swarm-feature`,
`/swarm-investigate`, `/swarm-verify`, `/swarm-research`). Skill-specific
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

Every final document must open with a `## Executive Summary` section (~20-30
lines, before any other content) that a human can read in under a minute. The
summary captures the core finding, the proposed actions or verdicts, and the
current approval status. Full agent analyses and synthesis details follow below
for reviewers and implementation agents. The summary is what the user reads
when the full document is too long to skim, and it stays with the artifact
across sessions.

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

## Material-Rewrite Reset

If the load-bearing section of a synthesis is materially rewritten between
rounds (in `/swarm-bug` and `/swarm-investigate` the root-cause section; in
`/swarm-feature` the design or approach; in `/swarm-research` the
recommendations or tradeoff table; in `/swarm-verify` the verdict), prior
approvals from the unchanged-context agents are void. Restart the review loop
from round 1 against the new synthesis. The 3-round cap applies
per-version-of-synthesis, not globally. Without this rule, a late pivot
consumes the round budget on approvals that were given against a now-stale
document.

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

## Typography Discipline

Every artifact file you author (orchestrator outputs like `analysis.md`,
`checkpoint.md`, `final.md`, `verification.md`, and agent outputs like
`investigation.md`, `synthesis.md`) is subject to
`@~/.claude/rules/typography.md`. No em dashes, no smart quotes, lines wrapped
at <80 characters except for tables, bullet items use
`**Element**: Description` lead-in (never ` - ` or ` — ` as separator), and
periods only on full-sentence bullets. Tables are exempt from line-length but
must be evenly padded.

Apply this pass before any verification or final-delivery step. The
Orchestrator writes prose-heavy synthesis sections and is the most common
source of em-dash violations; run `grep -c '—'` across all artifact files to
confirm zero before advancing.

## Artifacts Live in `agent-os`

Every swarm run creates a new worktree of the bare repo at
`~/nickolashkraus/agent-os` for its artifacts. The worktree branch name is the
slug derived from the input. Inside the worktree, artifacts live under
`domains/<domain>/<projects|teams>
/<name>/<bucket>/<slug>/`. The bucket is determined by skill:

| Skill                | Bucket            |
| -------------------- | ----------------- |
| `/swarm-bug`         | `bugs/`           |
| `/swarm-feature`     | `features/`       |
| `/swarm-investigate` | `investigations/` |
| `/swarm-verify`      | `verifications/`  |
| `/swarm-research`    | `research/`       |

Bug and Feature additionally create a code worktree in the target codebase for
implementation. Investigate, Verify, and Research are read-only on the codebase
and need no code worktree.
