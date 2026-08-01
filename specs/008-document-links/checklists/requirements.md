# Specification Quality Checklist: Document Links

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

Validation performed 2026-07-31. All items pass.

**Issues found and fixed during validation:**

- *No implementation details*: the Assumptions section originally described inbound-link scanning as
  happening "in pure Python". Rewritten to state the constraint that actually matters to a
  stakeholder — no external binary, no network access — with the language left to the plan.

**Judgement calls recorded rather than flagged**, so a reviewer can challenge them:

- **Command names appear in the spec** (`endpaper links`, `/link`). For a terminal tool the command
  surface *is* the user-facing interface, not an implementation choice, and every prior spec in this
  repository states it the same way. Not treated as an implementation-detail leak.
- **"Valid CommonMark" appears in requirements and success criteria.** This is a data-format contract
  the product already commits to in REQUIREMENTS.md §3.3 and constitution principle IV, and it is
  verifiable by a stakeholder opening the file in any markdown viewer. Not treated as a technology
  reference.
- **Zero [NEEDS CLARIFICATION] markers were raised.** Every gap in issue #27 had a default derivable
  from the constitution or existing behaviour; each one is written down in Assumptions instead of
  deferred to the user. The two closest calls, both defaulted rather than asked:
  - `/link` with more than one match — resolved as *report and insert nothing*, because a picker
    contradicts "never take the user out of the document" (constitution V, REQUIREMENTS §3.5).
  - Whether the preview pane's inbound links load on document open — resolved as *on section open*,
    following issue #27 item 5 and the cost asymmetry between outbound (free) and inbound (a scan).

**Coverage check** — every acceptance criterion in issue #27 maps to spec content:

| Issue #27 AC | Spec coverage |
|--------------|---------------|
| 1. Fragment-only link resolves, gains path on save | US2 AC1–2, FR-004, FR-022, SC-001 |
| 2. Path-only link resolves, gains fragment on save | US2 AC3, FR-005, FR-023, SC-002 |
| 3. Move a document; heal repairs, dry-run matches | US4 AC4–5, FR-035, FR-037, SC-003 |
| 4. Deleted target is dead, never rewritten | US2 AC5–6, US4 AC1–2, FR-025, SC-004 |
| 5. Correct path from every layout depth | Edge Cases (Repair), FR-007, SC-005 |
| 6. Files stay valid CommonMark and clickable | FR-008, US5 AC8, SC-010 |
| 7. `links <id> --direction in` lists inbound | US3 AC1, FR-032, SC-006 |

Items marked incomplete would require spec updates before `/speckit-clarify` or `/speckit-plan`; none
are.
