# Phase 0 Research: Assistant Discovery File

**Feature**: 013-assistant-discovery-file | **Date**: 2026-08-01

Every unknown the spec deliberately left to planning, resolved. The spec fixed behaviour; this fixes
spelling — paths, file formats, and where each piece of logic lands.

---

## R1 — Where Claude Code reads from, regardless of working directory

**Decision**: `~/.claude/skills/choom/SKILL.md`, a user-scope skill. The file carries YAML
frontmatter with `name` and `description`, then a short markdown body.

**Rationale**: User-scope skills live under the user's `~/.claude` profile directory and are
available in every session irrespective of the working directory, which is exactly FR-001's
requirement. The format is not guesswork: this repository already contains user-authored skills at
`.claude/skills/*/SKILL.md`, and their frontmatter is `name` + `description` (plus optional keys we
do not need). `description` is the field an assistant matches against when deciding whether a skill
is relevant, so it must say what choom is and when the skill applies — which is the discovery
mechanism itself, not decoration.

**Alternatives considered**:

- `~/.claude/CLAUDE.md` (user-scope memory). Rejected: it is the user's own file, hand-maintained,
  and often already populated. Appending to it means merging into content choom does not own and
  cannot safely rewrite in full — which FR-006 requires and FR-010 forbids doing to another file.
- A project-scope file. Rejected by the premise: the whole problem is that the assistant is started
  outside the workspace.

## R2 — Where GitHub Copilot CLI reads from, regardless of working directory

**Decision**: `~/.copilot/instructions/choom.instructions.md`.

**Rationale**: Copilot CLI's changelog documents `~/.copilot/instructions/*.instructions.md` as
"user-level instructions across all repositories", and lists that glob under `/help` alongside the
other instruction locations. That is the same guarantee the Claude skill gives: read on every
session, independent of the working directory. Confirmed against Copilot CLI documentation rather
than assumed, because the spec's FR-017 branch turns on whether such a location exists at all.

**Alternatives considered**:

- `~/.copilot/agents/*.json` (custom agents). Rejected: an agent is invoked deliberately with
  `/agent`; it is not ambient context, so it would not be read unless the user already knew to ask
  for it — which defeats discovery.
- `~/.copilot/settings.json`. Rejected: settings, not instructions; nothing there reaches the model
  as context.

**Consequence for FR-017**: both supported assistants have a location, so the "no location that
fits" branch is unreachable today. It is still implemented, because `AssistantProfile` is the
extension point for future assistants and a `None` there must not crash the install path.

## R3 — Resolving the user's profile directory across platforms

**Decision**: `pathlib.Path.home()`, with the two locations expressed as profile-relative paths on
`AssistantProfile`.

**Rationale**: `Path.home()` resolves `%USERPROFILE%` on Windows and `$HOME` elsewhere, standard
library only, no new dependency (Principle III). Both target paths are short — `.claude/skills/
choom/SKILL.md` is 30 characters — so they consume almost none of the Windows 260-character budget;
the long path in this feature is the *workspace path written inside the file*, which is content, not
a path choom has to open.

**Alternatives considered**: `platformdirs`. Rejected: a third-party dependency for one call, and
these two tools define their own locations under the home directory rather than following XDG or
Known Folder conventions, so a cross-platform directory library would compute the wrong answer.

## R4 — Where the per-assistant knowledge lives

**Decision**: extend the existing `AssistantProfile` in `core/assistants.py` with the profile-
relative path of its discovery file, and put the rendering and install/remove logic in a new
`core/discovery.py`.

**Rationale**: `AssistantProfile` already models exactly this — the per-assistant differences
(`binary`, `build_args`) behind one shape the adapters never branch on. Adding the discovery
location there means the CLI and the TUI keep calling one core function and never learn which
assistant they are dealing with (Principle I). A profile whose location is `None` is FR-017's case,
expressed in the type rather than in an `if` at each call site.

