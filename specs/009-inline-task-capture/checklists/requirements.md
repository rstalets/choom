# Specification Quality Checklist: Inline Task Capture

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-31
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- Items marked incomplete require spec updates before `/speckit-clarify` or `/speckit-plan`

### Validation record

**Iteration 1** — three issues found and fixed:

1. *Success criteria are measurable* — SC-007 ("costs no more than it does today") and SC-008
   ("imperceptible") had no threshold. Rewritten with a file-count bound and a 50 ms budget, and a new
   SC-012 added giving the capture gesture a 200 ms keypress-to-cursor budget.
2. *Requirements are testable and unambiguous* — "since they last agreed" (FR-024) was undefined without
   stored state. Pinned down in Key Entities ("Editing session") and in Assumptions to mean the item's
   state at document open, held in memory only.
3. *Scope is clearly bounded* — the source issue's promote gesture ("`/task` with no description on a line
   that already contains text") admits two readings. Resolved in favour of the prefix form, which needs no
   grammar change, and recorded in Assumptions with the rejected alternative and the reason.

**Iteration 2** — all items pass. No [NEEDS CLARIFICATION] markers remain; the three decisions above were
taken as informed defaults rather than deferred, and each is written down where a reader will find it.

### Terminology note on "implementation details"

The spec names user-facing surfaces — the `/task` grammar, `endpaper task add --link`, the `links` field
in a task's metadata comment, the checklist syntax left in a document. These are the product's contract
with its users and with the assistants that read a workspace, documented in `REQUIREMENTS.md` and
`AGENTS.md`, not internal design. No module, function, language, or data-structure choice appears.

### Carried assumptions worth a second look at `/speckit-clarify`

- The promote gesture is a prefix (`/task.followup ` typed in front of existing line text), not a trailing
  token.
- Reconciliation on open writes the document when — and only when — something actually changed, rather than
  correcting the displayed copy alone.
- Open resolves in favour of the tasks file; save resolves in favour of the document.
