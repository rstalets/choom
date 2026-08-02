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
    LinkCandidate,
    LinkDirection,
    LinkReport,
    LinkStatus,
    LinkTarget,
    ScanWarning,
    Task,
    UrlConversion,
    Workspace,
)
from choom.core.notes import scan_notes
from choom.core.task_store import iter_done_files, load_done_tasks, load_task_store
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


# --- Bare URL formatting on save (018-automatic-link-detection) ---------------
#
# format_bare_urls() wraps every bare http(s):// URL in a document as a real
# CommonMark inline link, [<url>](<url>), on a save the user performed. The
# rule that governs every mask below (T007/research R1, and it belongs here
# in a comment, not only in the spec): a *scanner* -- _LINK_RE above -- exists
# to find record links choom will act on, and being narrow there is safe: a
# link it misses is simply not healed. A *mask* exists to find every span
# that must not be touched, and being narrow there is unsafe: a link a mask
# misses gets a second [...](...) wrapped around a destination it failed to
# see, corrupting the file. _LINK_RE's destination alternative is
# `[^\s()]*`, so it misses a destination with balanced parentheses
# (`[a](https://x.com/Foo_(bar))`), an image (`(?<!!)` excludes it), a
# reference definition, and an autolink -- four ordinary forms a Wikipedia
# URL or an existing choom link can take. A mask MUST be a superset of the
# grammar it guards, never a subset of it, which is why the masks below are
# new and deliberately wider rather than a reuse of _LINK_RE.

_BARE_URL_RE = re.compile(
    r'(?<![^\s([{"\'*_~|>])(?P<u>(?P<scheme>https?://)[^\s<>\[\]]*)',
    re.IGNORECASE,
)

#: FR-013's trailing-boundary character set: dropped one at a time, repeatedly,
#: from the end of a candidate. `?`, `#`, `&`, `=`, `/`, and `%` are never in
#: this set -- they are part of a URL, not punctuation trailing it.
_TRAILING_CHARS = ".,:;!?'\"*_~"

_COMMENT_START = "<!--"
_COMMENT_END = "-->"

_ANGLE_SPAN_RE = re.compile(r"<[^<>\n]*>")

#: FR-012: a link reference definition, `[label]: destination`, optionally
#: indented up to 3 spaces (CommonMark's own limit before it becomes an
#: indented code block). Wrapping the destination would break the
#: definition and silently kill every `[label]` reference in the file.
_REFDEF_RE = re.compile(r"^ {0,3}\[[^\]\n]*\]:[ \t]*\S+", re.MULTILINE)


def _mask_frontmatter(text: str) -> str:
    r"""Blank the frontmatter block -- the leading ``---\n`` through the
    closing ``\n---``, inclusive -- to spaces, preserving every line
    terminator so offsets found afterward stay valid in `text` unchanged.
    Left byte-identical when either delimiter is absent.

    Stricter than `heal_text`, which never masks frontmatter, because that
    function only ever rewrites a destination inside an *existing* link,
    which cannot occur in frontmatter choom itself wrote -- this function's
    exposure is immediate, not theoretical (research R3): an unquoted YAML
    scalar that starts with ``[`` becomes a flow sequence, and wrapping a
    bare URL in frontmatter (`title: [https://x](https://x)`) turns the
    block into unparseable YAML. `_parse_document` then returns
    `(None, malformed_yaml)`, and the note drops out of every list, every
    search, and every `--json` payload choom produces -- the note is still
    on disk and is now invisible to the tool. This mask exists so that
    failure can never happen.
    """
    if not text.startswith("---\n"):
        return text
    terminator = text.find("\n---", 3)
    if terminator == -1:
        return text
    end = terminator + len("\n---")
    masked_block = "".join(ch if ch in ("\n", "\r") else " " for ch in text[:end])
    return masked_block + text[end:]


