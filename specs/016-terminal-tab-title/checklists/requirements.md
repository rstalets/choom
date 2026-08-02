# Specification Quality Checklist: The Terminal Tab Names the Workspace

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-02
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
- No [NEEDS CLARIFICATION] markers were needed. Issue #47 fixes the title wording, the trigger, the
  restore-on-exit obligation, and the scope boundary (workspace only, set once); every remaining gap had
  a defensible default, recorded in Assumptions.
- Validation run 1 flagged four gaps, all closed before this checklist was marked complete:
  - **Abnormal exits were unstated.** The issue says only "restore the previous title on exit". FR-011
    now enumerates every exit path choom can observe — plain `ctrl+q`, `ctrl+q` after a discard
    confirmation, any other in-app quit, `ctrl+c`, and an unhandled error — and FR-019 records the one
    case no in-process code can cover (kill signal, closed window), rather than leaving it implied.
    FR-012 adds the inverse case a reader would otherwise assume wrong: a cancelled quit must *not*
    restore.
  - **The CLI's position was unaddressed.** Constitution Principle II requires either the peer behaviour
    or a stated carve-out. The "Interface parity" subsection now states the carve-out explicitly, with
    its reasoning, and FR-016 turns it into a testable prohibition covered by US4.
  - **The core/interface boundary was implicit.** Principle I forbids I/O formatting in `choom.core`.
    FR-003 and FR-007 now split the feature at the text/bytes line, and the "Layering" table names which
    side each piece sits on so the plan's Constitution Check has something concrete to check against.
  - **Hostile and degenerate workspace names had no stated behaviour.** A POSIX directory name may
    contain an escape character, which would let the directory issue arbitrary terminal commands through
    an unfiltered title. FR-004 requires control characters be stripped, FR-005 bounds the length, and
    FR-002 covers a root with no final path segment.
- Two numeric choices are fixed here rather than left to implementation, per Principle V (the interface
  is specified, not improvised): the 64-character title cap (FR-005) and the exactly-once set at startup
  (FR-008, FR-009). Both are unit-testable against the core composition function without a terminal.
- Post-review fix (spec gate PASS, planning round): FR-016 read "No `choom` subcommand invocation MUST
  ever emit a title sequence" — a malformed MUST, since the negation attaches to the subject and the
  sentence parses as the opposite of its intent. Reworded to "Every `choom` subcommand invocation MUST
  NOT emit...". Meaning unchanged; ambiguity removed, because implementers read requirement text
  literally.
- Planning research turned up one thing worth recording against FR-011, which is left as written: inside a
  running choom, `ctrl+c` is **not** an exit path. Textual binds it to its own `action_help_quit`, which
  shows "Press ctrl+q to quit" and does not terminate anything. FR-011 is still satisfied — where a SIGINT
  does end the process it raises `KeyboardInterrupt`, which the restore path catches by process teardown
  rather than by any binding, as constitution Principle V requires. See research R4.
- No configuration knob is proposed, so Principle III's sensible-default rule is satisfied by FR-017
  rather than justified as a complexity exception.
