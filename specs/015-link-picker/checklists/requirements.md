# Specification Quality Checklist: A Picker for Ambiguous `/link`

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
- Validation run 1 flagged two issues, both fixed before this checklist was marked complete:
  - An assumption named an internal core function; reworded to describe the existing search in prose.
    The one remaining code-level reference sits in Dependencies, where naming the shipped primitive
    this feature builds on is the point of the section.
  - Behaviour for keys other than `↑`/`↓`/`enter`/`esc` while the list is open was unstated; a
    reasonable default (ignored, so no keystroke aimed at the list can reach the document) is now
    recorded in Assumptions and constrained by FR-007.
- No [NEEDS CLARIFICATION] markers were needed. Issue #46 specifies keys, ordering, row content, and
  both fast paths; everything else had a defensible default, recorded in Assumptions.
- Revalidated after `014-inline-editor-pane` merged. That feature gave the editor two hosts (inline in
  the preview pane, and full-screen), which the original spec did not account for. Added: a
  "Builds on" note, FR-004 (parity across both hosts), FR-005 (nothing on screen is displaced),
  FR-018 and an edge case for resize while a choice is pending, US3 scenarios 6-7, SC-007, and two
  dependency notes. FRs renumbered accordingly; no requirement was removed or weakened. All 16 items
  still pass.
- Revised again during implementation, where FR-005 turned out to be stricter than the interface it
  describes. It required that opening the list not resize the list and scope panes; but the status-bar
  region is docked with automatic height and its siblings share the remaining space, so *any* occupant
  becoming visible costs them rows — the command bar has always done exactly this when `/` is pressed.
  No bottom-bar picker could satisfy the requirement as written. FR-005 now states what is actually
  guaranteed (no overlay, no pane introduced or removed, width, horizontal position, and visibility
  all held) and names the vertical give-back as the existing behaviour it is. US3 scenario 6 and
  contract C1 were reworded to match. This is a correction to a requirement that was wrong about the
  system, not a relaxation to fit an implementation.
