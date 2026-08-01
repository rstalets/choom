"""The document-links primitive: everything a link needs, in one module.

A link is an ordinary CommonMark inline link, ``[text](path#id)``, whose ``#id``
fragment is authoritative and permanent and whose path is derived, computed by
choom, and repaired when it goes stale (see contracts/link-format.md). This
module holds the scanner, the id/path resolver, path derivation, the healer, and
the inbound-link scan together, deliberately: they are four views of one grammar,
and splitting them across files is how a byte-preservation guarantee gets quietly
broken (see plan.md, Structure Decision). Nothing here is persisted -- inbound
links are recomputed by scanning every time they are asked for.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from choom.core.atomic_write import write_text_atomic
from choom.core.documents import _read_document, match_document
from choom.core.editing import _apply_line_ending_policy, load_for_edit
from choom.core.meetings import scan_meetings
from choom.core.models import (
    EditableFile,
    Link,
    LinkDirection,
    LinkReport,
    LinkStatus,
    LinkTarget,
    ScanWarning,
    Task,
    Workspace,
)
from choom.core.notes import scan_notes
from choom.core.tasks import load_tasks, match_task, parse_tasks
from choom.core.text import _split_terminator

# --- Scanning -----------------------------------------------------------------

_FENCE_RE = re.compile(r"^[ ]{0,3}(?P<run>`{3,}|~{3,})(?P<rest>.*)$")
_BACKTICK_RUN = re.compile(r"`+")
_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_NEEDS_ESCAPE = re.compile(r"[ ()<>]")

_LINK_RE = re.compile(
    r"""
    (?<!!)                       # not an image
    \[(?P<text>[^\[\]]*)\]
    \(
        [ \t]*
        (?P<dest>
            <[^<>\n]*>
            |
            [^\s()]*
        )
        [ \t]*
    \)
    """,
    re.VERBOSE,
)


def _mask_fences(text: str) -> str:
    """Replace the contents of fenced code blocks (``` or ~~~, including the fence
    lines themselves) with spaces, preserving length and line terminators exactly.
    An unclosed fence is masked to end of file. A fence line's info string is never
    mistaken for a closing fence because a close requires nothing but whitespace
    after the run."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    fence_char: str | None = None
    fence_len = 0

    for line in lines:
        content, terminator = _split_terminator(line)
        if fence_char is None:
            match = _FENCE_RE.match(content)
            if match:
                fence_char = match.group("run")[0]
                fence_len = len(match.group("run"))
                out.append(" " * len(content) + terminator)
                continue
            out.append(line)
            continue

        match = _FENCE_RE.match(content)
        if (
            match
            and match.group("run")[0] == fence_char
            and len(match.group("run")) >= fence_len
            and content[len(content) - len(match.group("rest")) :].strip() == ""
        ):
            out.append(" " * len(content) + terminator)
            fence_char = None
            fence_len = 0
            continue
        out.append(" " * len(content) + terminator)

    return "".join(out)


def _mask_code_spans(text: str) -> str:
    """Blank inline code spans using CommonMark's equal-length-backtick-run rule:
    an opening run is closed by the next run of the same length. An unmatched run
    is literal content, not a code span, and is left alone."""
    runs = list(_BACKTICK_RUN.finditer(text))
    out = list(text)
    i = 0
    while i < len(runs):
        opener = runs[i]
        opener_len = len(opener.group())
        closer = None
        for j in range(i + 1, len(runs)):
            if len(runs[j].group()) == opener_len:
                closer = runs[j]
                break
        if closer is None:
            i += 1
            continue
        for k in range(opener.start(), closer.end()):
            if out[k] not in ("\n", "\r"):
                out[k] = " "
        i += 1
        while i < len(runs) and runs[i].start() < closer.end():
            i += 1

    return "".join(out)


def _dest_content(raw_dest: str) -> str:
    if raw_dest.startswith("<") and raw_dest.endswith(">"):
        return raw_dest[1:-1]
    return raw_dest


def _link_from_match(text: str, match: re.Match[str], source: Path) -> Link | None:
    dest = _dest_content(match.group("dest"))
    if not dest:
        return None

    path_part, sep, frag = dest.partition("#")
    if path_part and _SCHEME_RE.match(path_part):
        return None

    target_id = frag if sep and frag else None
    path = path_part if path_part else None
    if path is None and target_id is None:
        return None

    line_no = text.count("\n", 0, match.start()) + 1
    return Link(
        source=source,
        line=line_no,
        text=match.group("text"),
        path=path,
        target_id=target_id,
        start=match.start(),
        end=match.end(),
        in_tasks_field=False,
    )


def _scan_body_links(text: str, source: Path) -> list[tuple[Link, re.Match[str]]]:
    masked = _mask_code_spans(_mask_fences(text))
    results: list[tuple[Link, re.Match[str]]] = []
    for match in _LINK_RE.finditer(masked):
        link = _link_from_match(text, match, source)
        if link is not None:
            results.append((link, match))
    return results


def find_links(text: str, *, source: Path) -> tuple[Link, ...]:
    """Every CommonMark inline link in `text` that could name a record.

    Skips images, destinations carrying a URL scheme, and anything inside a
    fenced code block or an inline code span -- those are content, not links.
    Reference-style links (``[a][ref]``) are not recognised; choom never
    writes one.

    Each Link carries `start`/`end` character offsets into `text`, so a caller
    can splice a replacement destination in without re-rendering the document.

    Never raises. Any input is valid input.
    """
    return tuple(link for link, _match in _scan_body_links(text, source))


def find_task_links(value: str, *, source: Path, line: int, text: str) -> tuple[Link, ...]:
    """Parse one task's ``links:`` field value -- bare comma-separated ids,
    never markdown syntax, since a task line is already one line of metadata
    and the id prefix says which collection to look in -- into `Link` records.

    `value` is the raw field value, e.g.
    ``"meeting_20260728_a1b2c3d4,note_20260731_ff00ff00"``. `line` and `text`
    are the task's own line number and description; every returned `Link`
    carries them directly, so a caller never has to patch them in afterward.

    A separate function from `find_links` rather than a mode flag on it: the
    two parse entirely different grammars (CommonMark inline links with a
    code mask, versus a bare comma-separated list) and share only a return
    type.

    Never raises. Any input is valid input.
    """
    links: list[Link] = []
    pos = 0
    for token in value.split(","):
        start = pos
        end = start + len(token)
        pos = end + 1
        if not token:
            continue
        links.append(
            Link(
                source=source,
                line=line,
                text=text,
                path=None,
                target_id=token,
                start=start,
                end=end,
                in_tasks_field=True,
            )
        )
    return tuple(links)


# --- Path derivation ------------------------------------------------------------


def relative_destination(source: Path, target: Path) -> str:
    """The link destination path from `source`'s directory to `target`.

    Forward slashes on every platform, because a link destination is a URL and a
    Windows-authored ``\\`` does not resolve for a colleague on macOS. Pure
    string arithmetic on two paths; touches no filesystem. Never raises.
    """
    rel = os.path.relpath(target, source.parent)
    return rel.replace(os.sep, "/")


def _render_destination(dest: str) -> str:
    if _NEEDS_ESCAPE.search(dest):
        return f"<{dest}>"
    return dest


def format_link(source: Path, target: LinkTarget, text: str) -> str:
    """A complete markdown link from `source`'s directory to `target`, with
    `text` as the link text. Used by `/link` insertion so the editor and the
    healer agree on how a destination is escaped. Never raises.
    """
    dest_path = relative_destination(source, target.path)
    dest = f"{dest_path}#{target.id}"
    return f"[{text}]({_render_destination(dest)})"


# --- Resolution -------------------------------------------------------------


def resolve_id(
    workspace: Workspace, target_id: str
) -> tuple[LinkTarget | None, tuple[ScanWarning, ...]]:
    """Find the record `target_id` names, searching documents and then tasks.md.

    The id prefix says which collection to look in, so a full workspace scan is
    avoided where the prefix is recognised. Ids are compared whole, never split
    or offset-parsed, so ids written under the old single-letter scheme resolve
    unchanged.

    Returns (None, ()) when nothing carries the id -- that is `dead`, a valid
    state, not an error. When two records carry the same id, returns the first
    in path-sort order plus a `link_ambiguous` warning naming every path.

    Never raises.
    """
    warnings: list[ScanWarning] = []
    candidates: list[LinkTarget] = []

    pools: tuple[str, ...]
    if target_id.startswith("meeting_"):
        pools = ("meeting",)
    elif target_id.startswith("note_"):
        pools = ("note",)
    elif target_id.startswith("task_"):
        pools = ("task",)
    else:
        pools = ("meeting", "note", "task")

    if "meeting" in pools:
        documents, scan_warnings = scan_meetings(workspace)
        warnings.extend(scan_warnings)
        for document in documents:
            if document.id == target_id:
                candidates.append(
                    LinkTarget(
                        id=document.id,
                        path=document.path,
                        title=document.title,
                        kind="meeting",
                        line=None,
                    )
                )

    if "note" in pools:
        documents, scan_warnings = scan_notes(workspace)
        warnings.extend(scan_warnings)
        for document in documents:
            if document.id == target_id:
                candidates.append(
                    LinkTarget(
                        id=document.id,
                        path=document.path,
                        title=document.title,
                        kind="note",
                        line=None,
                    )
                )

    if "task" in pools:
        tasks, task_warnings = load_tasks(workspace)
        warnings.extend(task_warnings)
        for task in tasks:
            if task.id == target_id:
                candidates.append(
                    LinkTarget(
                        id=task.id,
                        path=workspace.tasks_file,
                        title=task.text,
                        kind="task",
                        line=task.line,
                    )
                )

    if not candidates:
        return None, tuple(warnings)

    candidates.sort(key=lambda t: str(t.path))
    if len(candidates) > 1:
        paths = ", ".join(str(c.path) for c in candidates)
        warnings.append(
            ScanWarning(
                path=candidates[0].path,
                reason="link_ambiguous",
                message=f"id {target_id!r} is carried by more than one record: {paths}",
            )
        )
    return candidates[0], tuple(warnings)


def _resolve_path_target(workspace: Workspace, candidate: Path) -> LinkTarget | None:
    if not candidate.is_file():
        return None

    kind: str | None = None
    for directory, name in (
        (workspace.meetings_dir, "meeting"),
        (workspace.notes_dir, "note"),
    ):
        try:
            candidate.relative_to(directory)
        except ValueError:
            continue
        kind = name
        break
    if kind is None:
        return None

    document = _read_document(candidate)
    if document is None:
        return None
    if kind == "meeting":
        return LinkTarget(
            id=document.id, path=document.path, title=document.title, kind="meeting", line=None
        )
    return LinkTarget(
        id=document.id, path=document.path, title=document.title, kind="note", line=None
    )


def resolve_link(workspace: Workspace, link: Link) -> tuple[LinkTarget | None, LinkStatus]:
    """Resolve one link, id first and path second.

    Returns the target and what is currently true of the link:
      resolved -- id resolves and the path already points at it
      stale    -- id resolves but the path is wrong or absent, or the fragment
                  is absent and the path resolves
      dead     -- neither the id nor the path names anything

    A link from a task's `links:` field never carries a path, so it can only be
    `resolved` or `dead` -- there is nothing to repair.

    Never raises.
    """
    if link.target_id is not None:
        target, _warnings = resolve_id(workspace, link.target_id)
        if target is None:
            return None, "dead"
        if link.in_tasks_field:
            return target, "resolved"
        expected = relative_destination(link.source, target.path)
        if link.path == expected:
            return target, "resolved"
        return target, "stale"

    if link.path is None:
        return None, "dead"

    candidate = Path(os.path.normpath(link.source.parent / link.path))
    target = _resolve_path_target(workspace, candidate)
    if target is None:
        return None, "dead"
    return target, "stale"


# --- Healing ------------------------------------------------------------------


def heal_text(
    workspace: Workspace,
    text: str,
    *,
    source: Path,
) -> tuple[str, tuple[LinkReport, ...], tuple[ScanWarning, ...]]:
    """Rewrite every stale link in `text`; leave every dead link byte-identical.

    A byte-level splice of link destinations only. Link text, surrounding prose,
    and line endings are untouched; the document is never round-tripped through
    a parser.

    Returns the new text, a report per link that was stale or dead, and a
    warning per dead link. `text` is returned unchanged when nothing is stale,
    so a caller can compare identity to decide whether a write is needed at all.

    Never raises. A dead link is reported, not fatal.
    """
    scanned = _scan_body_links(text, source)
    if not scanned:
        return text, (), ()

    reports: list[LinkReport] = []
    warnings: list[ScanWarning] = []
    edits: list[tuple[int, int, str]] = []

    for link, match in scanned:
        target, status = resolve_link(workspace, link)

        if status == "dead":
            reports.append(
                LinkReport(
                    file=source,
                    line=link.line,
                    text=link.text,
                    target_id=link.target_id,
                    old_path=link.path,
                    new_path=None,
                    status="dead",
                )
            )
            warnings.append(
                ScanWarning(
                    path=source,
                    reason="link_dead",
                    message=(
                        f"{source.name}:{link.line}: link "
                        f"{link.target_id or link.path!r} does not resolve"
                    ),
                )
            )
            continue

        if status == "resolved":
            continue

        assert target is not None
        new_path = relative_destination(source, target.path)
        new_dest = f"{new_path}#{target.id}"
        dest_start, dest_end = match.span("dest")
        edits.append((dest_start, dest_end, _render_destination(new_dest)))
        reports.append(
            LinkReport(
                file=source,
                line=link.line,
                text=link.text,
                target_id=target.id,
                old_path=link.path,
                new_path=new_path,
                status="stale",
            )
        )

    if not edits:
        return text, tuple(reports), tuple(warnings)

    new_text = text
    for start, end, replacement in sorted(edits, key=lambda e: e[0], reverse=True):
        new_text = new_text[:start] + replacement + new_text[end:]

    return new_text, tuple(reports), tuple(warnings)


def _read_editable(path: Path) -> EditableFile | None:
    try:
        return load_for_edit(path)
    except OSError:
        return None


def _iter_target_paths(workspace: Workspace, paths: tuple[Path, ...]) -> list[Path]:
    if paths:
        return list(paths)
    result: list[Path] = []
    for directory in (workspace.meetings_dir, workspace.notes_dir):
        if directory.is_dir():
            result.extend(sorted(directory.rglob("*.md")))
    if workspace.tasks_file.is_file():
        result.append(workspace.tasks_file)
    return result


def _task_links(task: Task, tasks_path: Path) -> tuple[Link, ...]:
    """Every Link named in one task's `links:` field, already carrying that
    task's own line and text -- the one place `find_task_links` is called, so
    every caller gets a correct record without patching it afterward."""
    if not task.links:
        return ()
    return find_task_links(",".join(task.links), source=tasks_path, line=task.line, text=task.text)


def _task_field_reports(workspace: Workspace, tasks_path: Path) -> list[LinkReport]:
    tasks, _warnings = load_tasks(workspace)
    reports: list[LinkReport] = []
    for task in tasks:
        for link in _task_links(task, tasks_path):
            _target, status = resolve_link(workspace, link)
            if status == "resolved":
                continue
            reports.append(
                LinkReport(
                    file=tasks_path,
                    line=task.line,
                    text=task.text,
                    target_id=link.target_id,
                    old_path=None,
                    new_path=None,
                    status=status,
                )
            )
    return reports


def check_links(workspace: Workspace, paths: tuple[Path, ...] = ()) -> tuple[LinkReport, ...]:
    """Report every stale and dead link under `paths` (the whole workspace when
    empty). Writes nothing, ever. Never raises."""
    reports: list[LinkReport] = []
    for path in _iter_target_paths(workspace, paths):
        if path == workspace.tasks_file:
            # tasks.md carries both kinds: `links:` field ids, and ordinary
            # markdown links in a task's text or its indented body (007). It
            # gets the field pass *and* the same markdown scan every other file
            # gets -- not one instead of the other.
            reports.extend(_task_field_reports(workspace, path))
        file = _read_editable(path)
        if file is None:
            continue
        _new_text, file_reports, _warnings = heal_text(workspace, file.text, source=path)
        reports.extend(file_reports)
    return tuple(reports)


def heal_links(
    workspace: Workspace, paths: tuple[Path, ...] = (), *, dry_run: bool = False
) -> tuple[LinkReport, ...]:
    """Rewrite every stale link under `paths` (the whole workspace when empty).
    Touches no dead link. A file with nothing stale in it is never opened for
    writing, so its `updated` never moves. `--dry-run` reports exactly what a
    real run would then change, and writes nothing. Never raises."""
    reports: list[LinkReport] = []
    for path in _iter_target_paths(workspace, paths):
        if path == workspace.tasks_file:
            # Field ids are never path-repaired, but markdown links in a task's
            # text or body are -- so tasks.md falls through to the writer below.
            reports.extend(_task_field_reports(workspace, path))
        file = _read_editable(path)
        if file is None:
            continue
        new_text, file_reports, _warnings = heal_text(workspace, file.text, source=path)
        reports.extend(file_reports)
        if dry_run or new_text == file.text:
            continue
        out_text = _apply_line_ending_policy(new_text, file.newline, file.trailing_newline)
        write_text_atomic(path, out_text)
    return tuple(reports)


# --- Inbound and outbound -----------------------------------------------------


def resolve_href(workspace: Workspace, source: Path, href: str) -> LinkTarget | None:
    """The record a rendered link points at, for a click in a preview pane.

    `href` is a raw markdown destination exactly as the renderer hands it back.
    Resolution is the usual id-first, path-second rule.

    Returns None for anything choom does not own -- an empty destination, a
    URL carrying a scheme, or a path and id that resolve to nothing -- so a
    caller can fall through to whatever the platform normally does with it
    rather than swallowing the click.

    Never raises.
    """
    if not href or _SCHEME_RE.match(href):
        return None

    path_part, sep, frag = href.partition("#")
    target_id = frag if sep and frag else None
    path = path_part or None
    if path is None and target_id is None:
        return None

    link = Link(
        source=source,
        line=0,
        text="",
        path=path,
        target_id=target_id,
        start=0,
        end=0,
        in_tasks_field=False,
    )
    target, _status = resolve_link(workspace, link)
    return target


def outbound_links(workspace: Workspace, source: Path) -> tuple[tuple[Link, LinkStatus], ...]:
    """Links `source` points at, including any that do not resolve.

    Reads one file. For a document already in memory, prefer `find_links`
    directly -- this is the convenience form. Never raises; an unreadable file
    yields ().
    """
    results: list[tuple[Link, LinkStatus]] = []
    if source == workspace.tasks_file:
        for link in _all_task_field_links(workspace, source):
            results.append((link, resolve_link(workspace, link)[1]))

    try:
        text = source.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return tuple(results)
    for link in find_links(text, source=source):
        results.append((link, resolve_link(workspace, link)[1]))
    return tuple(results)


def _all_task_field_links(workspace: Workspace, tasks_path: Path) -> list[Link]:
    tasks, _warnings = load_tasks(workspace)
    links: list[Link] = []
    for task in tasks:
        links.extend(_task_links(task, tasks_path))
    return links


def _tasks_file_links(tasks_path: Path) -> tuple[tuple[int | None, Link], ...]:
    """Markdown links written in `tasks.md` itself, each paired with the line of
    the task that owns it.

    A task owns its own checkbox line and every line of its indented body. A
    link outside any task -- in a heading, or in preamble prose -- is owned by
    nobody and pairs with None.

    These are ordinary `[text](path#id)` links carrying real paths, and are
    entirely separate from `links:` field ids, which carry no path and are
    handled by `_task_links`. A task can have both.

    Never raises; an unreadable file yields ().
    """
    try:
        text = tasks_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ()

    parsed = parse_tasks(text)
    owner_of_line: dict[int, int] = {}
    for task, span in zip(parsed.tasks, parsed.bodies, strict=True):
        owner_of_line[task.line - 1] = task.line
        for idx in range(span.start, span.end):
            owner_of_line[idx] = task.line

    return tuple(
        (owner_of_line.get(link.line - 1), link) for link in find_links(text, source=tasks_path)
    )


def outbound_for_target(
    workspace: Workspace, target: LinkTarget
) -> tuple[tuple[Link, LinkStatus], ...]:
    """Outbound links for one resolved record -- the building block behind
    `choom links <id> --direction out`. For a document this is exactly
    `outbound_links`; for a task, only what that task itself points at -- its
    `links:` field plus any markdown link in its own text or indented body --
    never every task in tasks.md, which holds many records in one file. Never
    raises."""
    if target.kind != "task":
        return outbound_links(workspace, target.path)

    tasks, _warnings = load_tasks(workspace)
    task = next((t for t in tasks if t.id == target.id), None)
    if task is None:
        return ()

    links = list(_task_links(task, workspace.tasks_file))
    links.extend(
        link
        for owner_line, link in _tasks_file_links(workspace.tasks_file)
        if owner_line == task.line
    )
    return tuple((link, resolve_link(workspace, link)[1]) for link in links)


def inbound_links(workspace: Workspace, target_id: str) -> tuple[Link, ...]:
    """Every link in the workspace that points at `target_id`, computed now by
    scanning.

    Nothing is stored, nothing persists between calls, and no file is written.
    Each file's bytes are substring-tested for the id first and only parsed
    when that hits, so this never parses the frontmatter of the workspace.

    An occurrence of the id that is not inside a link -- prose, or the target's
    own frontmatter `id:` line -- is not a link and is not returned.

    Never raises. An unreadable file is skipped.
    """
    results: list[Link] = []
    needle = target_id.encode("utf-8")

    for directory in (workspace.meetings_dir, workspace.notes_dir):
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.md")):
            try:
                data = path.read_bytes()
            except OSError:
                continue
            if needle not in data:
                continue
            text = data.decode("utf-8", errors="replace")
            for link in find_links(text, source=path):
                if link.target_id == target_id:
                    results.append(link)

    tasks_path = workspace.tasks_file
    if tasks_path.is_file():
        for link in _all_task_field_links(workspace, tasks_path):
            if link.target_id == target_id:
                results.append(link)
        # ...and markdown links written in tasks.md itself, which are ordinary
        # links that happen to live in a task's text or body (007).
        for _owner_line, link in _tasks_file_links(tasks_path):
            if link.target_id == target_id:
                results.append(link)

    return tuple(results)


def _report_for_link(link: Link, target: LinkTarget | None, status: LinkStatus) -> LinkReport:
    new_path = None
    if status == "stale" and target is not None and not link.in_tasks_field:
        new_path = relative_destination(link.source, target.path)
    return LinkReport(
        file=link.source,
        line=link.line,
        text=link.text,
        target_id=link.target_id,
        old_path=link.path,
        new_path=new_path,
        status=status,
    )


def links_for_id(
    workspace: Workspace, target_id: str, *, direction: LinkDirection = "both"
) -> tuple[LinkTarget | None, tuple[LinkReport, ...], tuple[LinkReport, ...]]:
    """The building block behind `choom links <id>`.

    Returns `(target, outbound_reports, inbound_reports)`. `target` is None
    when `target_id` itself does not resolve -- the caller should treat that
    as "not found" (exit 1); an empty pair of report tuples for an id that
    *does* resolve is a normal, successful result (exit 0). Either report
    tuple is empty when `direction` excludes it.

    Never raises.
    """
    target, _warnings = resolve_id(workspace, target_id)
    if target is None:
        return None, (), ()

    outbound: tuple[LinkReport, ...] = ()
    if direction in ("out", "both"):
        outbound = tuple(
            _report_for_link(link, resolve_link(workspace, link)[0], status)
            for link, status in outbound_for_target(workspace, target)
        )

    inbound: tuple[LinkReport, ...] = ()
    if direction in ("in", "both"):
        inbound_reports = []
        for link in inbound_links(workspace, target_id):
            link_target, status = resolve_link(workspace, link)
            inbound_reports.append(_report_for_link(link, link_target, status))
        inbound = tuple(inbound_reports)

    return target, outbound, inbound


# --- Search, for /link ---------------------------------------------------------


def find_link_targets(workspace: Workspace, query: str) -> tuple[LinkTarget, ...]:
    """Records whose title or id matches `query`, case-insensitive substring.

    Reuses the same matching rule as the list filter (`match_document`) so
    `/link` and the TUI filter never disagree about what "matches" means.
    Caller decides what to do with zero or several results; this reports, it
    does not choose.

    Never raises.
    """
    results: list[LinkTarget] = []

    meetings, _warnings = scan_meetings(workspace)
    for document in meetings:
        if match_document(document, query) or query.lower() in document.id.lower():
            results.append(
                LinkTarget(
                    id=document.id,
                    path=document.path,
                    title=document.title,
                    kind="meeting",
                    line=None,
                )
            )

    notes, _warnings = scan_notes(workspace)
    for document in notes:
        if match_document(document, query) or query.lower() in document.id.lower():
            results.append(
                LinkTarget(
                    id=document.id,
                    path=document.path,
                    title=document.title,
                    kind="note",
                    line=None,
                )
            )

    tasks, _warnings = load_tasks(workspace)
    for task in tasks:
        if task.id is None:
            continue
        if match_task(task, query) or query.lower() in task.id.lower():
            results.append(
                LinkTarget(
                    id=task.id,
                    path=workspace.tasks_file,
                    title=task.text,
                    kind="task",
                    line=task.line,
                )
            )

    return tuple(results)
