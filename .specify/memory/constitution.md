<!--
SYNC IMPACT REPORT
==================
Version change: (uninitialized template) → 1.0.0
Bump rationale: Initial ratification. All placeholder tokens replaced with
concrete governance for the endpaper project.

Modified principles:
  - [PRINCIPLE_1_NAME] → I. Core Is the Product
  - [PRINCIPLE_2_NAME] → II. Two Interfaces, One Contract
  - [PRINCIPLE_3_NAME] → III. Simplicity Is the Default (NON-NEGOTIABLE)
  - [PRINCIPLE_4_NAME] → IV. Never Lose the User's Words
  - [PRINCIPLE_5_NAME] → V. The Interface Is Specified, Not Improvised
  - (added)           → VI. Readable Python, Enforced Automatically

Added sections:
  - Platform & Distribution Constraints (was [SECTION_2_NAME])
  - Development Workflow & Quality Gates (was [SECTION_3_NAME])

Removed sections: none

Templates requiring updates:
  ✅ .specify/templates/plan-template.md — Constitution Check gates populated
  ✅ .specify/templates/spec-template.md — reviewed; no constitution-driven
     mandatory sections added or removed (principles constrain HOW, spec
     template governs WHAT)
  ✅ .specify/templates/tasks-template.md — sample Foundational tasks rewritten
     to core-first (they led with database/auth setup, contradicting III);
     Polish phase now includes terminal- and platform-verification tasks
  ✅ .claude/skills/speckit-*/SKILL.md — reviewed; no outdated agent-specific
     references requiring generic guidance

