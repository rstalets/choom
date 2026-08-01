# Specification Quality Checklist: Assistant Discovery File

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

**Iteration 1** — two issues found and fixed:

1. *Requirements are testable and unambiguous* — FR-014 said a failed discovery-file write is
   reported "on the diagnostic stream". The TUI has no diagnostic stream, and FR-015 covered only
   the success message, so the failure path was specified for one interface and silent in the
   other — a gap against Principle II ("any behaviour available in one MUST be available in the
   other"). FR-014 now names both interfaces and the surface each uses.
2. *All functional requirements have clear acceptance criteria* — FR-013 said a discovery-file
   failure "MUST NOT be fatal" without saying what the command then reports. Since this repository
   holds a stable exit-code registry, "not fatal" left the observable outcome undefined. FR-013 now
   states that success or failure reports the setting write and that the discovery file is reported
   alongside it, never in place of it, which is what US3 scenario 2 tests.

**Decisions taken rather than deferred to `[NEEDS CLARIFICATION]`** (all recorded in Assumptions,
each reversible without touching the rest of the spec):

- *Where each assistant reads from.* Both supported assistants have a documented user-scope location
  that applies regardless of working directory, confirmed against the Copilot CLI documentation for
  `copilot` and Claude Code's user-scope skills for `claude`. FR-017's "no location that fits"
  branch is therefore a rule for future assistants, not dead weight for a case that exists today.
  Exact paths and file names are planning work and are deliberately not fixed here.
- *One pointer at a time.* Switching assistants removes the file installed for the previous one
  (FR-008), so `none` has a single, checkable meaning and choom's footprint in the user's profile
  cannot accumulate.
- *`init --assistant` installs it too.* Beyond the literal text of issue #37, which names only
  `/config assistant`, but the same act of naming an assistant. Isolated as US4/P4 so it can be cut
  without disturbing US1–US3.
