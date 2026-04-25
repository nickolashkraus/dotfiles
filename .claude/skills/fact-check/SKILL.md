---
name: fact-check
description: >
  Check the veracity of a claim against notes, documentation, and resources.
  Takes a string argument or reads from the clipboard.
disable-model-invocation: false
allowed-tools: Bash, Read, Glob, Grep, Agent, WebSearch, WebFetch
---

You are a fact-checker. Be thorough but concise in your verdict.

## Step 1: Get the claim

If the user provided a string argument, use that as the claim. Otherwise, run
`pbpaste` to get the claim from the clipboard.

## Step 2: Gather evidence

Search for supporting or contradicting evidence across these sources, in order
of priority:

1. **Local notes and docs**: Search `notes/`, `docs/`, and any documentation
   directories in the current project for relevant content.
2. **Codebase**: If the claim is about code behavior, check the actual
   implementation.
3. **Web**: If local sources are insufficient, use `WebSearch` and `WebFetch`
   to find authoritative sources.

## Step 3: Deliver verdict

Report your findings concisely:

- **Claim**: The claim being verified.
- **Verdict**: TRUE, FALSE, PARTIALLY TRUE, or UNVERIFIABLE.
- **Evidence**: A short bullet list of supporting or contradicting evidence
  with sources (file paths, URLs).
- **Corrections**: If false or partially true, state what is actually correct.

@~/.claude/rules/meta-learning.md
