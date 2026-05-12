# {investigation_title}

## Status

## Context

## Symptom

---

## Agent Analysis

### Implementer

### Investigator

### Tracker

### Historian

## Agent Synthesis

## Attribution rule

If the system being investigated has multiple paths that produce
the same kind of resource (e.g., multiple Stripe customer-create
paths, multiple webhook subscribers, multiple migration scripts),
build a signature-based attribution table early. Identify the
externally-observable fingerprint each path leaves on the
resulting resource (metadata keys it sets, idempotency-key
presence, originator request fields, structural fields populated
vs empty). The synthesis then uses this table to classify any
sampled resource to its originating path deterministically,
rather than relying on circumstantial reasoning. Drop or replace
this section if the investigation does not have multiple
candidate origin paths.

## Recommended Actions
