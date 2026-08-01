from __future__ import annotations

import re
import tomllib
from pathlib import Path

from choom.core.atomic_write import write_text_atomic
from choom.core.errors import UsageError, WorkspaceError
from choom.core.models import Workspace

LEGAL_ASSISTANT_VALUES = ("claude", "copilot", "none")

_ASSISTANT_HEADER = re.compile(r"^\[assistant\][ \t]*$", re.MULTILINE)
_TABLE_HEADER = re.compile(r"^\[", re.MULTILINE)
_NAME_LINE = re.compile(r"^name\s*=.*$", re.MULTILINE)


def _config_path(workspace: Workspace) -> Path:
    return workspace.root / ".choom" / "config.toml"


def get_assistant(workspace: Workspace) -> str | None:
    """Return the configured assistant name, or None when unset.

    Never raises. A missing file, a missing [assistant] table, an unreadable or malformed
    file, and a value that is not a legal setting all return None and are treated the same
    as the user never having set this -- a hand-edited config must not stop choom from
    opening (Principle IV).
    """
    try:
        with _config_path(workspace).open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return None
    table = data.get("assistant")
    if not isinstance(table, dict):
        return None
    value = table.get("name")
    return value if value in LEGAL_ASSISTANT_VALUES else None


def set_assistant(workspace: Workspace, value: str) -> None:
    """Record the assistant, creating the [assistant] table if it is absent.

    Edits the single `name` line and no other byte, preserving comments, key order, and
    any unknown keys; writes atomically via a same-directory temp file and os.replace.

    Raises:
        UsageError: `value` is not claude, copilot, or none. Nothing is written.
        WorkspaceError: the config file cannot be read or written.
    """
    if value not in LEGAL_ASSISTANT_VALUES:
        raise UsageError(
            f"assistant must be one of {', '.join(LEGAL_ASSISTANT_VALUES)}; got {value!r}"
        )

    path = _config_path(workspace)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise WorkspaceError(f"could not read {path}: {exc}") from exc

    newline = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")
    new_text = _apply_assistant_value(text, value)
    if newline != "\n":
        new_text = new_text.replace("\n", newline)

    write_text_atomic(path, new_text)


def _apply_assistant_value(text: str, value: str) -> str:
    """Line-targeted edit: replace `[assistant]`'s `name` line, insert it as the
    table's first key if the table exists without one, or append the whole table if
    it is absent. Every other byte -- comments, key order, unknown keys -- survives."""
    if text and not text.endswith("\n"):
        text = text + "\n"

    header = _ASSISTANT_HEADER.search(text)
    if header is None:
        return text + f'\n[assistant]\nname = "{value}"\n'

    body_start = text.index("\n", header.start()) + 1
    next_header = _TABLE_HEADER.search(text, body_start)
    body_end = next_header.start() if next_header else len(text)
    body = text[body_start:body_end]

    name_line = _NAME_LINE.search(body)
    if name_line is not None:
        new_body = body[: name_line.start()] + f'name = "{value}"' + body[name_line.end() :]
    else:
        new_body = f'name = "{value}"\n' + body

    return text[:body_start] + new_body + text[body_end:]