def _mask_comments(text: str) -> str:
    """Blank HTML comments, ``<!--`` through the next ``-->``, to spaces,
    across line boundaries, preserving every line terminator. Covers the
    task line's own metadata comment (choom parses its contents) and any
    comment a user wrote for themselves. An unterminated comment masks to
    end-of-file -- the conservative direction, since it converts less."""
    out = list(text)
    pos = 0
    while True:
        start = text.find(_COMMENT_START, pos)
        if start == -1:
            break
        close = text.find(_COMMENT_END, start + len(_COMMENT_START))
        end = close + len(_COMMENT_END) if close != -1 else len(text)
        for i in range(start, end):
            if out[i] not in ("\n", "\r"):
                out[i] = " "
        pos = end
    return "".join(out)


def _mask_links(text: str) -> str:
    r"""Blank every markdown inline link or image, ``[text](dest)`` /
    ``![alt](dest)`` -- the *whole* span, link text and destination
    together, to spaces (FR-009, research R1/R6). Masking only the
    destination would leave the link-text copy of an already-converted URL
    exposed on the next save and break idempotency: the second pass would
    then produce ``[[U](U)](U)`` and the third ``[[[U](U)](U)](U)``, the
    user's file degrading a little on every save. Masking the whole span is
    what makes ``[U](U)`` inert on every later pass.

    Does not use `_LINK_RE` (see the module comment above this section) --
    the destination is scanned with paren-depth counting instead, so a
    destination with balanced parentheses is fully covered. An unbalanced
    paren inside an *angle-wrapped* destination defeats depth counting by
    construction (there is no way to tell, by counting alone, which ``)``
    closes the link); when that happens this function simply does not
    recognise a link here, and `_mask_angle` (run immediately after, in the
    mask pipeline) backstops it by blanking the `<...>` run on its own
    terms, which need no paren balance at all.

    An unclosed ``[`` never swallows the rest of the file: the text slot is
    only ever treated as a candidate up to the next ``[`` or ``]``, exactly
    matching `_LINK_RE`'s own ``[^\[\]]*`` text rule, and a failed match
    advances one character rather than skipping ahead.
    """
    out = list(text)
    i = 0
    n = len(text)
    while i < n:
        if text[i] != "[":
            i += 1
            continue
        text_end = i + 1
        while text_end < n and text[text_end] not in ("[", "]"):
            text_end += 1
        if text_end >= n or text[text_end] != "]" or text_end + 1 >= n or text[text_end + 1] != "(":
            i += 1
            continue
        depth = 1
        j = text_end + 2
        closed_at = -1
        while j < n:
            ch = text[j]
            if ch == "\n" and j + 1 < n and text[j + 1] == "\n":
                break  # a destination never spans a blank line; give up
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    closed_at = j
                    break
            j += 1
        if closed_at == -1:
            i += 1
            continue
        span_start = i - 1 if i > 0 and text[i - 1] == "!" else i
        span_end = closed_at + 1
        for k in range(span_start, span_end):
            if out[k] not in ("\n", "\r"):
                out[k] = " "
        i = span_end
    return "".join(out)


def _mask_angle(text: str) -> str:
    """Blank ``<...>`` runs containing no newline, to spaces -- a CommonMark
    autolink (``<https://example.com>``) and a raw HTML tag
    (``<a href="...">``) in one rule, since both share the delimiter and
    neither may contain a literal newline (FR-010, FR-011). Also the
    backstop for `_mask_links`: an angle-wrapped link destination whose
    interior parentheses are unbalanced defeats that function's paren-depth
    counter, and this rule catches the ``<...>`` regardless, because it does
    not count parens at all."""
    return _ANGLE_SPAN_RE.sub(lambda m: " " * len(m.group()), text)


def _mask_refdefs(text: str) -> str:
    """Blank a link reference definition, ``[label]: destination`` (FR-012),
    to spaces. Wrapping the destination would turn it into
    ``[label]: [dest](dest)``, which is no longer a valid reference
    definition, and would silently kill every ``[label]`` reference
    elsewhere in the file."""
    return _REFDEF_RE.sub(lambda m: " " * len(m.group()), text)


