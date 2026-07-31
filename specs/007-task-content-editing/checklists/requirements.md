# Specification Quality Checklist: Task Content Editing

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-30
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

- Items marked incomplete require spec updates before `/speckit-clarify` or `/speckit-plan`.

### Validation record

Two decisions with no safe default were resolved with the requester before drafting, so no
`[NEEDS CLARIFICATION]` markers were carried into the spec:

1. **Body storage** — inline, indented beneath the task's own line in `tasks.md`, rather than a
   per-task sidecar file. Recorded in Assumptions with its trade-off.
2. **Command-line surface** — a read command that shows one task and its body, plus a body field
   in the machine-readable listing. No interactive CLI writer. Recorded in Assumptions.

Vocabulary check: `tasks.md`, the preview pane, the editor, and the `e` binding appear in the
requirements. These are the product's own user-facing vocabulary, established in `REQUIREMENTS.md`
and named directly in issue #26 — not implementation choices. No language, framework, library, or
module is named anywhere in the spec.

One derived decision is called out in Assumptions rather than left implicit: a checkbox line
indented under a task continues to parse as its own task, which bounds where a body ends. The
alternative — treating nested checkboxes as body content — would silently reclassify tasks in
vaults that already exist, so it was rejected on the "never lose the user's words" principle.
