from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Literal


@dataclass(frozen=True, slots=True)
class Workspace:
    root: Path

    @property
    def meetings_dir(self) -> Path:
        return self.root / "meetings"

    @property
    def notes_dir(self) -> Path:
        return self.root / "notes"

    @property
    def daily_dir(self) -> Path:
        return self.root / "notes" / "daily"

    @property
    def tasks_file(self) -> Path:
        return self.root / "tasks.md"


@dataclass(frozen=True, slots=True)
class Document:
    id: str
    path: Path
    title: str
    type: str
    tags: tuple[str, ...]
    created: str
    updated: str


Meeting = Document
Note = Document


@dataclass(frozen=True, slots=True)
class YearMonth:
    year: int
    month: int

    def __str__(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"


@dataclass(frozen=True, slots=True)
class MonthListing:
    months: tuple[YearMonth, ...]
    has_unfiled: bool


@dataclass(frozen=True, slots=True)
class Collection:
    id_prefix: str
    create_dir: str
    scan_dirs: tuple[str, ...]
    reserved_types: frozenset[str]


@dataclass(frozen=True, slots=True)
class DailyNote:
    path: Path
    document: Document | None
    created: bool


ScanWarningReason = Literal[
    "no_frontmatter",
    "unterminated_frontmatter",
    "malformed_yaml",
    "not_a_mapping",
    "missing_fields",
    "unexpected_fields",
    "invalid_value",
    "task_unterminated_comment",
    "task_malformed_comment",
    "task_invalid_value",
    "link_dead",
    "link_ambiguous",
    "mirror_conflict",
    "mirror_ambiguous",
    "reply_capture_failed",
]


@dataclass(frozen=True, slots=True)
class ScanWarning:
    path: Path
    reason: ScanWarningReason
    message: str


@dataclass(frozen=True, slots=True)
class DocumentFilter:
    type: str | None = None
    tags: tuple[str, ...] = ()
    since: date | None = None


MeetingFilter = DocumentFilter


@dataclass(frozen=True, slots=True)
class EditableFile:
    path: Path
    text: str
    newline: str
    trailing_newline: bool


@dataclass(frozen=True, slots=True)
class UrlConversion:
    """One bare-URL-to-markdown-link edit `format_bare_urls` made, as offsets into
    the *original* text it was given (018-automatic-link-detection). `start`/`end`
    bound the matched URL; `replacement` is what was spliced in its place --
    `[url](destination)`. Never persisted: recomputed from the text on every save."""

    start: int
    end: int
    url: str
    replacement: str


@dataclass(frozen=True, slots=True)
class SaveResult:
    ok: bool
    saved_text: str
    stamped: bool
    message: str
    warnings: tuple[ScanWarning, ...] = ()
    conversions: tuple[UrlConversion, ...] = ()


@dataclass(frozen=True, slots=True)
class InitResult:
    workspace: Workspace
    written: tuple[str, ...]
    skipped: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Task:
    id: str | None
    text: str
    done: bool
    type: str
    tags: tuple[str, ...]
    created: date | None
    line: int
    links: tuple[str, ...] = ()
    body: str = ""


@dataclass(frozen=True, slots=True)
class TaskBodySpan:
    """A task's body location within `ParsedTasks.lines`, positionally aligned
    with `ParsedTasks.tasks`. Internal to the parser and the writer -- never
    exposed by the CLI or the TUI."""

    start: int
    end: int
    indent: str


@dataclass(frozen=True, slots=True)
class ParsedTasks:
    tasks: tuple[Task, ...]
    warnings: tuple[ScanWarning, ...]
    lines: tuple[str, ...]
    needs_id: tuple[int, ...]
    bodies: tuple[TaskBodySpan, ...] = ()


@dataclass(frozen=True, slots=True)
class TaskFilter:
    type: str | None = None
    tags: tuple[str, ...] = ()
    include_done: bool = False
    only_done: bool = False


LinkStatus = Literal["resolved", "stale", "dead"]
LinkDirection = Literal["out", "in", "both"]


@dataclass(frozen=True, slots=True)
class Link:
    """One directed reference, as found in a source file. `start`/`end` are character
    offsets into the text it was found in, so a repair can splice a new destination
    into the original string and change nothing else. At least one of `path` and
    `target_id` is not None -- a `[text]()` with an empty destination is not a link
    and is never collected."""

    source: Path
    line: int
    text: str
    path: str | None
    target_id: str | None
    start: int
    end: int
    in_tasks_field: bool = False


@dataclass(frozen=True, slots=True)
class LinkReport:
    """What `links check` and `links heal` emit for one link. Field names are the
    fixed JSON keys of the CLI contract."""

    file: Path
    line: int
    text: str
    target_id: str | None
    old_path: str | None
    new_path: str | None
    status: LinkStatus


@dataclass(frozen=True, slots=True)
class LinkTarget:
    """The resolved other end of a link. A link can point at a document or at a
    task, and the two live in different places, so resolution returns this small
    union rather than a Document."""

    id: str
    path: Path
    title: str
    kind: Literal["meeting", "note", "task"]
    line: int | None


@dataclass(frozen=True, slots=True)
class LinkCandidate:
    """One record a `/link` search matched, with the facts a picker row needs.

    Wraps `LinkTarget` rather than extending it: a link's resolved destination and
    a row in a chooser are different jobs, and `LinkTarget` is built in a dozen
    places that have nothing to do with choosing.
    """

    target: LinkTarget
    collection: str
    date: str | None


MirrorOutcome = Literal[
    "unchanged", "task_written", "mirror_corrected", "conflict", "ambiguous", "dead"
]


@dataclass(frozen=True, slots=True)
class Mirror:
    """One recognised mirror -- a checklist line in a document that is also a
    link to a task. Frozen; produced by scanning (`find_mirrors`), never
    constructed by a caller.

    `state_offset` is the load-bearing field: it is the character offset of
    the single state character in the document text, so applying a state is
    always `text[:o] + char + text[o+1:]` -- no line is ever re-rendered.

    `link_start`/`link_end` are the character offsets of the mirror's own
    link -- the same `Link` this was selected from (017-editor-task-delete).
    They exist so a caller deciding whether a line carries text beyond its
    checkbox and its task link (FR-011) reads the answer `find_mirrors`
    already computed rather than re-scanning the line for it, which would be
    a second, divergent definition of which link is the mirror (FR-005,
    FR-007)."""

    task_id: str
    done: bool
    line: int
    state_offset: int
    text: str
    link_start: int
    link_end: int


@dataclass(frozen=True, slots=True)
class MirrorResolution:
    """What was decided for one task during a reconcile pass."""

    task_id: str
    outcome: MirrorOutcome
    done: bool | None
    message: str = ""


@dataclass(frozen=True, slots=True)
class MirrorReport:
    """The result of a reconcile or propagate call.

    `text` is the *same object* as the input when nothing needed correcting,
    so a caller can test identity to decide whether a write is needed at all
    (FR-030)."""

    text: str
    resolutions: tuple[MirrorResolution, ...]
    warnings: tuple[ScanWarning, ...]


MirrorDeletionOutcome = Literal[
    "deletable", "line_only", "unreadable_tasks", "ambiguous_id", "self_referential"
]


@dataclass(frozen=True, slots=True)
class MirrorDeletion:
    """What deleting the task line at one cursor position would do
    (017-editor-task-delete), decided by `mirrors.plan_mirror_deletion` and
    carried out by `mirrors.commit_mirror_deletion`. Never persisted -- it
    lives for the length of one keystroke.

    `text` and `span` describe the same single removal:
    `text == original[:span[0]] + original[span[1]:]`. `text` is what a
    non-widget caller uses; `span` is what the TUI converts to widget
    coordinates so the removal is one undoable `TextArea.delete` rather than
    a re-render (Principle IV, FR-017, FR-018). Both are `""` / `(0, 0)` on a
    refusing outcome, since nothing is removed.

    `message` names why a refusing outcome was refused and what to do about
    it (Principle V); it is `""` for `deletable` and `line_only`, which need
    no explanation."""

    outcome: MirrorDeletionOutcome
    task_id: str
    description: str
    text: str
    span: tuple[int, int]
    extra_text: bool
    message: str = ""


@dataclass(frozen=True, slots=True)
class EditorCommand:
    name: str
    argument: str
    description: str
    requires_argument: bool
    accepts_suffix: bool = False


@dataclass(frozen=True, slots=True)
class ParsedCommand:
    command: EditorCommand
    argument: str
    suffix: str = ""


@dataclass(frozen=True, slots=True)
class AssistantProfile:
    name: str
    display_name: str
    binary: str
    build_args: Callable[[str], list[str]]
    parse_reply: Callable[[str], str]
    #: The discovery file's path relative to the user's profile root (013-assistant-
    #: discovery-file, research R1-R3), or None when this assistant has no user-scope
    #: location that it reads regardless of working directory (FR-017) -- a case that
    #: exists in the type so a future profile can express it without a crash, though
    #: neither assistant supported today hits it (research R2).
    discovery_relpath: PurePosixPath | None = None


@dataclass(frozen=True, slots=True)
class ResolvedAssistant:
    profile: AssistantProfile | None
    source: str  # configured | detected | none | unset | ambiguous
    available: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AssistantReply:
    ok: bool
    text: str
    message: str
    cancelled: bool


@dataclass(frozen=True, slots=True)
class ReplyLine:
    """One line of an assistant reply, classified by `parse_reply_lines`.

    `text` is the line exactly as the assistant wrote it, without its line
    terminator, and is never modified by the classifier. `task` is the parsed
    task command when the line is eligible for capture -- outside any fenced
    code block, with no leading whitespace, and naming the `task` command --
    and `None` for every other line, including an ineligible `/task` mention.
    A non-`None` `task` may still be unusable (e.g. `/task` with no
    description); the classifier does not judge that, only `capture_task`
    does."""

    text: str
    task: ParsedCommand | None


@dataclass(frozen=True, slots=True)
class ReplyCapture:
    """The outcome of walking one reply with `capture_reply_tasks`.

    `text` is the reply with every successfully captured line replaced by its
    mirror line and every other line byte-identical to the input -- the same
    object as the input when no line was captured (FR-011), so a caller can
    test identity. `tasks` holds the tasks created, in the order their lines
    appeared in the reply. `warnings` holds one entry per line that was
    eligible but could not be captured. `len(tasks) + len(warnings)` equals
    the number of eligible lines."""

    text: str
    tasks: tuple[Task, ...]
    warnings: tuple[ScanWarning, ...]
