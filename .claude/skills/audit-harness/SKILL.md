---
name: audit-harness
description: >
  Audit the Claude harness (dotfiles, agent-os, bash-scripts) for
  self-improvement. Reads recent daily compact logs, harness commits,
  memory, and the Claude Code changelog since the last audit; surfaces 2-5
  highest-value improvement candidates, including anything the platform
  now does that the harness reimplements. Run it locally; a cloud
  `/schedule` routine cannot read the local repos. TRIGGER when: user says
  "audit harness", "review the harness", "upgrade the harness", or this is
  the weekly scheduled run.
disable-model-invocation: false
allowed-tools: Agent, Bash, Read, Glob, Grep, Write
argument-hint: "[--days N]"
---

You are auditing the Claude Code harness for self-improvement
opportunities. The harness spans three repos, each a bare repo with
a `master` worktree:

- **dotfiles**: `~/nickolashkraus/dotfiles/master/.claude/` (rules,
  skills, hooks, settings; `~/.claude/` symlinks here)
- **agent-os**: `~/nickolashkraus/agent-os/master/.claude/` (project
  rules and skills)
- **bash-scripts**: `~/nickolashkraus/bash-scripts/master/` (shell
  helpers such as `claude-wip`, `system-update`, `fh-sync`)

The deliverable is a short Markdown report of 2-5 highest-value
candidates, ranked by impact-per-effort. Follow every step in order.

## Step 1: Parse arguments

Default look-back window is 7 days. If `$ARGUMENTS` contains
`--days N`, use that instead.

Compute the window cutoff date in ISO format (e.g., 2026-05-19 for
a 7-day window ending today).

## Step 2: Read recent activity

1. Daily compact logs from
   `~/nickolashkraus/agent-os/master/notes/logs/YYYY/MM/YYYY-MM-DD.md`
   for each date in the window. Skip dates with no log. Logs average
   about 350 lines, so do not truncate them. For a window over 7 days,
   split the dates into chunks of about 15 logs and give each chunk to
   a parallel subagent with the Step 3 pattern list. Each subagent
   returns candidate patterns with dated quotes, not log contents.

2. Commits in each repo since the cutoff:

   ```
   git -C ~/nickolashkraus/dotfiles/master log --since=<cutoff> \
     --pretty='%h %ad %s' --date=short -- .claude/
   git -C ~/nickolashkraus/agent-os/master log --since=<cutoff> \
     --pretty='%h %ad %s' --date=short -- .claude/
   git -C ~/nickolashkraus/bash-scripts/master log --since=<cutoff> \
     --pretty='%h %ad %s' --date=short
   ```

3. Memory indexes and entries modified in the window, for both the
   dotfiles and agent-os projects:

   ```
   ~/.claude/projects/-Users-nickolas-nickolashkraus-dotfiles/memory/
   ~/.claude/projects/-Users-nickolas-nickolashkraus-agent-os/memory/
   ```

4. The previous `harness-audit-*.md` report in the dotfiles memory
   directory, so candidates it already closed are not re-proposed.

5. The platform delta. The changelog lives at
   `~/.claude/cache/changelog.md`, newest first, one `## <version>`
   section per release, with no dates. The current version is
   `claude --version`. The baseline is the `Claude Code` line of the
   previous report; if it has none, take the last version published
   before the previous report's date:

   ```
   npm view @anthropic-ai/claude-code time --json
   ```

   Split the sections between the baseline and the current version into
   chunks of about 1,000 entries and give each chunk to a parallel
   subagent along with a listing of the three repos' skills, hooks,
   rules, and scripts. Each subagent returns only the entries that
   touch something the harness does, with the file it touches.

## Step 3: Pattern-spot

Read the collected inputs and look for these recurring patterns. Each
pattern is a candidate signal of a harness gap.

- **Manual recovery**: A skill was invoked but the user had to step in
  with an inline correction ("no, do X instead", "stop", "actually
  use Y"). The skill's instructions are insufficient.
- **Repeat fix**: The same kind of fix was committed across multiple
  sessions (e.g., "fix typography in PR body" three days in a row).
  Suggests a missing lint check or a stale rule.
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
- **Platform overlap**: A skill, hook, rule, script, or memory
  reimplements or works around something the platform now provides or
  has fixed. Replacing it with the native feature removes code that
  can drift. A stale workaround memory counts.

Ignore one-off noise. A friction pattern must show up at least twice
in the window to count. A platform overlap needs one changelog entry
and one harness file it makes redundant.

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
Claude Code: <baseline> to <current>.
Inputs scanned: <log-count> daily logs, <commit-count> commits
(dotfiles/agent-os/bash-scripts), <memory-count> memory entries,
<entry-count> changelog entries.

## Top candidates

### 1. <Short title> (impact: <high|medium|low>, effort: <minutes|hours|days>)

**Pattern**: <what you observed, with evidence: quote log lines, cite
commit SHAs, or name the changelog version>.

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
