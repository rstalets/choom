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

### One decision carried forward for confirmation

It is not left as a `[NEEDS CLARIFICATION]` marker, because the constitution supersedes other inputs
and therefore supplies the resolution. It is recorded in Assumptions with the principle that drove
it, and is worth an explicit nod before `/speckit-plan`, because it departs from the literal text of
issue #19:

1. **`endpaper init` records the assistant from an argument instead of asking.** Issue #19 item 3
   says the user "should be asked" at `init`. Constitution II forbids the command line from
   blocking on input, without exception. FR-027 keeps the intent (configure at init) and
   FR-025 keeps the interactive path (`/config assistant` in the terminal interface). If the author
   wants a genuine question at `init`, it has to live in the terminal interface's own `/init` verb —
   already reserved in the verb table but with no action — and that is a different requirement than
   the one written here.

### Resolved by the author after the first draft

**Where the assistant setting lives** was initially carried forward as a second open decision. The
first draft read the constitution's rule — per-user state must never live in the shared workspace
directory, so two people on a synced folder cannot overwrite each other — as applying here, and
left the storage location to the plan.

The author confirmed that shared workspaces are not a factor: a workspace is intended for one user,
and the future shared-workspace design nests each user's workspace one level below a parent
workspace carrying its own configuration file. A single-user workspace file therefore *is* per-user
state, the rule is not engaged, and the setting does not have to move when shared workspaces arrive.
FR-029 now says plainly that the setting is stored in the workspace's own configuration, matching
issue #19. No new per-user state store is needed.

The remaining tension — Constitution III's "configuration beyond workspace paths is out of scope" —
is unaffected by this and still belongs in the plan's Complexity Tracking table.

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

### Re-validated against the test suite retrofit (#29), 2026-07-30

The suite was rebuilt for the constitution's risk-based coverage rule after this spec's first draft.
Re-reading the spec against the merged suite changed one requirement and clarified another:

1. **FR-018 reversed.** It used to require detecting that the document changed on disk mid-request
   and warning the user. `tests/integration/test_external_edits.py` pins the opposite as endpaper's
   established behaviour: an externally modified file opens, edits, and saves like any other, buffer
   wins, no warning anywhere. `REQUIREMENTS.md` §5 also lists conflict resolution for simultaneous
   edits as out of scope, with OneDrive's conflict-copy behaviour named as the answer. The old
   FR-018 was scope this spec invented — it is not in issue #19 and exists nowhere in the product.
   FR-018 now states the boundary explicitly, User Story 2's scenario 8 asserts the buffer-wins
   outcome instead of a warning, and the reasoning is recorded in Assumptions. FR-010's instruction
   to the assistant to reply rather than edit remains the only mitigation, which is the right size
   for the risk.
2. **FR-025 pinned to a surface.** `tests/unit/test_command_parsing.py::test_existing_verbs_unchanged`
   asserts the command-bar verb table is exactly nine verbs, which makes "which surface does
   `/config` live on" a question with a testable answer rather than a planning guess. FR-025 now
   says `config` is a command-bar verb — it acts on the workspace, not on a document — while `/ai`
   is the in-editor surface FR-001 introduces.

Three pinned tests that this feature must update rather than merely extend are now named in the
spec's Dependencies, so planning does not read them as unexpected breakage. Nothing else in the
spec needed to change: the retrofit's parametrized CLI/TUI parity tests match FR-026's requirement
for a command-line peer, `tests/contract/test_non_blocking.py` is exactly the gate FR-027's
no-prompt rule has to pass, and `tests/integration/test_save_failure.py` already establishes the
buffer-intact-on-failed-save behaviour FR-008 depends on.
