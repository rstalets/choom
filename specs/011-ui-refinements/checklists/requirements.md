# Specification Quality Checklist: UI Refinements

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-01
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

1. *Requirements are testable and unambiguous* — FR-032 said columns are dropped "in a defined priority
   order" without defining it; the order lived only in Assumptions. The order (tags first, then type,
   with date and title always kept) is now stated in the requirement itself.
2. *Requirements are testable and unambiguous* — FR-036 asked that a long path be shortened so its
   "deepest components stay readable", which two implementers could satisfy differently. Rewritten to
   name the behaviour: elide from the left, keep the final component intact, mark the elision visibly.
3. *Success criteria are measurable* — SC-006 was phrased as what a first-time user "can state", which is
   not checkable without a study. Rewritten as a property of the labels: each names its key and its
   outcome, and no label is a bare OK/Yes/No/Cancel.

**Iteration 2** — all items pass. No [NEEDS CLARIFICATION] markers remain. Every open decision in the
source issue was resolved as an informed default and written into Assumptions with the rejected
alternative and the reason.

**Iteration 3** — two revisions after review, both re-validated:

1. *Scope is clearly bounded / requirements are testable* — **story order was wrong for implementation**.
   Deleting from the list was P1 and the confirmation redesign was P4, so an implementer working in
   priority order would have wired the delete to the dialog that exists today and then replaced it three
   stories later — building the confirmation twice and shipping the old style in between. The
   confirmation is now P1 and the three delete stories follow it as P2–P4. A **Sequencing note** at the
   head of the user-scenarios section states which dependency is binding and which stories are free to
   move, and FR-009 now says outright that the delete confirmation is the confirmation specified in
   FR-021–FR-026, so the dependency survives someone reading the requirements without the stories.
2. *Requirements are testable and unambiguous* — **Story 6 moved the workspace path from the bottom bar
   to the top bar**, snapped to the top-right corner, because bottom-bar width is at a premium. Story 6,
   FR-034/FR-036, the narrow-bar edge case, SC-008, and the Assumptions entry were all rewritten; a new
   FR-038 makes "spends no bottom-bar width" checkable, and the cursor-placement requirements renumbered
   to FR-039–FR-043. The Assumptions entry records that the source issue asked for the bottom bar and
   that this was a deliberate revision, not a misreading.

**Iteration 4** — one dependency settled, not a defect:

`010-read-on-load` (#51) is confirmed to land **before** this feature, so the session-lifetime snapshot
is gone by the time this is built. Recorded in a new "Sequenced after" line in the header, in
Dependencies and Relationships, and in Assumptions: a delete has no cache to invalidate, and FR-011's
refresh is for immediate feedback rather than correctness. The one genuine interaction it creates — a
periodic re-read landing while a confirmation is on screen — is now covered by FR-010 (the confirmation
acts on the record it named when raised) and an edge case. Dependencies also records the gate: #51's
implementation is merged into this branch and the spec re-checked against it before `/speckit-plan`.

Note: the Functional Requirements are grouped by theme, so the delete requirements still appear before
the confirmation ones. That is deliberate — renumbering 27 requirements to mirror story order would
invalidate every existing cross-reference. Build order is carried by the story priorities, the sequencing
note, and FR-009's explicit pointer.

### Terminology note on "implementation details"

The spec names user-facing surfaces — `ctrl+d`, `Esc`, `Enter`, `choom <type> delete <id> --force`,
`--json`, the tasks file, exit codes. These are the product's contract with its users and with the
assistants that read a workspace, documented in `docs/REQUIREMENTS.md` and `AGENTS.md`, not internal
design. No module, function, widget, language, or data-structure choice appears.

### Carried assumptions worth a second look at `/speckit-clarify`

- The task done-state marker sits outside the four labelled columns rather than inside the date column.
- The explicit delete flag is `--force` (rather than `--yes`), and delete identifies records by id only,
  with no path form for documents.
- Entering edit mode positions the cursor without writing blank lines into the buffer, so an untouched
  document is never marked dirty by the placement alone.
- The workspace path shows only on screens that have a top bar (the list screen today), not on the
  full-screen preview or editor.
- Deletion does not scan for inbound links before confirming; dead links are left for the existing link
  check to report.
