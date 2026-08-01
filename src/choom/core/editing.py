from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from choom.core.atomic_write import write_text_atomic
from choom.core.errors import WorkspaceError
from choom.core.models import EditableFile, SaveResult, ScanWarning, Workspace

_UPDATED_LINE = re.compile(r"^updated:.*$", re.MULTILINE)


def stamp_updated(text: str, timestamp: str) -> tuple[str, bool]:
    """Replace the value on the frontmatter block's first `updated:` line, changing no
    other byte. Returns (new_text, True) when stamped, (text, False) when the block or
    the line could not be located. Never raises.
    """
    if not text.startswith("---\n"):
        return text, False

    terminator = text.find("\n---", 3)
    if terminator == -1:
        return text, False

    block = text[4 : terminator + 1]
    match = _UPDATED_LINE.search(block)
    if match is None:
        return text, False

    start = 4 + match.start()
    end = 4 + match.end()
    new_text = text[:start] + f"updated: {timestamp}" + text[end:]
    return new_text, True


def load_for_edit(path: Path) -> EditableFile:
    """Read a file for editing: whole text including frontmatter, normalised to "\\n",
    with the line-ending convention and trailing-newline state captured for restoration.

    Raises:
        OSError: the file cannot be read.
    """
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        raw = f.read()

    first_break = raw.find("\n")
    if first_break > 0 and raw[first_break - 1] == "\r":
        newline = "\r\n"
    else:
        newline = "\n"

    trailing_newline = raw.endswith("\n")
    text = raw.replace("\r\n", "\n")
    return EditableFile(path=path, text=text, newline=newline, trailing_newline=trailing_newline)


def _apply_line_ending_policy(text: str, newline: str, trailing_newline: bool) -> str:
    if newline != "\n":
        text = text.replace("\n", newline)
    has_trailing = text.endswith("\n")
    if trailing_newline and not has_trailing:
        text = text + newline
    elif not trailing_newline and has_trailing:
        text = text[: -len(newline)]
    return text


def save_buffer(
    path: Path,
    text: str,
    file: EditableFile,
    *,
    now: datetime | None = None,
    workspace: Workspace | None = None,
) -> SaveResult:
    """Stamp `updated`, restore `file`'s line endings and trailing newline, and write
    atomically to `path` via a same-directory temp file and os.replace.

    When `workspace` is given, stale links in the body are healed before `updated`
    is stamped, and any dead link found is reported in `SaveResult.warnings`
    (never fatal -- a dead link never sets `ok=False`). When `workspace` is None,
    behaviour is exactly as before this parameter existed.

    Never raises on a write failure -- returns SaveResult(ok=False) with a
    user-facing message, leaving the target byte-identical.
    """
    assert path == file.path

    warnings: tuple[ScanWarning, ...] = ()
    if workspace is not None:
        from choom.core.links import heal_text

        text, _reports, warnings = heal_text(workspace, text, source=path)

    when = now or datetime.now()
    timestamp = when.replace(microsecond=0).isoformat()
    stamped_text, stamped = stamp_updated(text, timestamp)
    out_text = _apply_line_ending_policy(stamped_text, file.newline, file.trailing_newline)

    try:
        write_text_atomic(path, out_text)
    except WorkspaceError as exc:
        return SaveResult(ok=False, saved_text="", stamped=False, message=str(exc))
    return SaveResult(
        ok=True, saved_text=stamped_text, stamped=stamped, message="", warnings=warnings
    )