Follow-up TODOs:
  - README.md names the project "cairn" while REQUIREMENTS.md, the command
    name, and this constitution use "endpaper". Not changed here (outside the
    constitution workflow's scope); resolve before first public release.
-->

# endpaper Constitution

## Core Principles

### I. Core Is the Product

`endpaper.core` holds all logic: vault resolution, frontmatter parsing, file creation,
markdown scanning, search, and task toggling. Core MUST contain no I/O formatting, no
widget code, and no argument parsing. Every core function MUST be callable and testable
without a terminal, a TTY, or an event loop.

**Rationale**: Two peer front-ends can only stay behaviourally identical if neither owns
behaviour. A core that needs a terminal to run is a core that cannot be tested, and
untestable logic is where divergence between the CLI and the TUI begins.

### II. Two Interfaces, One Contract

The CLI and the TUI are peers. Both are thin adapters over `core`; neither shells out to
the other. Any behaviour available in one MUST be available in the other, unless it is
inherently interactive (live filtering) or inherently non-interactive (stdin piping).

The CLI serves AI assistants, and that is a hard requirement:

- MUST NOT open an editor. No `$EDITOR`, no subprocess to an editor, ever.
- MUST NOT block on input. No prompts, no confirmations, no pagers. Destructive
  operations take an explicit flag instead of asking.
- MUST NOT colorize or decorate when stdout is not a TTY.
- `--json` MUST be available on every read command and emit a stable, documented schema.
  Adding a key is a minor change; renaming or removing one is breaking.
- Data goes to stdout, errors to stderr. Exit codes are meaningful: 0 success, 1 not
  found, 2 usage error, 3 workspace error.

**Rationale**: The CLI is an assistant's only interface. A single interactive prompt or a
stray escape sequence on a non-TTY turns a working automation into a hang or a corrupt
parse, and the failure is silent from the assistant's side.

### III. Simplicity Is the Default (NON-NEGOTIABLE)

Markdown files are the only state endpaper has. Introducing a second source of truth —
an index, a database, a cache — requires a documented justification in the plan's
Complexity Tracking table, naming the simpler alternative and why it fails.

- No SQLite, no index, no `reindex` command.
- No external binary dependencies for core functionality (no `ripgrep`, no `pandoc`);
  the target machine is locked down and cannot be assumed to have them.
- Prefer the standard library. Every third-party dependency MUST be justified by what it
  would cost to do without.
- Configuration beyond workspace paths is out of scope. A setting that could be a
  sensible default MUST be a sensible default.

**Rationale**: At hundreds to low thousands of files, a full scan costs a fraction of a
second — cheaper than the invalidation logic, staleness bugs, and corruption risk an
index introduces. A database file inside a OneDrive-synced folder is a genuine corruption
hazard, and the simplest way to avoid it is to not have one.

### IV. Never Lose the User's Words

Users hand-edit their files, in endpaper and elsewhere. Every parser and writer MUST
treat that as the normal case:

- Malformed input is skipped and logged, never fatal. A broken metadata comment on one
  task line MUST NOT prevent the rest of the file from parsing.
- A parse failure MUST NEVER lose a line or truncate a file.
- Missing metadata is repaired in place — a checkbox with no id gets one written back,
  without disturbing surrounding lines.
- Files stay valid CommonMark. Metadata rides in HTML comments and frontmatter so that
  any markdown viewer renders the file correctly.
- Writes preserve `created` and update `updated`. Never the reverse.

**Rationale**: The vault is the user's own notes in their own directory. Data loss is not
a bug with a severity rating here; it is a breach of the premise that makes a plain-files
tool worth using over an app with a database.

### V. The Interface Is Specified, Not Improvised

User-facing behaviour is decided in the spec, not at the keyboard.

- The TUI is one screen: a filterable list and a preview pane. States are list → preview
  → edit, and every transition is one keystroke.
- Reading is the default; editing is the exception. Opening an existing note shows
  rendered markdown.
- Every active binding is visible in the footer. No hidden keys.
- Confirmations fire only when there is something to lose. A dialog that appears when
  nothing would be discarded teaches users to dismiss it reflexively, which disarms it
  for the one time it matters.
- Key bindings MUST respect terminal reality: `ctrl` is the only portable modifier, `ctrl+c`
  and `ctrl+q` are reserved, and `ctrl+s` is XOFF and MAY be bound only as an alias to a
  canonical binding that is guaranteed to arrive.
- Error messages name what went wrong and what to do instead, including the directory or
  command the user should have used.

**Rationale**: The tool's whole claim is that it disappears into the twenty seconds
before a meeting. Every decision the user has to make — where a file goes, what to call
it, which key saves — spends that budget.

### VI. Readable Python, Enforced Automatically

This is a public open-source project. Code is read far more often than it is written, and
by strangers.

- Python 3.11+. Formatting and linting are enforced by tooling in CI, not by reviewers.
- Public functions in `core` carry type hints and a docstring stating what they do and
  what they raise. Type checking runs in CI.
- Tests use `pytest` and run against `core` without a terminal. Every acceptance criterion
  in a spec MUST map to at least one test.
- Prefer a plain function to a class, a class to a framework, and an explicit branch to a
  clever abstraction. Names say what the thing is; comments explain only why.
- Public API changes — `--json` schemas, exit codes, frontmatter fields, the task line
  format, file layout — MUST be recorded in the changelog with their version.

**Rationale**: Automated gates make quality the cheap path rather than a matter of
reviewer stamina, and a contributor who can read the codebase in an afternoon is a
contributor who sends a second patch.

## Platform & Distribution Constraints

- Windows, macOS, and Linux are supported. Windows is a first-class target — the primary
  user is a corporate employee on a managed machine.
- Installation MUST NOT require admin rights. `uv tool install` and `pipx` are the
  supported paths.
- No operation may require network access.
- Paths MUST stay well under the Windows 260-character limit; assume the workspace root is
  already a long OneDrive path.
- Workspace paths containing spaces and non-ASCII characters MUST work.
- Per-user state (such as the current workspace) MUST live in per-user local state, never
  in the shared workspace directory, so two people sharing a synced folder cannot
  overwrite each other's selection.
- `AGENTS.md` is generated at `init` and MUST stay under roughly 60 lines. It carries the
  folder layout, the frontmatter schema, the task line format, and the commands an
  assistant needs. It does not restate the README.

## Development Workflow & Quality Gates

- Specs precede plans, plans precede tasks, tasks precede code.
- The Constitution Check in `plan.md` MUST pass before Phase 0 research and be re-checked
  after Phase 1 design. Violations are either fixed or justified in the Complexity
  Tracking table — an empty justification is a failed gate.
- Every pull request MUST pass formatting, linting, type checking, and the test suite
  before review.
- Behaviour changes MUST land with the tests that cover them and the documentation that
  describes them, in the same change.
- TUI changes MUST be verified on the target terminals before release: Windows Terminal,
  iTerm2, macOS Terminal, PuTTY, and inside tmux.
- Anything in a version's explicit out-of-scope list stays out until a spec moves it.

## Governance

This constitution supersedes all other development practices. Where a convention, a habit,
or a reviewer's preference conflicts with a principle here, this document wins.

**Amendments** require a pull request that states the principle being changed, the
rationale, and the migration path for any code or specs the change invalidates. Amendments
take effect when merged.

**Versioning** follows semantic versioning:

- **MAJOR**: a principle is removed or redefined in a backward-incompatible way.
- **MINOR**: a principle or section is added, or existing guidance is materially expanded.
- **PATCH**: clarifications, wording, and typo fixes that do not change meaning.

**Compliance** is verified at two points: the Constitution Check gate in every
implementation plan, and pull request review. Reviewers MUST cite the principle by number
when requesting a change on constitutional grounds. Complexity that cannot be justified
in writing is removed rather than merged.

`REQUIREMENTS.md` holds the current version's scope and acceptance criteria; `AGENTS.md`
in a workspace holds runtime guidance for AI assistants. Neither overrides this document.

**Version**: 1.0.0 | **Ratified**: 2026-07-28 | **Last Amended**: 2026-07-28
