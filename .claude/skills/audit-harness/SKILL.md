---
name: audit-harness
description: >
  Audit the Claude harness for self-improvement. Reads recent daily compact
  logs, recent dotfiles commits, and memory; surfaces 2-5 highest-leverage
  improvement candidates. Designed for weekly `/schedule audit-harness` or
  ad-hoc invocation. TRIGGER when: user says "audit harness", "review the
  harness", or this is the weekly scheduled run.
disable-model-invocation: false
allowed-tools: Bash, Read, Glob, Grep, Write
argument-hint: "[--days N]"
---

You are auditing the Claude Code harness for self-improvement
opportunities. The deliverable is a short Markdown report of 2-5
highest-leverage candidates, ranked by impact-per-effort. Follow every
step in order.

## Step 1: Parse arguments

Default look-back window is 7 days. If `$ARGUMENTS` contains
`--days N`, use that instead.

Compute the window cutoff date in ISO format (e.g., 2026-05-19 for
a 7-day window ending today).

## Step 2: Read recent activity

Collect the following inputs into context. Cap each at ~100 lines via
`tail` or `head` to keep context lean.

1. Daily compact logs from
   `~/nickolashkraus/agent-os/master/notes/logs/YYYY/MM/YYYY-MM-DD.md`
   for each date in the window. Skip dates with no log.

2. Recent commits in `.claude/` of the dotfiles repo:

   ```
   git -C ~/nickolashkraus/dotfiles/master log --since=<cutoff> \
     --pretty='%h %ad %s' --date=short -- .claude/
   ```

3. Current memory index:

   ```
   ~/.claude/projects/-Users-nickolas-nickolashkraus-dotfiles/memory/MEMORY.md
   ```

4. Recent additions to the memory directory (files modified in the
   window):

   ```
   find ~/.claude/projects/-Users-nickolas-nickolashkraus-dotfiles/memory \
     -name '*.md' -newer <some-marker> | head -20
   ```

## Step 3: Pattern-spot

Read the collected inputs and look for these recurring patterns. Each
pattern is a candidate signal of a harness gap.

- **Manual recovery**: A skill was invoked but the user had to step in
  with an inline correction ("no, do X instead", "stop", "actually
  use Y"). The skill's instructions are insufficient.
- **Repeat fix**: The same kind of fix landed across multiple sessions
  (e.g., "fix typography in PR body" three days in a row). Suggests
  a missing lint check or a stale rule.
- **Tool errors**: An MCP or built-in tool call failed repeatedly with
  the same error. Suggests auth/config drift or a missing precondition
  the skill should set up.
- **Pre-commit / hook failures**: The pre-commit or `lint-outbound`
  hook fired on the same pattern repeatedly. Suggests a rule that
  should be promoted to a positive enforcement (auto-fix, template,
  or upstream change) rather than just a block.
- **Slow skills**: A skill took multiple rounds of agent calls that
  could have been one focused call. Suggests over-decomposition.
- **Untouched skills**: A skill has not been invoked in the window
  despite the kind of work it covers being done manually. Suggests
  weak discoverability (missing TRIGGER cue or wrong description).

Ignore one-off noise. A pattern must show up at least twice in the
window to count.

## Step 4: Rank candidates

For each candidate, estimate:

- **Impact**: How much time / how many sessions does fixing this save
  per week?
- **Effort**: How long would the fix take (minutes, hours, days)?
- **Risk**: What could the fix break?

Rank by impact-per-effort. Drop anything with high effort and unclear
impact.

Keep the top 2-5. Discard the rest.

## Step 5: Write the report

Write the report to:

```
~/.claude/projects/-Users-nickolas-nickolashkraus-dotfiles/memory/harness-audit-YYYY-MM-DD.md
```

Use this structure:

```markdown
---
name: harness-audit-YYYY-MM-DD
description: >
  Audit of the Claude harness for the week ending YYYY-MM-DD. Top
  candidates ranked by impact-per-effort.
metadata:
  node_type: memory
  type: project
---

# Harness Audit: YYYY-MM-DD

Window: <cutoff> to <today> (N days).
Inputs scanned: <log-count> daily logs, <commit-count> commits,
<memory-count> memory entries.

## Top candidates

### 1. <Short title> (impact: <high|medium|low>, effort: <minutes|hours|days>)

**Pattern**: <what you observed, with evidence — quote log lines or
cite commit SHAs>.

**Why it matters**: <the cost of not fixing>.

**Proposed fix**: <concrete change to a file / hook / skill / rule>.

### 2. ...

## Patterns observed but not actionable

Brief mention of patterns that surfaced but were ruled out (low
impact, unclear root cause, requires upstream change). One line each.

## No-ops

What looked like a pattern but was actually fine on closer look. One
line each.
```

Use folded YAML `>` for the report's frontmatter description (per
the standard in
`memory/skill_description_yaml_format.md`).

## Step 6: Report

Print the absolute path to the report. Print the top 1-2 candidates
inline so the user can act without opening the file.

If no actionable patterns surfaced, write a one-line "clean" report
and say so. Do not invent candidates to fill the quota.
