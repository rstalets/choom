from __future__ import annotations

import re
from pathlib import Path

from choom.core.editing import load_for_edit, save_buffer

_MASKED_UPDATED = re.compile(r"^updated:.*$", re.MULTILINE)


def _normalize(text: str) -> str:
    return _MASKED_UPDATED.sub("updated: <masked>", text)


def _make_document(newline: str, *, trailing: bool) -> str:
    lines = [
        "---",
        "id: meeting_1",
        'title: "line ending test"',
        "created: 2026-01-01T09:00:00",
        "updated: 2026-01-01T09:00:00",
        "---",
        "",
        "Body line one.",
        "Body line two.",
    ]
    text = "\n".join(lines)
    if trailing:
        text += "\n"
    return text.replace("\n", newline)


def _round_trip(path: Path, newline: str, *, trailing: bool) -> None:
    original_bytes = path.read_bytes()

    file = load_for_edit(path)
    result = save_buffer(path, file.text, file)

    assert result.ok is True
    new_bytes = path.read_bytes()
    assert newline.encode() in new_bytes or newline == "\n"
    assert _normalize(new_bytes.decode("utf-8")) == _normalize(original_bytes.decode("utf-8"))

    if trailing:
        assert new_bytes.endswith(newline.encode())
    else:
        assert not new_bytes.endswith(b"\n")


def test_crlf_with_trailing_newline_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "doc.md"
    path.write_bytes(_make_document("\r\n", trailing=True).encode("utf-8"))
    _round_trip(path, "\r\n", trailing=True)


def test_crlf_without_trailing_newline_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "doc.md"
    path.write_bytes(_make_document("\r\n", trailing=False).encode("utf-8"))
    _round_trip(path, "\r\n", trailing=False)


def test_lf_with_trailing_newline_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "doc.md"
    path.write_bytes(_make_document("\n", trailing=True).encode("utf-8"))
    _round_trip(path, "\n", trailing=True)


def test_lf_without_trailing_newline_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "doc.md"
    path.write_bytes(_make_document("\n", trailing=False).encode("utf-8"))
    _round_trip(path, "\n", trailing=False)


def test_mixed_endings_normalise_to_first_seen_convention(tmp_path: Path) -> None:
    path = tmp_path / "doc.md"
    # First line ending is CRLF; a later one is bare LF.
    raw = "---\r\nid: meeting_1\nupdated: 2026-01-01T09:00:00\r\n---\r\n"
    path.write_bytes(raw.encode("utf-8"))

    file = load_for_edit(path)
    assert file.newline == "\r\n"

    result = save_buffer(path, file.text, file)
    assert result.ok is True
    new_bytes = path.read_bytes()
    # every line ending is now CRLF, including the one that was originally bare LF
    assert b"\n" not in new_bytes.replace(b"\r\n", b"")