`core/discovery.py` rather than more of `assistants.py`: `assistants.py` is about *invoking* an
assistant — process spawning, cancellation, reply normalisation. Installing a file into a profile
directory shares none of that machinery. Keeping them apart keeps both readable (Principle VI).

## R5 — Recording that the offer was made

**Decision**: a second key in the existing `[assistant]` table of the workspace's
`.choom/config.toml`, written through a generalised form of `config.py`'s existing line-targeted
edit.

**Rationale**: The spec directs the record to the workspace configuration, and the assistant setting
it qualifies is already in that table. `_apply_assistant_value` today does a careful line-targeted
edit that preserves comments, key order, and unknown keys — Principle IV's requirement — via three
cases (replace the `name` line, insert it into an existing table, append the whole table). Writing a
second key needs exactly the same three cases, so the fix is to generalise that private helper to
take a key name rather than to write a second regex block beside it. One edit path, one place for a
bug to live.

Read side mirrors `get_assistant`: never raises, treats a missing file, missing table, malformed
TOML, or a non-boolean value as "not offered", so a hand-edited config cannot stop choom opening.

**Alternatives considered**:

- A separate state file in the user's profile. Rejected: it contradicts the spec's explicit
  direction, and would split one decision across two stores.
- A sentinel inside the discovery file itself. Rejected: it cannot represent "offered and declined",
  because declining writes no file.

## R6 — Where the launch offer is raised in the TUI

**Decision**: in `ChoomApp.on_mount`, after `push_screen(ListScreen())`, deferred with
`call_after_refresh` so the list is mounted and painted first (FR-034). The dialog is
`ConfirmDialog`, pushed with a dismiss callback, exactly as `list_screen.py` pushes it for delete.

**Rationale**: The offer belongs to the session, not to a screen — `ListScreen` is re-entered on
every resume, and raising it there would need suppression logic to avoid re-asking within one run.
`on_mount` runs once. Deferring past the first refresh is what makes "the app is up and usable
behind the question" true rather than merely claimed.

Popping the dialog triggers `ListScreen.on_screen_resume`, which already re-reads and re-renders;
this is why the outcome message is handed over as a pending status rather than rendered directly —
`list_screen.py`'s own comment records that two independent refreshes race and the loser's status
text is silently overwritten. The delete path solved this with `_pending_error`; the offer reuses
that mechanism rather than inventing a second one.

**Alternatives considered**:

- Raising it in `ListScreen.on_mount`. Rejected for the re-entry problem above.
- Raising it lazily at first `/ai` use. Rejected: that is precisely when the user wants an answer,
  not a question, and it would not help an assistant started outside choom entirely.

## R7 — Two outcomes, not three

**Decision**: `Enter` installs; `Esc` installs nothing; the record is written on either key, so the
question is asked at most once per workspace.

**Rationale**: This is forced by `011-ui-refinements`, merged into main: `ConfirmDialog` offers
exactly two options (011 FR-022) and `Esc` must change nothing about the request it interrupted (011
FR-023). A durable "no" carried by `Esc` would give that key a meaning it has nowhere else in the
tool; a third "ask me later" option would need a second dialog style, which 011 FR-026 forbids.
Recording *that the offer was made* satisfies both constraints and still delivers the spec's
requirement that a user who declines is not re-prompted at every launch.

The dialog therefore does not re-ask after a failed install either (spec edge case): a profile
directory that is permanently unwritable would otherwise raise the same question at every launch,
which is the nagging the once-only rule exists to prevent.

**Alternatives considered**: extending `ConfirmDialog` with a third option. Rejected: it is "the one
confirmation in the product" by its own docstring, and widening it for one caller regresses the
consistency 011 was written to achieve.

## R8 — What the CLI prints on a successful set

**Decision**: the discovery-file outcome goes to **stderr**; stdout stays empty on a set. Exit code
is unchanged from today's `0`.

