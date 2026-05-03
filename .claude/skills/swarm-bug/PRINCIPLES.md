# Bug Swarm Principles

For shared swarm principles (independence, consensus, context
management, fact-checking, artifact location), read
`~/.claude/skills/swarm-core/PRINCIPLES.md`. The lessons below
are specific to the bug-fix workflow.

## Lessons from BYB-1345

The following lessons from the first swarm run inform the
automation design:

1. **Independence produces divergence, which produces
   completeness.** Tracker was wrong about the specific failure
   chain for the reported member. But the mechanism Tracker
   identified (stale canceled subscription IDs from migrations)
   was real, just not the trigger for this specific member.
   The synthesis incorporated both mechanisms, producing a more
   complete fix than either analysis alone.

2. **The synthesis phase is the bottleneck.** Four independent
   analyses produce overlapping findings with different
   framings. Reconciling them requires understanding how the
   failure modes interact, not just listing them. The
   Orchestrator must do this work; it cannot be parallelized.

3. **Fact-checking changes the fix plan.** The claim that
   "legacy checkouts always create a new Stripe customer" was
   wrong. Verifying it against the actual code changed the
   scope of Layer 3. The automation must include an explicit
   fact-check step, not assume agent analyses are correct.

4. **Review agents must not know implementation intent.** The
   implementation agent made a conscious choice to use
   `stripe.Subscription.list_async` directly (copying the
   existing pattern). Tracker, not knowing this intent, flagged
   it as an observability gap. The intent was wrong; the review
   was right. If the review agent had seen the implementation
   agent's reasoning, it might have accepted the choice.

5. **The spec must be unambiguous enough to implement without
   questions.** The implementation agent never had to ask "what
   should this do?" because the spec answered it. This is the
   test: if the implementation agent asks a clarifying
   question, the spec failed.

6. **One round of review findings is sufficient when the spec
   is good.** All four of Tracker's findings were edge-case
   tightening, not architectural issues. None required
   rethinking the approach. This suggests the spec was correct
   and the review phase's role is polishing, not redesigning.

7. **Local CI must match remote CI exactly.** The
   implementation agent ran `ruff check` and `pyright` but not
   `ruff format`. The shipping phase caught this. The
   implementation agent prompt should explicitly list every CI
   command to run.

8. **The user gate after synthesis is essential.** The user
   might have context the agents do not (e.g., "we are already
   planning to deprecate that code path, do not fix it"). The
   automation must pause for approval before implementing.

9. **Review agents must verify whether prior findings were
   addressed.** Investigator reviewed the updated code and
   wrote corrections to Tracker's findings, not realizing the
   implementation had already addressed them. The corrections
   were themselves wrong in context. The review prompt must
   instruct agents to treat the findings document as a
   historical record: note which findings are resolved, do not
   "correct" observations from a prior review round.

10. **Dependency ordering is a structural property, not a
    line-by-line property.** The most useful Investigator
    review finding (Layer 3 must precede Layer 4 in all
    checkout paths) required tracing the call graph across
    three functions. Each path handled the ordering differently
    (explicit sequencing in `create_checkout`, implicit via
    branch structure in `_execute_stripe_payment`, resolver-
    first in `ts_actions`). A diff review cannot catch this.
    The Investigator review prompt should explicitly require
    full-file reads, not just diff review.

11. **Database investigation surfaces what code analysis
    cannot.** Investigator's most valuable Phase 2 contribution
    (the customer ID staleness cycle) emerged from querying
    the Dev database, not from reading code. The staleness
    cycle is a feedback loop between
    `get_customer_by_patient_id` (filters `disabled=False`),
    customer creation, and webhook handlers. Each function is
    correct in isolation. The bug is in the interaction, which
    only shows up in the data.

---

# Tracker Perspective

## What the Role Contributes

The Tracker role sits between Implementer and Investigator.
Implementer reads functions. Investigator reads the database.
Tracker reads the data lifecycle: how a field got its value,
what was supposed to update it, and why the update failed. This
is the role that asks "where did this NULL come from?" and
traces it back through a migration backfill, a webhook
handler's fallback chain, and a mapping table.

The role's primary contribution is separating failure modes that
look like one problem from the outside. A symptom like
"duplicate records" can have multiple independent causes: a
filter that is too narrow, a product ID mismatch between two
systems, a backfill that populated stale data. Code-level
analysis tends to find the first decision point and stop.
Tracker traces each data input separately and identifies which
failure modes compound and which are independent. This changes
the fix plan, because a fix that addresses one mode (widening a
filter) may do nothing for another (a product mismatch between
systems that were never designed to interoperate).

The second contribution is verifying claims made by other
agents. When an agent proposes a fix that depends on a specific
field being present (e.g., metadata on an external record),
Tracker traces the code path that creates that record and checks
whether the field actually exists. Claims about data flow are
easy to assert and easy to get wrong. Verifying them against
the creation path, not the consumption path, is what prevents
the fix from being built on a false assumption.

## What the Role Needs

The Tracker investigation prompt works well as written. Two
additions would make it more effective:

1. **Access to external APIs (read-only).** Tracing data flows
   requires seeing both ends: the internal database state and
   the external system state. The investigation prompt should
   explicitly authorize read-only API calls to external systems
   when reproduction data includes resource IDs.

2. **Migration history.** The Tracker role traces how data
   entered the system. Migrations are a primary source of
   initial state. The investigation prompt should direct the
   agent to read relevant migrations, not just application
   code. Backfill migrations often contain business decisions
   (which legacy records to include, conflict resolution
   behavior) that are invisible from the application layer but
   critical to understanding a member's current state.

## What the Review Lens Catches

The Tracker review lens (observability and consistency) is
explicitly different from the Implementer lens (spec
compliance), the Tester lens (test coverage), and the
Investigator lens (structural correctness). The categories of
findings:

1. **Asymmetries**: Two code paths that should produce the same
   result update different fields. The missing field is not a
   bug today, but it is a latent inconsistency.
2. **Constant inconsistencies**: A status list used in one part
   of the code does not match the equivalent list used in
   another part. Both lists are valid independently, but
   together they create a gap where a record in a valid state
   falls through.
3. **Observability gaps**: Error paths that bypass the standard
   logging or error-handling wrappers. The code works, but when
   it fails, the failure is invisible.

None of these are correctness bugs in the narrow sense. They
are consistency and observability gaps that make the next bug
harder to find and fix. The Tracker review lens is
maintenance-oriented: will the next developer understand this
code, and will the next failure be observable?
