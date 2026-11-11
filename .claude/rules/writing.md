# Writing

The style guide for blog posts, articles and essays (voice, structure,
openings, closings, code examples) lives in the `writing-style` skill. Invoke
it before drafting or editing long-form prose. The density rules below apply
to everything else.

## Density

The rubric is "informative but tight," not minimal. A reviewer or future
reader needs the *why* and the load-bearing context. Stripping the contract
from an ADR or the failure-mode bullets from a PR body loses real value.
"Less verbose" never means "strip everything."

- **PR bodies**: Scale with the diff, and err far shorter than feels
  natural. A one-line change gets one sentence: what it does, and why it
  matters if that is not obvious. No headers, no expected-plan paragraph,
  no restating edits the diff shows, and no `## References` block, since
  the Linear bot posts a linkback comment whenever the branch carries the
  slug. Reach for `## Overview` and `## Implementation Details` only when
  several substantive design points cannot be read off the diff; 25-50
  lines is the ceiling for a genuinely large change, never a target to
  fill. The failure mode is a template imposed on a small change: on
  sre-infra-terraform#1914, a one-line boolean flip, I wrote 40 lines, cut
  it to 12 when told it was too long, and Nickolas then cut it to the
  single sentence it should have been. Both of my attempts were wrong by
  an order of magnitude.
- **Code comments and docstrings**: Keep docstrings on non-trivial
  functions (2-4 lines: what it returns, non-obvious caveats). Keep ADR
  comments on files that genuinely embody an architectural decision
  (20-40 lines is fine; 90+ is not). Always keep the *why* on non-obvious
  decisions. Drop pure narration, restatements of signatures, section
  dividers, and ASCII-art tables.
- **Orchestration messages to agents**: Tight, but include the context the
  recipient needs to act. Reviews with concrete file or line references
  beat single-word acknowledgments when the agent needs to know what to do.
  Acknowledgments after a clean ping can be one word ("Acked.").

**One fact, one surface.** The Linear issue, the PR body, the commit
message and the docstring answer different questions, and no sentence
belongs to two of them:

- **Linear issue**: Why the work exists and what it has to do.
- **PR body**: What a reviewer of *this diff* needs that the diff does
  not show. Mostly the choices taken and the alternatives rejected.
- **Commit message**: The same, compressed, for someone reading `git log`.
- **Docstring**: What a caller has to know to use the thing correctly.

Never paste one into another. Duplication costs the reader two copies to
read and me an edit in every copy whenever one changes, and it is the
main way these surfaces get bloated. `hooks/lint-outbound.py` rejects a
PR body sharing a verbatim sentence with its Linear issue.

Investigation evidence (row counts, grant quantities, the names of
things found in a Dev database) belongs in the issue or in chat, not in
a PR body and never in a docstring.

**Calibration check**: if you're about to tell an agent "cut from N lines
to N/9 lines" or "make this one sentence," that's almost certainly an
overcorrection. The right ask is usually "cut N/3 lines" or "trim
subsection X to a paragraph."