def _mask_for_bare_urls(text: str) -> str:
    r"""Compose the seven exclusion masks `format_bare_urls` relies on, in the
    order that lets each one see only real structure (research R2):

    frontmatter -> fences -> code spans -> comments -> links/images ->
    angle spans -> reference definitions

    Frontmatter is masked first because its own contents must never be
    read as anything else. Fences and code spans come next, reusing
    `_mask_fences` and `_mask_code_spans` **verbatim** -- this function adds
    no new fence-parsing or backtick-parsing logic anywhere (FR-031); a
    second notion of "what counts as code" in one module is exactly how a
    byte-preservation guarantee gets quietly broken. Comments are masked for
    the same opacity reason -- a fenced block or a comment containing
    ``[a](b)`` must never be read as link syntax by the links/images mask
    that runs after it. Angle spans run *after* links/images so they can
    backstop the one case paren-depth counting cannot resolve. Reference
    definitions run last.

    Every mask blanks its spans to spaces and leaves every ``\n``/``\r`` in
    place, so the string returned is always the same length as `text`, with
    the same newline positions -- the property that makes every offset found
    in the masked text valid in `text` unchanged.
    """
    masked = _mask_frontmatter(text)
    masked = _mask_fences(masked)
    masked = _mask_code_spans(masked)
    masked = _mask_comments(masked)
    masked = _mask_links(masked)
    masked = _mask_angle(masked)
    masked = _mask_refdefs(masked)
    return masked


def _trim_bare_url(candidate: str) -> str:
    """Trim `candidate`'s tail per FR-013, repeatedly, until neither rule
    fires: drop a final character in `. , : ; ! ? ' " * _ ~`, or drop a
    final `)` while `candidate` holds more `)` than `(`. The paren rule is
    what separates "the URL owns this parenthesis" from "the sentence
    does", and is exact in both directions since it only ever counts.
    `?`, `&`, `=`, `/`, and `%` are never touched -- they are the URL, not
    punctuation trailing it. Never raises."""
    while candidate:
        if candidate[-1] in _TRAILING_CHARS:
            candidate = candidate[:-1]
            continue
        if candidate[-1] == ")" and candidate.count(")") > candidate.count("("):
            candidate = candidate[:-1]
            continue
        break
    return candidate


def format_bare_urls(text: str) -> tuple[str, tuple[UrlConversion, ...]]:
    """Wrap every bare ``http://`` or ``https://`` URL in `text` as a
    markdown link (018-automatic-link-detection, FR-001, contracts/core-
    api.md C1).

    Each bare URL becomes ``[<url>](<destination>)`` with the URL
    reproduced byte-for-byte in both slots; the destination is angle-wrapped
    only when it contains a space, ``(``, ``)``, ``<``, or ``>``, by
    `_render_destination` -- the same rule every other link choom writes
    already uses.

    A URL is skipped -- left byte-identical -- when it sits in frontmatter,
    a fenced code block, an inline code span, an HTML comment, an existing
    link or image, a CommonMark autolink, a raw HTML tag, or a link
    reference definition; when it has no host after ``://``; when it does
    not begin a token (a candidate must start at the beginning of `text` or
    immediately after whitespace or one of ``([{"'*_~|>``); or when it
    contains ``[`` or ``]`` -- the candidate pattern's own character class
    already excludes both, so a bracketed IPv6 host such as
    ``https://[::1]/status`` never produces a convertible candidate in the
    first place.

    Returns `text` itself -- the same object -- when nothing was converted,
    so a caller can test identity and skip the rest of a save unconditionally.

    Idempotent: `format_bare_urls(format_bare_urls(t)[0])[0] ==
    format_bare_urls(t)[0]`, for any `t`, through any number of passes --
    masking the *whole* span of an existing link (`_mask_links`, above)
    means both copies of a converted URL are invisible to the next pass.

    Resolves nothing against the workspace, unlike `heal_text` -- a URL is
    self-describing, so this function takes no `Workspace` and no `Path`.

    Never raises. Any input is valid input.
    """
    masked = _mask_for_bare_urls(text)
    conversions: list[UrlConversion] = []
    for match in _BARE_URL_RE.finditer(masked):
        start = match.start("u")
        scheme = match.group("scheme")
        url = _trim_bare_url(match.group("u"))
        if len(url) <= len(scheme):
            continue
        end = start + len(url)
        replacement = f"[{url}]({_render_destination(url)})"
        conversions.append(UrlConversion(start=start, end=end, url=url, replacement=replacement))

    if not conversions:
        return text, ()

    new_text = text
    for conv in sorted(conversions, key=lambda c: c.start, reverse=True):
        new_text = new_text[: conv.start] + conv.replacement + new_text[conv.end :]

    return new_text, tuple(conversions)


