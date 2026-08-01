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
    _write_assistant_key(workspace, "name", f'"{value}"')


def get_launch_offer_made(workspace: Workspace) -> bool:
    """Whether the launch question (013-assistant-discovery-file, US2) has been asked
    and answered in this workspace.

    Never raises. A missing file, a missing [assistant] table, an unreadable or
    malformed file, an absent key, and a non-boolean value all read as False -- "not
    offered" -- so a hand-edited config cannot stop choom from opening (Principle IV,
    research R5).
    """
    try:
        with _config_path(workspace).open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return False
    table = data.get("assistant")
    if not isinstance(table, dict):
        return False
    value = table.get("launch_offer_made")
    return value if isinstance(value, bool) else False


def set_launch_offer_made(workspace: Workspace, value: bool) -> None:
    """Record that the launch offer has been asked and answered, on either key
    (FR-027), or clear the record on an explicit set of the assistant (FR-028).

    Raises:
        WorkspaceError: the config file cannot be read or written.
    """
    _write_assistant_key(workspace, "launch_offer_made", "true" if value else "false")


def _write_assistant_key(workspace: Workspace, key: str, raw_value: str) -> None:
    """Read-edit-write one key of `[assistant]` atomically. `raw_value` is the exact
    right-hand side already formatted as TOML (`'"claude"'`, `"true"`) -- this function
    does not know or care what kind of value it is, only where the line goes.

    Raises:
        WorkspaceError: the config file cannot be read or written.
    """
    path = _config_path(workspace)
    try:
        # newline="" disables universal-newline translation: plain read_text() would
        # silently collapse "\r\n" to "\n" before the CRLF check below ever saw it.
        with path.open(encoding="utf-8", newline="") as f:
            raw = f.read()
    except OSError as exc:
        raise WorkspaceError(f"could not read {path}: {exc}") from exc

    newline = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")
    new_text = _apply_assistant_key(text, key, raw_value)
    if newline != "\n":
        new_text = new_text.replace("\n", newline)

    write_text_atomic(path, new_text)


def _apply_assistant_key(text: str, key: str, raw_value: str) -> str:
    """Line-targeted edit: replace `[assistant]`'s `key` line, insert it as the
    table's first key if the table exists without one, or append the whole table if
    it is absent. Every other byte -- comments, key order, unknown keys -- survives.

    Generalised from the original `name`-only version (research R5) so a second key
    (`launch_offer_made`) can be written through the same three cases rather than a
    second regex block beside it -- one edit path, one place for a bug to live.
    """
    if text and not text.endswith("\n"):
        text = text + "\n"

    header = _ASSISTANT_HEADER.search(text)
    if header is None:
        return text + f"\n[assistant]\n{key} = {raw_value}\n"

    body_start = text.index("\n", header.start()) + 1
    next_header = _TABLE_HEADER.search(text, body_start)
    body_end = next_header.start() if next_header else len(text)
    body = text[body_start:body_end]

    key_line = re.compile(rf"^{re.escape(key)}\s*=.*$", re.MULTILINE).search(body)
    if key_line is not None:
        new_body = body[: key_line.start()] + f"{key} = {raw_value}" + body[key_line.end() :]
    else:
        new_body = f"{key} = {raw_value}\n" + body

    return text[:body_start] + new_body + text[body_end:]
