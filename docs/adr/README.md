# Architecture Decision Records

The decisions made up to v1.1 are summarised in [`FINAL_ARCHITECTURE_PLAN.md` §37](../FINAL_ARCHITECTURE_PLAN.md) (ADR-001 … ADR-015).
New significant decisions get a file here: `NNNN-short-title.md`, numbered from 0016.

```markdown
# NNNN. Title

- Status: proposed | accepted | superseded by NNNN
- Date: YYYY-MM-DD

## Context
What forces are at play, and what problem needs a decision.

## Decision
What we will do.

## Consequences
What becomes easier or harder, and what follow-up work is needed.
```

A decision needs an ADR when it changes layering, data ownership, security posture, a public API contract, or the choice of a major dependency.
