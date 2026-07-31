# Specification Quality Checklist: Local AI Assistant Invocation

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

### Two decisions carried forward for confirmation

Neither is left as a `[NEEDS CLARIFICATION]` marker, because the constitution supersedes other
inputs and therefore supplies the resolution. Both are recorded in Assumptions with the principle
that drove them, and both are worth an explicit nod before `/speckit-plan`, because each departs
from the literal text of issue #19:

1. **`endpaper init` records the assistant from an argument instead of asking.** Issue #19 item 3
   says the user "should be asked" at `init`. Constitution II forbids the command line from
   blocking on input, without exception. FR-027 keeps the intent (configure at init) and
   FR-025 keeps the interactive path (`/config assistant` in the terminal interface). If the author
   wants a genuine question at `init`, it has to live in the terminal interface's own `/init` verb —
   already reserved in the verb table but with no action — and that is a different requirement than
   the one written here.
2. **Where the assistant setting lives is left to the plan.** Issue #19 says "stored in the toml
   file". The constitution requires per-user state to live in per-user local state and never in the
   shared workspace directory, precisely so two people on a synced workspace cannot overwrite each
   other. FR-029 therefore states the observable requirement — persists, resolves per workspace,
   does not leak between workspaces — and leaves the file to the plan. Note that endpaper has no
   per-user state store today, so honouring this creates one; that cost, and the tension with
   Constitution III ("configuration beyond workspace paths is out of scope"), both belong in the
   plan's Complexity Tracking table.

### Items reviewed and accepted with reasoning

- **Naming Claude Code CLI and GitHub Copilot CLI** is not an implementation detail. They are the
  products this feature integrates with, named in the issue, and the user chooses between them by
  name. FR-020 is what keeps them from becoming structural.
- **Naming user-facing commands and arguments** (`/ai`, `/config assistant`, `endpaper init` with
  an assistant argument, `ctrl+c`) follows the precedent set by `004-viewing-editing` and
  `005-ui-layout-refresh`: the command surface is the product's contract with the user, and
  Constitution II makes the command line's surface product behaviour rather than implementation.
- **SC-002's one-second cancel budget** is a user-perception threshold, not a benchmark of any
  particular mechanism.
- **FR-009 says the request "identifies the saved document"** rather than specifying what is sent.
  Whether that is a path, a range, or something else is a planning decision; the requirement is that
  the assistant can resolve a prompt like "the process described on lines 15-18".
- **`ctrl+c` as the cancel key** conflicts with Constitution V's reservation of that key. The spec
  accepts it only inside the locked in-flight state, where it is the sole available action, and
  says so in Assumptions. If planning finds this cannot be done safely on a target terminal, the
  key is the thing to change, not the requirement that cancelling is always available.

### Coverage gaps closed during validation

The first draft left FR-003/FR-004 (framework extensibility and help discoverability), FR-018
(document changed on disk mid-request), FR-021 (non-interactive invocation), FR-023 (more than one
assistant available), and FR-030 (configuration predating the feature) without acceptance
scenarios. Scenarios were added to User Stories 1, 2, and 3 to cover each. FR-020's extensibility
claim is verified by SC-005 (identical behaviour across assistants) rather than by a scenario, since
it is a property of the design rather than an observable event.
