---
name: write-trd
description: >
  Generates a Technical Requirements Document through structured
  interviews and codebase analysis.
disable-model-invocation: false
allowed-tools: Agent, Bash, Glob, Grep, Read, Write
argument-hint: [feature-name]
---

You are writing a TRD. Follow every step in order.

## Step 1: Gather context

Ask the user once:

> Do you have supporting materials? (PRD, meeting notes, Slack
> threads, design docs, prior art.) Paste them or share file paths.
> Type "none" to skip.

If materials are provided, read them in full. Extract goals,
constraints, decisions already made, named integrations, timeline
hints, and open questions. Carry this forward and do not re-ask
anything the materials already answer.

## Step 2: Interview

Ask all unanswered questions in a single message. Skip any that
the supporting materials already answer.

```
1.  Project/feature name?
2.  Author(s) and roles?
3.  Related PRD link? ("none" if N/A)
4.  Linear epic link? ("none" if N/A)
5.  Figma link? ("none" if N/A)
6.  Review deadline? (YYYY-MM-DD or "TBD")
7.  Problem statement: what technical problem are we solving?
    (3-5 sentences)
8.  Why now? What changed, or what happens if we don't do this?
9.  What is in scope? (bullet list of systems/components)
10. What is out of scope? (explicit exclusions)
11. Mobile app changes? (yes/no/unsure)
12. Security or compliance requirements? (yes/no/unsure)
```

## Step 3: Explore the codebase

After the interview, explore the codebase. Do not ask the user for
information you can infer from code. Extract:

- Services and entry points (REST endpoints, PubSub
  topics/subscriptions).
- Data models and database schema relevant to the feature.
- Existing state machines or workflow definitions.
- External integrations (Stripe, Shopify, Fullscript, etc.).
- Feature flag patterns (Statsig gates/configs).
- Error handling and retry patterns.

Use this to pre-populate the architecture, data model, API design,
and observability sections.

## Step 4: Fill gaps

After exploring the code, ask remaining questions in a single
message. Skip any you can answer from code or prior context.

```
13. Proposed high-level approach? ("infer from code" if obvious)
14. Key design decisions or trade-offs to document?
15. Alternatives considered and rejected? ("none" if N/A)
16. New infrastructure needed? (Cloud Functions, queues, new
    DBs, etc.)
17. Feature flags planned? (Statsig gate names, or "none")
18. Team composition? (e.g., "2 BE, 1 Web, 1 Mobile")
19. Target sprint start date or rough timeline?
20. Key success metrics?
21. Open questions or unresolved decisions?
```

## Step 5: Write the TRD

Populate the template in TEMPLATE.md top to bottom. Follow these
rules:

- Follow @rules/typography.md and @rules/writing.md for all
  prose.
- Infer from code wherever possible rather than leaving
  placeholders.
- For unavoidable gaps, use `[TBD: what is needed]`.
- If mobile changes were confirmed, add a mobile consultation
  checklist item and document OTA/version strategy.
- If security/compliance was confirmed, fully populate the
  Security and Compliance section.
- Generate Mermaid diagrams for: (1) high-level architecture
  (flowchart), (2) primary happy-path sequence, (3) key
  error/retry flow if non-trivial.
- The risk table must have at least 3 rows based on integration
  points found in the code.
- The Review and Approval and Post-Implementation Review sections
  are stubs. Do not fill them.
- Save the document as
  `TRD-<kebab-feature-name>-<YYYY-MM-DD>.md` in the project root
  unless the user specifies a different location.

## Step 6: Verify

Before delivering, confirm:

- All sections present (stubs are fine for Review and
  Post-Implementation).
- No empty placeholder brackets. Every gap uses
  `[TBD: reason]`.
- At least one architecture diagram and one sequence diagram.
- Risk table has 3+ rows with mitigation strategies.
- In scope and out of scope explicitly stated.
- Output filename follows the naming convention.

@~/.claude/rules/meta-learning.md
