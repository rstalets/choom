<!--
SYNC IMPACT REPORT
==================
Version change: 1.1.0 → 1.2.0
Bump rationale: MINOR, covering two amendments in one bump. (1) Principle VI
gains a new testing rule (tests must not depend on the wall clock), which
materially expands existing guidance. (2) The `AGENTS.md` constraint raises its
line cap from 60 to 100 and reframes the cap as the backstop to a content rule
rather than the rule itself — a relaxation. No principle is removed, renamed,
or redefined, and nothing that satisfied the 1.1.0 rules becomes non-compliant:
the tests that violated the new wall-clock rule were already fixed before this
amendment, and the `AGENTS.md` template sits at 60 lines, well inside the new
cap.

Modified principles:
  - VI. Readable Python, Enforced Automatically — new bullet added alongside
    the existing testing bullet: "Tests MUST NOT depend on the wall clock",
    with the failure it prevents (a fixture pinned to a literal month falling
    out of a month-scoped view and rendering an empty list) and the remedy
    (derive such dates from the same clock the behaviour reads).
  - Platform & Distribution Constraints — the `AGENTS.md` bullet no longer
    leads with "MUST stay under roughly 60 lines". The binding rule is now
    content (nothing an assistant could infer from the workspace itself; no
    restating the README) and roughly 100 lines is its checkable backstop.
    Two reasons. The number was already under water: the template is at
    exactly 60 today, has been hand-tightened twice to stay there (007's
    `task show`, 008's link syntax), and REQUIREMENTS.md §4.2 already promises
    `read`, `write`, `append`, and `find` — four AI-facing commands that must
    appear in the file when they land. With `workspace list/use/current` from
    the §6.1 backlog, v1.0 projects to roughly 75–80 lines. More importantly,
    a hard cap that forces deleting real instructions inverts its own purpose;
    exceeding the cap now triggers a review of the whole file rather than the
    automatic removal of whatever was added last. The rationale about context
    files is preserved verbatim in substance — only the number and the framing
    change.

Added sections: none
Removed sections: none

Templates requiring updates:
  ✅ .specify/templates/plan-template.md — Constitution Check gate VI row
     extended with "and no test depends on the wall clock", so every future
     plan is checked against the new rule at the gate
  ✅ .specify/templates/tasks-template.md — reviewed; left unchanged. Its
     per-user-story notes govern which test layers a story needs, not how a
     fixture is written, and repeating the rule in all three story phases
     would add noise without adding a check the plan gate does not already do
  ✅ .specify/templates/spec-template.md — reviewed; left unchanged. No
     constitution-driven mandatory section is added or removed, and how a
     test sources its dates is an implementation concern, not a spec one
  ✅ .specify/templates/checklist-template.md — reviewed; left unchanged. It
     carries no test-authoring guidance to contradict
  ✅ .claude/skills/speckit-*/SKILL.md — reviewed; left unchanged. None
     instructs an agent to write date literals into fixtures, and each already
     defers to the constitution as the authority on testing discipline
  ✅ README.md — updated for amendment 2 only: the `AGENTS.md` bullet said
     "under ~60 lines" and would otherwise contradict this document. Reviewed
     for amendment 1 and left unchanged there; it documents usage, not test
     authoring. (No AGENTS.md exists at the repository root; the file is
     generated into a workspace at `init`.)

Non-template files, amendment 2:
  ✅ tests/contract/test_guidance_docs.py — updated. It held the one test that
     asserted the old number (`test_agents_md_stays_within_line_budget`,
     `<= 60`); it now asserts `<= 100`, with a comment recording what the bound
     is a backstop for. The only `tests/` change in this amendment; no source
     behaviour changes.
  ✅ REQUIREMENTS.md §4.3 — reviewed; deliberately left unchanged. It still
     reads "Kept under roughly 60 lines" and so now states a tighter cap than
     this document. That divergence is known and accepted, not an oversight:
     REQUIREMENTS.md is being retired under separate work in flight, and
     editing it here would only create a conflict for that job on a file that
     is going away. The Governance section already settles which document wins
     — this constitution supersedes other practices, and REQUIREMENTS.md does
     not override it — so the stale number misleads no one with authority to
     act on it, and no note was added to REQUIREMENTS.md saying so.

Follow-up TODOs:
  - (Dropped) REQUIREMENTS.md §4.3's stale "six commands" count was logged
    here mid-amendment, then withdrawn: the file is being retired, so a TODO
    pointing at it would never be actioned.

Migration path:
  - Amendment 1 (wall clock): none required. No existing spec, plan, or test
    becomes non-compliant. The six tests that violated the rule (July-2026
    fixtures asserted against the month-scoped list introduced by spec 005)
    were already repaired on main before this amendment landed.
  - Amendment 2 (AGENTS.md cap): none required. The change only relaxes an
    existing limit. The template is at 60 lines and stays compliant; anything
    that satisfied the 60-line cap satisfies the 100-line one.
-->

<!--
SYNC IMPACT REPORT
==================
Version change: 1.2.0 → 1.3.0
Bump rationale: MINOR, covering four amendments in one bump. (1) Two conventions
are promoted from docs/REQUIREMENTS.md into gated principles (III, IV). (2) Three
enumerated registries move out to docs/REQUIREMENTS.md, each leaving behind the rule
that governs it (II, Platform, Development Workflow). (3) Principle II's rationale
is corrected. (4) Principle VI's changelog mandate is removed. No principle is
removed or renamed.

Amendment 4 is the only bump-ambiguous change. Governance defines MAJOR as "a
principle is removed or redefined in a backward-incompatible way", and this does
delete an obligation from VI. It is treated as MINOR because principle VI is
neither removed nor renamed, and the change is a relaxation — nothing that
satisfied 1.2.0 becomes non-compliant, since a PR that still records its API
changes remains fine, merely no longer required to. That matches how this project
bumped its two prior relaxations: 1.1.0 loosened VI's testing rule and 1.2.0's
second amendment raised the AGENTS.md cap, both MINOR on the same reasoning.

Modified principles:
  - II. Two Interfaces, One Contract — the exit code list (0 success, 1 not found,
    2 usage error, 3 workspace error) is replaced by the rule that exit codes MUST
    be meaningful and stable and that renaming or removing one is breaking; the
    registry moves to docs/REQUIREMENTS.md. Separately, the rationale no longer opens
    "The CLI is an assistant's only interface". That stopped being true when
    assistants began editing markdown bodies directly, which the shipped
    CLAUDE.md.tmpl already instructs them to do. It now states what the CLI is
    actually for — creating records and reading structured output, the operations
    where choom's conventions have to hold. No rule under II changes.
  - III. Simplicity Is the Default — gains the directory-layout invariant: date is
    the only axis the tree encodes, and `type` is carried in frontmatter and the
    filename, never as a directory. Stated only in docs/REQUIREMENTS.md until now, and
    therefore ungated, while violating it means migrating every user's vault.
  - IV. Never Lose the User's Words — gains two invariants, both previously
    ungated: choom never moves a user's file to match its partition, and a tag
    MUST NEVER silently vanish (the reason `--tag` is the supported CLI form, since
    `#` opens a comment in bash and zsh).
  - VI. Readable Python, Enforced Automatically — the changelog mandate is removed.
    PRs, and release notes generated from PRs and closed issues, now carry that
    record; requiring a hand-maintained changelog alongside them duplicates it.
  - Platform & Distribution Constraints — the `AGENTS.md` bullet no longer
    enumerates what the file carries; that list moves to docs/REQUIREMENTS.md. The
    content rule and the ~100-line backstop introduced in 1.2.0 are unchanged. The
    enumeration had already drifted: it omitted the link syntax 008 added to the
    shipped template.
  - Development Workflow & Quality Gates — the target-terminal list moves to
    docs/REQUIREMENTS.md; the rule that TUI changes are verified before release stays.

Added sections: none
Removed sections: none

Templates requiring updates:
  ✅ .specify/templates/plan-template.md — gate rows III and IV extended with the
     promoted invariants, so a plan proposing a type-per-directory layout or a
     file-moving migration fails at the gate; gate VI drops "public API changes
     recorded in the changelog"
  ✅ .specify/templates/tasks-template.md — the Polish-phase documentation task
     listed "(README, AGENTS.md, changelog)"; `changelog` removed
  ✅ .specify/templates/spec-template.md — reviewed; left unchanged. No
     constitution-driven mandatory section is added or removed
  ✅ .specify/templates/checklist-template.md — reviewed; left unchanged. It
     carries no guidance that these amendments contradict
  ✅ .claude/skills/speckit-*/SKILL.md — reviewed; left unchanged. None mandates a
     changelog entry, and none restates a registry that moved
  ✅ .claude/skills/changed/SKILL.md — reviewed; left unchanged. It drafts release
     narrative in CHANGELOG.md's style. Amendment 4 removes the obligation to keep
     that file, not the ability to; a skill that produces a draft on request is
     optional tooling and contradicts nothing
  ✅ README.md — changed in this PR, but for its own reason: it is becoming
     public-facing documentation and now links no internal document. It referenced
     docs/REQUIREMENTS.md four times and this constitution zero times

Non-template files:
  ✅ docs/REQUIREMENTS.md — reshaped in this same PR, and NOT retired. Issue #41
     proposed deleting it; the outcome instead was to strip the v0.0.1
     bootstrapping (per-feature acceptance criteria, the out-of-scope list, the
     backlog) and keep the design intent and the living conventions. This
     supersedes the 1.2.0 report's statement that the file "is being retired under
     separate work in flight". Its §4.3 cap, deliberately left divergent at
     "roughly 60 lines" for that reason, is restated to match this document.
     It also moves from the repository root to `docs/`, where it sits alongside
     the other contributor-facing material. References in this document, in
     tasks-template.md, and in the product-owner skill are updated; the citations
     under specs/ are not, for the same reason their section numbers are not —
     they are point-in-time records, accurate as written.

Follow-up TODOs:
  - (Resolved) docs/REQUIREMENTS.md's stale "six commands" count — logged during 1.2.0
    and then withdrawn on the grounds that the file was going away — is fixed here.
  - (Resolved) The "cairn" naming TODO carried from 1.1.0 is withdrawn: README
    names the project "choom" throughout, so there is nothing to reconcile.

Note on 1.2.0's AGENTS.md cap arithmetic:
  - It cited two inputs this PR removes — docs/REQUIREMENTS.md §4.2's promise of `read`,
    `write`, `append` and `find`, and `workspace list/use/current` from the §6.1
    backlog. The four commands are obsolete, since an assistant edits a markdown
    body directly; the backlog moved to issue #18. The cap is not reopened: it is a
    relaxation, and the argument that carried it — a hard cap that forces deleting
    real instructions inverts its own purpose — does not depend on either
    projection.

Migration path:
  - Amendments 1 and 3 (promoted invariants, corrected rationale): none required.
    Both codify what the codebase and every shipped spec already do; no existing
    layout, spec, or test becomes non-compliant.
  - Amendment 2 (registries): none required. No rule changes, and each list is
    restated in docs/REQUIREMENTS.md rather than dropped.
  - Amendment 4 (changelog mandate): none required. A relaxation. CHANGELOG.md is
    left in place and untouched; nothing now requires it to be maintained, and
    whether to retire it is tracked separately.
-->

# choom Constitution

## Core Principles

### I. Core Is the Product

`choom.core` holds all logic: vault resolution, frontmatter parsing, file creation,
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
- Data goes to stdout, errors to stderr. Exit codes MUST be meaningful and stable;
  renaming or removing one is breaking. The registry lives in `docs/REQUIREMENTS.md`.

**Rationale**: The CLI is how an assistant creates records and reads structured output —
the operations where choom's conventions have to hold, and the ones it cannot safely
reproduce by hand. A single interactive prompt or a stray escape sequence on a non-TTY
turns a working automation into a hang or a corrupt parse, and the failure is silent from
the assistant's side.

### III. Simplicity Is the Default (NON-NEGOTIABLE)

Markdown files are the only state choom has. Introducing a second source of truth —
an index, a database, a cache — requires a documented justification in the plan's
Complexity Tracking table, naming the simpler alternative and why it fails.

- No SQLite, no index, no `reindex` command.
- No external binary dependencies for core functionality (no `ripgrep`, no `pandoc`);
  the target machine is locked down and cannot be assumed to have them.
- Prefer the standard library. Every third-party dependency MUST be justified by what it
  would cost to do without.
- Configuration beyond workspace paths is out of scope. A setting that could be a
  sensible default MUST be a sensible default.
- Date is the only axis the directory tree encodes. `type` MUST be carried in frontmatter
  and in the filename, never as a directory — types are free-form and user-invented, so a
  directory per type would fragment the vault into a long tail of one-file folders. Date
  is the only attribute every file has exactly one of.

**Rationale**: At hundreds to low thousands of files, a full scan costs a fraction of a
second — cheaper than the invalidation logic, staleness bugs, and corruption risk an
index introduces. A database file inside a OneDrive-synced folder is a genuine corruption
hazard, and the simplest way to avoid it is to not have one.

### IV. Never Lose the User's Words

Users hand-edit their files, in choom and elsewhere. Every parser and writer MUST
treat that as the normal case:

- Malformed input is skipped and logged, never fatal. A broken metadata comment on one
  task line MUST NOT prevent the rest of the file from parsing.
- A parse failure MUST NEVER lose a line or truncate a file.
- Missing metadata is repaired in place — a checkbox with no id gets one written back,
  without disturbing surrounding lines.
- Files stay valid CommonMark. Metadata rides in HTML comments and frontmatter so that
  any markdown viewer renders the file correctly.
- Writes preserve `created` and update `updated`. Never the reverse.
- choom MUST NEVER move a user's file to match its partition. A file the user has filed
  under the wrong month still lists — its date comes from frontmatter, never from its path.
- A tag MUST NEVER silently vanish. `#` opens a comment in bash and zsh, so an unquoted
  `#tag` is discarded by the shell before choom sees it; `--tag` is therefore the
  supported CLI form, and both `--help` and `AGENTS.md` MUST state it explicitly.

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
- Tests use `pytest` and run against `core` without a terminal. Coverage is risk-based:
  every user-facing behaviour MUST be covered, but the author chooses where — the layer
  and the number of tests are driven by what could plausibly break, not generated
  mechanically from the spec's acceptance scenarios. A spec with ten acceptance scenarios
  for one behaviour does not require ten tests. `contract/` covers the CLI's AI-facing
  surface (`--json` schema, exit codes, stream separation, non-blocking behaviour);
  `integration/` covers one end-to-end path per user story, parametrized across CLI and
  TUI adapters rather than duplicated into separate files; `unit/` covers `core` logic
  worth isolating (parsing, id generation); `performance/` covers only scenarios with a
  real budget to protect. A behaviour does not get re-verified at every layer it touches.
- Tests MUST NOT depend on the wall clock. A meeting fixture dated 20 July, listed by a
  pane that shows the current month, passes every day of July and returns an empty list on
  1 August — nothing changed but the date, and it breaks for whoever pushes next rather
  than whoever wrote it. Derive such dates from the same clock the behaviour reads.
- Prefer a plain function to a class, a class to a framework, and an explicit branch to a
  clever abstraction. Names say what the thing is; comments explain only why.

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
- `AGENTS.md` is generated at `init`. It carries what `docs/REQUIREMENTS.md` lists, and nothing
  an assistant could infer from the workspace itself. It does not restate the README. That
  content rule is what binds; roughly 100 lines is its checkable backstop, not a budget to
  be spent. Short, human-curated, genuinely non-obvious guidance is what helps an
  assistant, and a bloated file measurably raises exploration cost. A real instruction that
  pushes the file past the cap means the whole file gets reviewed for content that has
  stopped earning its place — never that the instruction is dropped to fit under a number.

## Development Workflow & Quality Gates

- Specs precede plans, plans precede tasks, tasks precede code.
- The Constitution Check in `plan.md` MUST pass before Phase 0 research and be re-checked
  after Phase 1 design. Violations are either fixed or justified in the Complexity
  Tracking table — an empty justification is a failed gate.
- Every pull request MUST pass formatting, linting, type checking, and the test suite
  before review.
- Behaviour changes MUST land with the tests that cover them and the documentation that
  describes them, in the same change.
- TUI changes MUST be verified before release on the target terminals listed in
  `docs/REQUIREMENTS.md`.
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

`docs/REQUIREMENTS.md` holds choom's design intent and its living conventions — the
frontmatter schema, the id scheme, the file layout, the task line format, link semantics,
the exit code registry, and the target terminals — and is expected to change as features
ship. `AGENTS.md` in a workspace holds runtime guidance for AI assistants. Neither
overrides this document.

**Version**: 1.3.0 | **Ratified**: 2026-07-28 | **Last Amended**: 2026-07-31