def map_cursor_offset(conversions: tuple[UrlConversion, ...], offset: int) -> int:
    """Where `offset` -- a character offset into the text handed to
    `format_bare_urls` -- ends up in the text it returned (contracts/core-
    api.md C2).

    An offset at or before a conversion's start is unchanged, so far as that
    conversion is concerned. An offset strictly inside a converted span --
    after its start and before its end -- lands at the end of that span's
    replacement, since there is no meaningful position between the two
    copies of the URL a cursor could occupy. An offset at or after a
    conversion's end is shifted right by what that conversion added, and the
    next conversion is then checked the same way.

    Pure integer arithmetic over `conversions`, in ascending order by
    `start`; reads no text. Never raises.
    """
    shift = 0
    for conv in conversions:
        if offset <= conv.start:
            return offset + shift
        if offset < conv.end:
            return conv.start + shift + len(conv.replacement)
        shift += len(conv.replacement) - (conv.end - conv.start)
    return offset + shift


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
        # tasks.md first, and the done store only on a miss
        # (019-completed-tasks-partition, research R4/R9) -- resolving an
        # open task's id, the common case, costs exactly what it always
        # did. `LinkTarget.path` is *always* `workspace.tasks_file`,
        # whichever file actually holds the record right now (FR-024): this
        # is the canonical-address rule that is the whole reason completing
        # or reopening a task rewrites no mirror anywhere in the vault. Do
        # not "fix" this to the record's real path -- that would be the bug.
        tasks, task_warnings = load_tasks(workspace)
        warnings.extend(task_warnings)
        task_matches = [t for t in tasks if t.id == target_id]
        if not task_matches:
            done_tasks, done_warnings = load_done_tasks(workspace)
            warnings.extend(done_warnings)
            task_matches = [t for t in done_tasks if t.id == target_id]
        for task in task_matches:
            assert task.id is not None  # every match here matched t.id == target_id above
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
    # 019-completed-tasks-partition (FR-028): ordinary markdown links in a
    # completed task's text or body are still links and must not stop being
    # checked/healed because the task moved into the done store.
    result.extend(iter_done_files(workspace))
    return result


def _task_links(task: Task, tasks_path: Path) -> tuple[Link, ...]:
    """Every Link named in one task's `links:` field, already carrying that
    task's own line and text -- the one place `find_task_links` is called, so
    every caller gets a correct record without patching it afterward."""
    if not task.links:
        return ()
    return find_task_links(",".join(task.links), source=tasks_path, line=task.line, text=task.text)