**Rationale**: Principle II is explicit — data to stdout, diagnostics to stderr — and 011 set the
precedent for mutations in this codebase: its delete command "MUST exit 0 and write nothing to
stdout". A set command that started printing a path to stdout would break any script that pipes it,
for a message that is confirmation rather than data. Sending it to stderr satisfies FR-015 without
touching the machine-readable surface.

FR-013's separation falls out of the same choice: the setting write decides the exit code, and the
discovery-file result — success or failure — is reported alongside it on stderr.

## R9 — Machine-readable additions

**Decision**: `config assistant --json` gains `discovery_file` (absolute path string, or `null`) and
`launch_offer_made` (boolean). No existing key changes.

**Rationale**: Principle II makes adding a key a minor change and renaming or removing one breaking,
so additive is the whole design constraint. `discovery_file` answers FR-016 and `launch_offer_made`
answers FR-033; both are readable without opening the TUI, which is what makes the launch offer's
state testable from a contract test.

## R10 — The discovery file's content

**Decision**: one generated body per assistant, differing only in the wrapper each tool expects
(frontmatter keys for the skill, a plain heading for the instructions file). Inside: what choom is
in one line, the absolute workspace path, the instruction to read that workspace's `AGENTS.md`
before creating or changing anything, and a generated-by marker naming the command that rewrites it.
Target 12–16 lines, hard backstop 20 (FR-004).

**Rationale**: FR-003 forbids restating `AGENTS.md`, which is where the real content already lives
and is regenerated per workspace. What cannot be inferred by following the pointer is only: that
choom exists, where this workspace is, and that the instructions are in it. The generated-by marker
does double duty — it satisfies FR-005 and it is the check that makes removal safe (R11).

The workspace path is written on its own line, unwrapped, so a path containing spaces or non-ASCII
characters is unambiguous without quoting rules the reader has to know (FR-018).

## R11 — Keeping exactly one file, safely

**Decision**: on install, write the configured assistant's file and remove the other assistants'
choom-owned paths — but remove a file only if it exists *and* contains the generated-by marker.

**Rationale**: FR-008 wants one file; FR-010 forbids touching anything choom did not write. The
marker makes those compatible: a file at our path without our marker is somebody else's and is left
alone with a warning, rather than deleted on the strength of its filename. Overwriting our own path
needs no such check — FR-006 requires a full rewrite — but deletion is irreversible and gets the
stricter test.

## R12 — Test placement

**Decision**:

- `tests/unit/` — path resolution per profile, rendered content (marker present, no `AGENTS.md`
  restatement, line budget, path with spaces and non-ASCII), the config read/write of the new key
  (including malformed and hand-edited files), and the one-file invariant including the
  marker-guarded removal.
- `tests/contract/` — the CLI's AI-facing surface: the two new `--json` keys, stdout empty on set,
  the message and exit code when the profile directory is unwritable, and that a read writes
  nothing.
- `tests/integration/` — one end-to-end pass of the launch offer through the TUI: offered once,
  `Enter` installs, `Esc` does not, and neither is asked again.

**Rationale**: Principle VI's coverage is risk-based and placed at the layer where the risk lives,
not generated one-per-acceptance-scenario. The risks here are: computing the wrong path, writing
content that violates its own content rule, corrupting a hand-edited config, deleting a file that
was not ours, and asking the question twice. Each of those has exactly one home above.

No test may depend on the wall clock; nothing in this feature reads a date, so the rule costs
nothing here beyond not introducing one.

## R13 — Isolating the tests from the developer's real profile

**Decision**: tests resolve the profile root through a single seam — the same function the
implementation calls — and monkeypatch it to a `tmp_path`. No test may write to the real
`~/.claude` or `~/.copilot`.

**Rationale**: This is the one genuinely dangerous thing in the feature: a test suite that installs
and deletes files in the profile directory of whoever runs it. Routing every profile-relative path
through one function makes the seam obvious and the monkeypatch total, rather than leaving each test
to remember. A `conftest.py` autouse fixture makes it the default, so a new test cannot forget.