def _task_field_reports(workspace: Workspace, tasks_path: Path) -> list[LinkReport]:
    # 019-completed-tasks-partition (FR-028): a completed task's own `links:`
    # field ids are still links. Every report is attributed to `tasks_path`
    # (always tasks.md, the canonical address, FR-024) regardless of which
    # file the record currently sits in.
    tasks, _warnings = load_task_store(workspace)
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
    # 019-completed-tasks-partition (FR-028): covers the whole store, not
    # just tasks.md, so a completed task's `links:` field is still found.
    tasks, _warnings = load_task_store(workspace)
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

    # 019-completed-tasks-partition (FR-028): a completed task is found by
    # searching the whole store, and its ordinary markdown links are read
    # from wherever its record actually sits (`task.source`) -- that is
    # where the bytes are -- while its `links:` field is still attributed
    # to tasks.md, the canonical address (FR-024).
    tasks, _warnings = load_task_store(workspace)
    task = next((t for t in tasks if t.id == target.id), None)
    if task is None:
        return ()

    source_path = task.source or workspace.tasks_file
    links = list(_task_links(task, workspace.tasks_file))
    links.extend(
        link for owner_line, link in _tasks_file_links(source_path) if owner_line == task.line
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

    # 019-completed-tasks-partition (FR-028): a completed task's own
    # markdown links move with it into the done store; they are still
    # links and must still be found. `links:` field ids are already covered
    # above via `_all_task_field_links`'s store-wide read.
    for done_path in iter_done_files(workspace):
        try:
            data = done_path.read_bytes()
        except OSError:
            continue
        if needle not in data:
            continue
        for _owner_line, link in _tasks_file_links(done_path):
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


def link_candidates(workspace: Workspace, query: str) -> tuple[LinkCandidate, ...]:
    """Records whose title, id, type, or tags match `query`, ready to be chosen from.

    The same matching rule as the list filter (`match_document` / `match_task`) and
    the same records `find_link_targets` reports -- this is that search plus the
    ordering and the per-row facts a picker needs. Newest first, ties by title,
    undated records last.

    Caller decides what to do with zero, one, or several results; this reports,
    it does not choose.

    Never raises.
    """
    results: list[LinkCandidate] = []

    meetings, _warnings = scan_meetings(workspace)
    for document in meetings:
        if match_document(document, query) or query.lower() in document.id.lower():
            results.append(
                LinkCandidate(
                    target=LinkTarget(
                        id=document.id,
                        path=document.path,
                        title=document.title,
                        kind="meeting",
                        line=None,
                    ),
                    collection="meeting",
                    # `Document.created` is a full ISO timestamp; the row (and
                    # every other date the TUI shows -- DocumentRow, the
                    # preview meta line) shows the date only, the same slice
                    # `document.created[:10]` already used there.
                    date=document.created[:10],
                )
            )

    notes, _warnings = scan_notes(workspace)
    for document in notes:
        if match_document(document, query) or query.lower() in document.id.lower():
            results.append(
                LinkCandidate(
                    target=LinkTarget(
                        id=document.id,
                        path=document.path,
                        title=document.title,
                        kind="note",
                        line=None,
                    ),
                    collection="note",
                    date=document.created[:10],
                )
            )

    tasks, _warnings = load_tasks(workspace)
    for task in tasks:
        if task.id is None:
            continue
        if match_task(task, query) or query.lower() in task.id.lower():
            results.append(
                LinkCandidate(
                    target=LinkTarget(
                        id=task.id,
                        path=workspace.tasks_file,
                        title=task.text,
                        kind="task",
                        line=task.line,
                    ),
                    collection="task",
                    date=task.created.isoformat() if task.created else None,
                )
            )

    # Two stable passes, the same idiom core/documents.py already uses for
    # newest-first ordering: sort by title first so it survives as the
    # tie-break, then sort by (has date, date) descending so dated candidates
    # come first, newest to oldest, and undated candidates land last, still in
    # title order among themselves.
    results.sort(key=lambda c: c.target.title.lower())
    results.sort(key=lambda c: (c.date is not None, c.date or ""), reverse=True)
    return tuple(results)


def find_link_targets(workspace: Workspace, query: str) -> tuple[LinkTarget, ...]:
    """Records whose title or id matches `query`, case-insensitive substring.

    A thin projection of `link_candidates` -- one scan and one definition of
    "matches", so this and the picker it backs can never disagree about what
    counts as a match. Caller decides what to do with zero or several results;
    this reports, it does not choose.

    Never raises.
    """
    return tuple(candidate.target for candidate in link_candidates(workspace, query))
